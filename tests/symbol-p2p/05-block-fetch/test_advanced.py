import json
import pathlib
import socket
import ssl
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch
from fixture_data import block_fixture, transaction_fixture
import p2p_common as common
import pull_block
import tls_test_support as legacy

ROOT = pathlib.Path(__file__).resolve().parents[3] / "symbol-p2p" / pathlib.Path(__file__).resolve().parent.name

class BlockTests(unittest.TestCase):
    def test_request_height_and_endian(self):
        self.assertEqual(pull_block.make_request(42), bytes.fromhex('10000000040000002a00000000000000'))
        for height in (-1, 2**64):
            with self.assertRaises(ValueError):
                pull_block.make_request(height)

    def test_sdk_decodes_known_fields(self):
        result = pull_block.parse_block(block_fixture(), 42)
        self.assertEqual(result['height'], 42)
        self.assertEqual(result['timestamp_ms_since_network_epoch'], 123456)
        self.assertEqual(result['signer'], '22'*32)
        self.assertEqual(result['previous_block_hash'], '33'*32)
        self.assertEqual(result['type_name'], 'NORMAL')

    def test_all_block_kinds_and_footer_lengths(self):
        for kind, size in ((0x8043, 424), (0x8143, 376), (0x8243, 424)):
            data = block_fixture(kind)
            self.assertEqual(len(data), size)
            self.assertEqual(pull_block.parse_block(data)['type'], kind)

    def test_incorrect_size_type_version_and_reserved(self):
        for offset, value in ((0, 0), (4, 1), (104, 1), (108, 2), (110, 0xff), (372, 1)):
            data = bytearray(block_fixture())
            data[offset] = value
            with self.subTest(offset=offset), self.assertRaises(common.ProtocolError):
                pull_block.parse_block(bytes(data))

    def test_all_header_truncations(self):
        for size in range(376):
            data = bytearray(block_fixture()[:size])
            if size >= 4:
                struct.pack_into('<I', data, 0, size)
            with self.subTest(size=size), self.assertRaises(common.ProtocolError):
                pull_block.parse_block(bytes(data))

    def test_requested_height_mismatch(self):
        with self.assertRaises(common.ProtocolError):
            pull_block.parse_block(block_fixture(), 43)
        self.assertEqual(pull_block.parse_block(block_fixture(), 0)['height'], 42)

    def test_transaction_alignment_and_last_has_no_padding(self):
        tx1, tx2 = transaction_fixture(b'x'), transaction_fixture()
        result = pull_block.parse_block(block_fixture(transactions=(tx1, tx2)))
        self.assertEqual([tx['size'] for tx in result['transactions']], [161, 160])
        self.assertEqual(result['transactions'][0]['type'], 0x4154)

    def test_corrupt_transaction_and_padding(self):
        raw = block_fixture(transactions=(transaction_fixture(b'x'), transaction_fixture()))
        for offset, value in ((376, 0), (537, 1)):
            data = bytearray(raw)
            data[offset] = value
            with self.assertRaises(common.ProtocolError):
                pull_block.parse_block(bytes(data))
        raw = block_fixture(transactions=(transaction_fixture(b'x'),)) + bytes(7)
        data = bytearray(raw)
        struct.pack_into('<I', data, 0, len(data))
        with self.assertRaises(common.ProtocolError):
            pull_block.parse_block(bytes(data))

    def test_trailing_bytes_are_rejected(self):
        with self.assertRaises(common.ProtocolError):
            pull_block.parse_block(block_fixture() + b'trailing')

    def test_cli_requires_host(self):
        run = subprocess.run([sys.executable, str(ROOT/'pull_block.py')],
                             capture_output=True, text=True, timeout=5)
        self.assertEqual(run.returncode, 2)
        self.assertIn('host', run.stderr)


class CommonTests(unittest.TestCase):
    def test_size_cap_before_reading_body(self):
        for size in (0, 7, common.MAX_PACKET+1):
            stream = legacy.Stream(struct.pack('<II', size, 4) + b'body')
            with self.assertRaises(common.ProtocolError):
                common.read_packet(stream, 4, time.monotonic()+1)
            self.assertEqual(stream.data, b'body')

    def test_fragmented_packet_and_next_packet(self):
        data = common.packet(4, block_fixture())
        for chunk in (1, 3, 8, 55, len(data)):
            stream = legacy.Stream(data + b'next', chunk)
            self.assertEqual(common.read_packet(stream, 4, time.monotonic()+10), block_fixture())
            self.assertEqual(stream.data, b'next')

    def test_disconnect_wrong_type_and_empty_reply(self):
        with self.assertRaises(ConnectionError):
            common.read_packet(legacy.Stream(common.packet(4, b'abc')[:-1]), 4, time.monotonic()+1)
        with self.assertRaises(common.ProtocolError):
            common.read_packet(legacy.Stream(common.packet(5)), 4, time.monotonic()+1)
        self.assertEqual(common.read_packet(legacy.Stream(common.packet(4)), 4, time.monotonic()+1), b'')

    def test_write_deadline(self):
        sock = MagicMock()
        with self.assertRaises(TimeoutError):
            common.write_packet(sock, b'packet', time.monotonic()-1)
        sock.sendall.assert_not_called()


class BlockTLSTests(unittest.TestCase):
    setUpClass = classmethod(legacy.TLSTests.setUpClass.__func__)
    tearDownClass = classmethod(legacy.TLSTests.tearDownClass.__func__)
    context = legacy.TLSTests.context

    def serve_block(self, payload):
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
                            state['request'] = legacy.client.recv_exact(tls, 16, time.monotonic()+5)
                            response = common.packet(4, payload)
                            tls.sendall(response[:3])
                            tls.sendall(response[3:])
            except OSError as exc:
                state['error'] = str(exc)
        thread = threading.Thread(target=handle, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 6)
        return port, thread, state

    def test_block_tls_round_trip(self):
        port, thread, state = self.serve_block(block_fixture())
        result = pull_block.query('127.0.0.1', port, self.context(), 42)
        thread.join(6)
        self.assertEqual(result['height'], 42)
        self.assertEqual(state.get('request'), pull_block.make_request(42))
        self.assertNotIn('error', state)

    def test_block_cli_round_trip(self):
        port, thread, state = self.serve_block(block_fixture())
        cert = self.base / 'client/cert'
        run = subprocess.run([
            sys.executable, str(ROOT/'pull_block.py'), '127.0.0.1',
            '--port', str(port), '--height', '42',
            '--cert', str(cert/'node.full.crt.pem'), '--key', str(cert/'node.key.pem'),
        ], capture_output=True, text=True, timeout=15)
        thread.join(6)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout), pull_block.parse_block(block_fixture(), 42))
        self.assertEqual(state.get('request'), pull_block.make_request(42))
        self.assertNotIn('error', state)

    def test_empty_response_is_error(self):
        port, thread, state = self.serve_block(b'')
        with self.assertRaises(common.ProtocolError):
            pull_block.query('127.0.0.1', port, self.context(), 100)
        thread.join(6)
        self.assertNotIn('error', state)


if __name__ == "__main__":
    unittest.main()
