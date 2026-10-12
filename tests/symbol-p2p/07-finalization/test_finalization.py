import json
import pathlib
import socket
import ssl
import struct
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch

import finalization as sample
import p2p_common as common
import tls_test_support as legacy

ROOT = pathlib.Path(__file__).resolve().parents[3] / "symbol-p2p" / pathlib.Path(__file__).resolve().parent.name
# Synthetic structural fixtures, not valid signed proofs.
STATS = struct.pack('<IIQ32s', 3, 8, 246, bytes.fromhex('AB' * 32))
GROUP = struct.pack('<IIIIQ', 248, 1, 1, 1, 246) + bytes.fromhex('AB' * 32) + bytes(192)
PROOF = struct.pack('<IIIIQ32s', 304, 1, 3, 8, 246, bytes.fromhex('AB' * 32)) + GROUP


class ParserTests(unittest.TestCase):
    def test_request_bytes(self):
        cases = [('stats', None, '0800000032010000', 0x132),
                 ('epoch', 3, '0c0000003301000003000000', 0x135),
                 ('height', 246, '1000000034010000f600000000000000', 0x135)]
        for kind, value, wire, expected in cases:
            request, response, cap = sample.make_request(kind, value)
            self.assertEqual(request, bytes.fromhex(wire))
            self.assertEqual(response, expected)

    def test_invalid_requests(self):
        for kind, value in [('other', 1), ('epoch', 0), ('epoch', 2**32),
                            ('height', -1), ('height', 2**64), ('height', None)]:
            with self.subTest(kind=kind, value=value), self.assertRaises(ValueError):
                sample.make_request(kind, value)

    def test_statistics_fields(self):
        self.assertEqual(sample.parse_statistics(STATS), {
            'epoch': 3, 'point': 8, 'height': 246, 'hash': 'AB' * 32})

    def test_statistics_exact_length(self):
        for data in (STATS[:-1], STATS + b'x', b''):
            with self.assertRaises(common.ProtocolError):
                sample.parse_statistics(data)

    def test_proof_fields_and_groups(self):
        proof = sample.parse_proof(PROOF)
        self.assertEqual(proof['height'], 246)
        self.assertEqual(proof['groups'], [{'stage': 'precommit', 'height': 246,
                                           'hashes': ['AB' * 32], 'signatures_count': 1}])

    def test_empty_proof(self):
        self.assertIsNone(sample.parse_proof(b''))

    def test_all_nonempty_truncations(self):
        for length in range(1, len(PROOF)):
            with self.subTest(length=length), self.assertRaises(common.ProtocolError):
                sample.parse_proof(PROOF[:length])

    def test_bad_lengths_counts_version_stage(self):
        for offset, value in [(0, 0), (4, 2), (56, 0), (60, 2**32-1),
                              (64, 2**32-1), (68, 2)]:
            data = bytearray(PROOF)
            struct.pack_into('<I', data, offset, value)
            with self.subTest(offset=offset), self.assertRaises(common.ProtocolError):
                sample.parse_proof(bytes(data))

    def test_partial_group_header(self):
        for length in range(1, 24):
            data = bytearray(PROOF[:56] + bytes(length))
            struct.pack_into('<I', data, 0, len(data))
            with self.assertRaises(common.ProtocolError):
                sample.parse_proof(bytes(data))

    def test_multiple_groups(self):
        data = bytearray(PROOF + GROUP)
        struct.pack_into('<I', data, 0, len(data))
        self.assertEqual(len(sample.parse_proof(bytes(data))['groups']), 2)

    def test_response_requested_value_mismatch(self):
        with patch.object(sample, 'exchange', return_value=PROOF):
            with self.assertRaises(common.ProtocolError):
                sample.query('host', 7900, None, 'height', 247)
            with self.assertRaises(common.ProtocolError):
                sample.query('host', 7900, None, 'epoch', 4)

    def test_proof_size_cap_before_reading_body(self):
        stream = legacy.Stream(struct.pack('<II', sample.MAX_PROOF_PACKET + 1, 0x135) + b'body')
        with self.assertRaises(common.ProtocolError):
            common.read_packet(stream, 0x135, time.monotonic() + 1, sample.MAX_PROOF_PACKET)
        self.assertEqual(stream.data, b'body')

    def test_cli_requires_host(self):
        for args in ([],):
            run = subprocess.run([sys.executable, str(ROOT/'finalization.py')] + args,
                                 capture_output=True, text=True, timeout=5)
            self.assertEqual(run.returncode, 2)


class FinalizationTLSTests(unittest.TestCase):
    setUpClass = classmethod(legacy.TLSTests.setUpClass.__func__)
    tearDownClass = classmethod(legacy.TLSTests.tearDownClass.__func__)
    context = legacy.TLSTests.context

    def serve_reply(self, payload, packet_type, request_size):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        cert = self.base / 'server/cert'
        context.load_cert_chain(str(cert/'node.full.crt.pem'), str(cert/'node.key.pem'))
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(str(self.base/'client/cert/ca.crt.pem'))
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        listener.settimeout(5)
        port = listener.getsockname()[1]
        state = {}
        def handle():
            try:
                with listener:
                    tcp, _ = listener.accept()
                    with tcp:
                        tcp.settimeout(5)
                        with context.wrap_socket(tcp, server_side=True) as tls:
                            state['request'] = legacy.client.recv_exact(tls, request_size, time.monotonic()+5)
                            response = common.packet(packet_type, payload)
                            tls.sendall(response[:3])
                            tls.sendall(response[3:])
            except OSError as exc:
                state['error'] = str(exc)
        thread = threading.Thread(target=handle, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 6)
        return port, thread, state

    def test_statistics_cli(self):
        port, thread, state = self.serve_reply(STATS, 0x132, 8)
        cert = self.base / 'client/cert'
        run = subprocess.run([
            sys.executable, str(ROOT/'finalization.py'), '127.0.0.1',
            '--port', str(port), '--cert', str(cert/'node.full.crt.pem'),
            '--key', str(cert/'node.key.pem'),
        ], capture_output=True, text=True, timeout=15)
        thread.join(6)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout), sample.parse_statistics(STATS))
        self.assertEqual(state.get('request'), bytes.fromhex('0800000032010000'))
        self.assertNotIn('error', state)

    def test_proof_epoch_and_height(self):
        for kind, value, size in [('epoch', 3, 12), ('height', 246, 16)]:
            port, thread, state = self.serve_reply(PROOF, 0x135, size)
            result = sample.query('127.0.0.1', port, self.context(), kind, value)
            thread.join(6)
            self.assertEqual(result, sample.parse_proof(PROOF))
            self.assertEqual(state.get('request'), sample.make_request(kind, value)[0])
            self.assertNotIn('error', state)

    def test_empty_proof_reply(self):
        port, thread, state = self.serve_reply(b'', 0x135, 16)
        self.assertIsNone(sample.query('127.0.0.1', port, self.context(), 'height', 246))
        thread.join(6)
        self.assertNotIn('error', state)


if __name__ == '__main__':
    unittest.main()
