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

import capture_lab
from fixture_data import block_fixture, transaction_fixture
import p2p_common as common
import pull_block
import push_transaction
import test_chain_statistics as legacy

ROOT = pathlib.Path(__file__).resolve().parent


class BlockTests(unittest.TestCase):
    def test_request_height_and_endian(self):
        self.assertEqual(pull_block.make_request(42), bytes.fromhex('10000000040000002a00000000000000'))
        for height in (-1, 2**64):
            with self.assertRaises(ValueError):
                pull_block.make_request(height)

    def test_layout_and_hash_golden(self):
        result = pull_block.parse_block(block_fixture(), 42)
        self.assertEqual(result['height'], 42)
        self.assertEqual(result['timestamp_ms_since_network_epoch'], 123456)
        self.assertEqual(result['signer'], '22'*32)
        self.assertEqual(result['previous_block_hash'], '33'*32)
        self.assertEqual(result['computed_hash'],
                         'AA463BC7FDEA3F718E9D708B747A37C214F339D52BEE9AFCF52C80A0CEA70278')

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

    def test_header_hash_not_full_body_hash(self):
        first = block_fixture(transactions=(transaction_fixture(b'a'),))
        second = block_fixture(transactions=(transaction_fixture(b'b'),))
        self.assertEqual(pull_block.parse_block(first)['computed_hash'],
                         pull_block.parse_block(second)['computed_hash'])
        # This is why reading/computing a hash is not transaction Merkle validation.

    def test_block_cli_offline(self):
        with tempfile.TemporaryDirectory() as work:
            path = pathlib.Path(work) / 'block.bin'
            path.write_bytes(block_fixture())
            run = subprocess.run([sys.executable, str(ROOT/'pull_block.py'), '--file', str(path)],
                                 capture_output=True, text=True, timeout=5)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)['height'], 42)


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


class PushTests(unittest.TestCase):
    def test_push_wire_bytes(self):
        tx = transaction_fixture()
        self.assertEqual(push_transaction.make_request(tx), bytes.fromhex('a800000009000000') + tx)

    def test_invalid_payloads(self):
        for tx in (b'', transaction_fixture()[:-1], bytes(160)):
            with self.assertRaises(common.ProtocolError):
                push_transaction.make_request(tx)
        for start, size in ((8, 64), (72, 32)):
            data = bytearray(transaction_fixture())
            data[start:start+size] = bytes(size)
            with self.assertRaises(common.ProtocolError):
                push_transaction.make_request(bytes(data))

    def test_dry_run_never_connects(self):
        with tempfile.TemporaryDirectory() as work:
            path = pathlib.Path(work) / 'tx.hex'
            path.write_text(transaction_fixture().hex())
            with patch.object(sys, 'argv', ['push_transaction.py', str(path)]), \
                 patch.object(push_transaction, 'connection') as connect, \
                 patch.object(push_transaction, 'make_context') as context:
                self.assertEqual(push_transaction.main(), 0)
                connect.assert_not_called()
                context.assert_not_called()

    def test_explicit_flags_and_loopback_guard(self):
        with patch.object(push_transaction, 'connection') as connect:
            for flags in ({}, {'enabled': True}, {'private_network': True}):
                with self.assertRaises(ValueError):
                    push_transaction.send_transaction(transaction_fixture(), '127.0.0.1', 7900, None, **flags)
            for host in ('192.168.1.1', '8.8.8.8', 'localhost'):
                with self.assertRaises(ValueError):
                    push_transaction.send_transaction(transaction_fixture(), host, 7900, None,
                                                       enabled=True, private_network=True)
            connect.assert_not_called()

    def test_mainnet_refused(self):
        tx = bytearray(transaction_fixture())
        tx[109] = 0x68
        with patch.object(push_transaction, 'connection') as connect:
            with self.assertRaises(ValueError):
                push_transaction.send_transaction(bytes(tx), '127.0.0.1', 7900, None,
                                                   enabled=True, private_network=True)
            connect.assert_not_called()

    def test_send_branch_uses_only_in_memory_mock_no_ack(self):
        tls = MagicMock()
        with patch.object(push_transaction, 'connection') as connect:
            connect.return_value.__enter__.return_value = (tls, time.monotonic()+10)
            push_transaction.send_transaction(transaction_fixture(), '127.0.0.1', 7900, None,
                                               enabled=True, private_network=True)
        tls.sendall.assert_called_once_with(push_transaction.make_request(transaction_fixture()))
        tls.recv.assert_not_called()
        # No socket/TLS server is used and no transaction is actually transmitted.


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

    def test_empty_response_is_error(self):
        port, thread, state = self.serve_block(b'')
        with self.assertRaises(common.ProtocolError):
            pull_block.query('127.0.0.1', port, self.context(), 100)
        thread.join(6)
        self.assertNotIn('error', state)


class CaptureTests(unittest.TestCase):
    def test_keylog_new_file_permissions_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as work:
            path = pathlib.Path(work)/'secret.keylog'
            capture_lab.reserve_keylog(str(path))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                capture_lab.reserve_keylog(str(path))

    def test_owned_lab_with_and_without_keylog(self):
        with tempfile.TemporaryDirectory() as work:
            path = pathlib.Path(work)/'secret.keylog'
            first = capture_lab.run_lab(0)
            second = capture_lab.run_lab(0, str(path))
            self.assertFalse(first['keylog_enabled'])
            self.assertTrue(second['keylog_enabled'])
            self.assertEqual(second['tls'], 'TLSv1.3')
            self.assertEqual(second['request_hex'], '0800000011010000')
            self.assertEqual(second['response_size'], 102)
            self.assertGreater(path.stat().st_size, 0)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            # Do not print/read keys into test logs.


if __name__ == '__main__':
    unittest.main()
