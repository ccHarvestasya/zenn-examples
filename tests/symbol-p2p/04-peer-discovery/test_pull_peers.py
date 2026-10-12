import json
import struct
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

import pull_peers as client
from node_fixture import NODE_PACKET
import tls_test_support as support


NODE = NODE_PACKET[8:]


def frame(body=b'', packet_type=0x113):
    return struct.pack('<II', 8 + len(body), packet_type) + body


class PeerTests(unittest.TestCase):
    def test_request_bytes(self):
        self.assertEqual(client.make_request(), bytes.fromhex('0800000013010000'))

    def test_empty_response(self):
        self.assertEqual(client.parse_packet(frame()), [])

    def test_multiple_variable_length_nodes(self):
        # The second record has empty host/name and therefore a different size.
        second = bytearray(NODE[:81])
        struct.pack_into('<I', second, 0, 81)
        second[79:81] = b'\0\0'
        peers = client.parse_packet(frame(NODE + second))
        self.assertEqual(len(peers), 2)
        self.assertEqual((peers[0].host, peers[0].port), (b'localhost', 7900))
        self.assertEqual((peers[1].size, peers[1].host), (81, b''))

    def test_short_headers(self):
        for size in range(8):
            with self.subTest(size=size), self.assertRaises(client.ProtocolError):
                client.parse_packet(frame()[:size])

    def test_wrong_type(self):
        with self.assertRaises(client.ProtocolError):
            client.parse_packet(frame(NODE, 0x111))

    def test_packet_length_mismatch(self):
        for packet in (frame(NODE)[:-1], frame(NODE) + b'x'):
            with self.subTest(packet=packet), self.assertRaises(client.ProtocolError):
                client.parse_packet(packet)

    def test_packet_size_limits_before_body_read(self):
        for size in (0, 7, client.MAX_PACKET_SIZE + 1):
            stream = support.Stream(struct.pack('<II', size, 0x113) + b'unchanged')
            with self.subTest(size=size), self.assertRaises(client.ProtocolError):
                client.read_peers(stream, time.monotonic() + 1)
            self.assertEqual(stream.data, b'unchanged')

    def test_invalid_record_sizes(self):
        for size in (0, 80, 95, 592, 0xFFFFFFFF):
            node = bytearray(NODE)
            struct.pack_into('<I', node, 0, size)
            with self.subTest(size=size), self.assertRaises(client.ProtocolError):
                client.parse_packet(frame(node))

    def test_string_lengths_must_match_record(self):
        node = bytearray(NODE)
        node[79] += 1
        with self.assertRaises(client.ProtocolError):
            client.parse_packet(frame(node))

    def test_trailing_partial_size(self):
        for count in (1, 2, 3):
            with self.subTest(count=count), self.assertRaises(client.ProtocolError):
                client.parse_packet(frame(NODE + b'x' * count))

    def test_split_reads_leave_next_packet(self):
        packet = frame(NODE + NODE)
        expected = client.parse_packet(packet)
        for chunk_size in range(1, len(packet) + 1):
            stream = support.Stream(packet + b'next', chunk_size)
            self.assertEqual(client.read_peers(stream, time.monotonic() + 1), expected)
            self.assertEqual(stream.data, b'next')

    def test_every_truncation_is_an_error(self):
        packet = frame(NODE)
        for size in range(len(packet)):
            with self.subTest(size=size), self.assertRaises(ConnectionError):
                client.read_peers(support.Stream(packet[:size]), time.monotonic() + 1)

    def test_deadline_expires_between_header_and_body(self):
        with patch('node_info.time.monotonic', side_effect=[0.0, 2.0]):
            with self.assertRaises(TimeoutError):
                client.read_peers(support.Stream(frame(NODE)), 1.0)

    def test_cli_requires_host(self):
        run = subprocess.run([sys.executable, str(support.ROOT / 'pull_peers.py')],
                             capture_output=True, text=True, timeout=5)
        self.assertEqual(run.returncode, 2)
        self.assertIn('host', run.stderr)


class PeerTLSTests(unittest.TestCase):
    setUpClass = classmethod(support.TLSTests.setUpClass.__func__)
    tearDownClass = classmethod(support.TLSTests.tearDownClass.__func__)
    serve = support.TLSTests.serve
    context = support.TLSTests.context

    def test_tls_round_trip(self):
        packet = frame(NODE + NODE)
        with patch.object(support, 'FRAME', packet):
            port, thread, state = self.serve()
            context = self.context()
            self.assertFalse(context.check_hostname)
            self.assertEqual(context.verify_mode, 0)
            result = client.query('127.0.0.1', port, context)
            thread.join(6)
        self.assertEqual(result, client.parse_packet(packet))
        self.assertEqual(state.get('request'), bytes.fromhex('0800000013010000'))
        self.assertEqual(state.get('tls'), 'TLSv1.3')
        self.assertNotIn('error', state)

    def test_cli_round_trip(self):
        with patch.object(support, 'FRAME', frame(NODE)):
            port, thread, state = self.serve()
            cert = self.base / 'client/cert'
            run = subprocess.run([
                sys.executable, str(support.ROOT / 'pull_peers.py'), '127.0.0.1',
                '--port', str(port), '--cert', str(cert / 'node.full.crt.pem'),
                '--key', str(cert / 'node.key.pem'),
            ], capture_output=True, text=True, timeout=15)
            thread.join(6)
        self.assertEqual(run.returncode, 0, run.stderr)
        lines = run.stdout.splitlines()
        self.assertEqual(lines[0], 'peer candidates: 1')
        self.assertEqual(json.loads(lines[1]), {
            'host': 'localhost', 'port': 7900, 'roles': ['Peer'],
            'network': 'Testnet', 'key_prefix': '0001020304050607',
        })
        self.assertEqual(state.get('request'), bytes.fromhex('0800000013010000'))
        self.assertNotIn('error', state)


if __name__ == '__main__':
    unittest.main()
