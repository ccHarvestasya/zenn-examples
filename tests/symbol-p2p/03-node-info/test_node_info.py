import json
import pathlib
import struct
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

import node_info as node
import tls_test_support as legacy

ROOT = pathlib.Path(__file__).resolve().parents[3] / "symbol-p2p" / pathlib.Path(__file__).resolve().parent.name


def replace_u32(packet, offset, value):
    changed = bytearray(packet)
    struct.pack_into('<I', changed, offset, value)
    return bytes(changed)


def fixture(host=b'', name=b''):
    # Keep the independently written fixed bytes; edit lengths for edge cases.
    fixed = bytearray(node.DEMO_PACKET[8:89])
    struct.pack_into('<I', fixed, 0, 81 + len(host) + len(name))
    fixed[79] = len(host)
    fixed[80] = len(name)
    payload = bytes(fixed) + host + name
    return struct.pack('<II', 8 + len(payload), 0x111) + payload


class NodeInfoTests(unittest.TestCase):
    def test_wire_request(self):
        self.assertEqual(node.make_request(), bytes.fromhex('0800000011010000'))

    def test_struct_sizes(self):
        self.assertEqual(node.HEADER.size, 8)
        self.assertEqual(node.NODE_FIXED.size, 81)
        self.assertEqual(node.MAX_PACKET_SIZE, 599)

    def test_fixed_fixture_fields_and_endian(self):
        result = node.parse_packet(node.DEMO_PACKET)
        self.assertEqual(result.size, 94)
        self.assertEqual(result.version, 0x01020304)
        self.assertEqual(result.identity_key, bytes(range(32)))
        self.assertEqual(result.generation_hash_seed, bytes(range(32, 64)))
        self.assertEqual((result.roles, result.port, result.network_identifier), (1, 7900, 0x98))
        self.assertEqual((result.host, result.friendly_name), (b'localhost', b'node'))

    def test_version_components(self):
        for value, text in ((0x01020304, '1.2.3.4'), (0, '0.0.0.0'),
                            (0xffffffff, '255.255.255.255')):
            result = node.parse_packet(replace_u32(node.DEMO_PACKET, 12, value))
            self.assertEqual(result.version_text, text)

    def test_roles_combined_and_unknown(self):
        for value, names in ((0, ['None']), (7, ['Peer', 'API', 'Voting']),
                             (0xC1, ['Peer', 'IPv4', 'IPv6']),
                             (9, ['Peer', 'Unknown(0x8)'])):
            result = node.parse_packet(replace_u32(node.DEMO_PACKET, 80, value))
            self.assertEqual(result.role_names, names)
            self.assertEqual(result.roles, value)

    def test_network_display_keeps_raw_identifier(self):
        for value, label in ((0x68, 'Mainnet'), (0x98, 'Testnet'), (0xA8, 'Unknown')):
            packet = bytearray(node.DEMO_PACKET)
            packet[86] = value
            result = node.parse_packet(bytes(packet))
            self.assertEqual(result.to_dict()['network_name'], label)
            self.assertEqual(result.network_identifier, value)

    def test_short_headers(self):
        for size in range(8):
            with self.subTest(size=size), self.assertRaises(node.ProtocolError):
                node.parse_header(node.DEMO_PACKET[:size])

    def test_header_requires_exact_size(self):
        with self.assertRaises(node.ProtocolError):
            node.parse_header(node.DEMO_PACKET[:9])

    def test_wrong_packet_type(self):
        with self.assertRaises(node.ProtocolError):
            node.parse_packet(replace_u32(node.DEMO_PACKET, 4, 5))

    def test_response_size_limits(self):
        for size in (0, 7, 8, 88, 600, 0xffffffff):
            stream = legacy.Stream(struct.pack('<II', size, 0x111) + b'body')
            with self.subTest(size=size), self.assertRaises(node.ProtocolError):
                node.read_node_info(stream, time.monotonic() + 10)
            self.assertEqual(stream.data, b'body')

    def test_all_truncated_complete_packets(self):
        for size in range(len(node.DEMO_PACKET)):
            with self.subTest(size=size), self.assertRaises(node.ProtocolError):
                node.parse_packet(node.DEMO_PACKET[:size])

    def test_short_payloads(self):
        for size in range(81):
            with self.subTest(size=size), self.assertRaises(node.ProtocolError):
                node.parse_payload(node.DEMO_PACKET[8:8+size])

    def test_wrong_outer_size_and_extra_data(self):
        for packet in (replace_u32(node.DEMO_PACKET, 0, 101), node.DEMO_PACKET + b'extra'):
            with self.assertRaises(node.ProtocolError):
                node.parse_packet(packet)

    def test_wrong_entity_sizes(self):
        for size in (0, 80, 93, 95, 0xffffffff):
            with self.subTest(size=size), self.assertRaises(node.ProtocolError):
                node.parse_packet(replace_u32(node.DEMO_PACKET, 8, size))

    def test_variable_field_lengths(self):
        for offset in (87, 88):
            for size in (0, 1, 255):
                packet = bytearray(node.DEMO_PACKET)
                packet[offset] = size
                with self.subTest(offset=offset, size=size), self.assertRaises(node.ProtocolError):
                    node.parse_packet(bytes(packet))

    def test_entity_cannot_hide_trailing_bytes(self):
        packet = replace_u32(node.DEMO_PACKET + b'extra', 0, 107)
        with self.assertRaises(node.ProtocolError):
            node.parse_packet(packet)

    def test_empty_and_maximum_variable_fields(self):
        for host, name in ((b'', b''), (b'a'*255, b'b'*255), (b'abc', b''), (b'', b'abc')):
            with self.subTest(host_size=len(host), name_size=len(name)):
                result = node.parse_packet(fixture(host, name))
                self.assertEqual((result.host, result.friendly_name), (host, name))

    def test_byte_lengths_and_non_utf8_bytes_are_preserved(self):
        for name in ('ノード'.encode(), b'\xff\x00\x1b[31m'):
            result = node.parse_packet(fixture(b'localhost', name))
            self.assertEqual(result.friendly_name, name)
            encoded = json.dumps(result.to_dict(), ensure_ascii=True)
            self.assertNotIn('\x1b', encoded)
            self.assertEqual(result.to_dict()['friendly_name_hex'], name.hex())

    def test_all_stream_fragment_sizes_leave_next_packet(self):
        for size in range(1, len(node.DEMO_PACKET)+1):
            stream = legacy.Stream(node.DEMO_PACKET + b'next', size)
            self.assertEqual(node.read_node_info(stream, time.monotonic()+10),
                             node.parse_packet(node.DEMO_PACKET))
            self.assertEqual(stream.data, b'next')

    def test_all_stream_truncations(self):
        for size in range(len(node.DEMO_PACKET)):
            with self.subTest(size=size), self.assertRaises(ConnectionError):
                node.read_node_info(legacy.Stream(node.DEMO_PACKET[:size]), time.monotonic()+10)

    def test_deadline_expires_between_header_and_payload(self):
        with patch.object(legacy.client.time, 'monotonic', side_effect=[0, 1.1]):
            with self.assertRaises(TimeoutError):
                node.read_node_info(legacy.Stream(node.DEMO_PACKET), 1.0)

    def test_demo_cli(self):
        run = subprocess.run([sys.executable, str(ROOT/'node_info.py'), '--demo'],
                             capture_output=True, text=True, timeout=5)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout), node.parse_packet(node.DEMO_PACKET).to_dict())

    def test_network_cli_requires_peer_ca(self):
        run = subprocess.run([sys.executable, str(ROOT/'node_info.py'), '--host', 'localhost'],
                             capture_output=True, text=True, timeout=5)
        self.assertEqual(run.returncode, 2)
        self.assertIn('--peer-ca', run.stderr)


class NodeInfoTLSTests(unittest.TestCase):
    # Reuse the existing test certificate setup and loopback TLS server.
    setUpClass = classmethod(legacy.TLSTests.setUpClass.__func__)
    tearDownClass = classmethod(legacy.TLSTests.tearDownClass.__func__)
    serve = legacy.TLSTests.serve
    context = legacy.TLSTests.context

    def test_node_info_cli_tls_round_trip(self):
        with patch.object(legacy, 'FRAME', node.DEMO_PACKET):
            port, thread, state = self.serve()
            cert = self.base / 'client/cert'
            run = subprocess.run([
                sys.executable, str(ROOT / 'node_info.py'), '--host', '127.0.0.1',
                '--port', str(port), '--peer-ca', str(self.base / 'server/cert/ca.crt.pem'),
                '--cert', str(cert / 'node.full.crt.pem'), '--key', str(cert / 'node.key.pem'),
            ], capture_output=True, text=True, timeout=15)
            thread.join(6)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout), node.parse_packet(node.DEMO_PACKET).to_dict())
        self.assertEqual(state.get('request'), node.make_request())
        self.assertNotIn('error', state)

    def test_node_info_tls_round_trip(self):
        with patch.object(legacy, 'FRAME', node.DEMO_PACKET):
            port, thread, state = self.serve()
            result = node.query('127.0.0.1', port, self.context())
            thread.join(6)
        self.assertEqual(result, node.parse_packet(node.DEMO_PACKET))
        self.assertEqual(state.get('request'), node.make_request())
        self.assertEqual(state.get('tls'), 'TLSv1.3')
        self.assertNotIn('error', state)


if __name__ == '__main__':
    unittest.main()
