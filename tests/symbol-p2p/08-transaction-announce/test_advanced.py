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
import push_transaction
from prepare_transfer import create_transfer
import tls_test_support as legacy

ROOT = pathlib.Path(__file__).resolve().parents[3] / "symbol-p2p" / pathlib.Path(__file__).resolve().parent.name

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
    def setUp(self):
        self.transaction = create_transfer().serialize()

    def test_push_wire_bytes(self):
        self.assertEqual(push_transaction.make_request(self.transaction),
                         bytes.fromhex('bb00000009000000') + self.transaction)

    def test_invalid_payloads(self):
        for tx in (b'', self.transaction[:-1], self.transaction + b'x', transaction_fixture()):
            with self.assertRaises(common.ProtocolError):
                push_transaction.make_request(tx)

    def test_signature_tampering(self):
        for offset in (8, 72, 112, 178):
            data = bytearray(self.transaction)
            data[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(common.ProtocolError):
                push_transaction.make_request(bytes(data))

    def test_dry_run_never_connects(self):
        with tempfile.TemporaryDirectory() as work:
            path = pathlib.Path(work) / 'tx.hex'
            path.write_text(self.transaction.hex())
            with patch.object(sys, 'argv', ['push_transaction.py', 'testnet1.symbol-mikun.net', str(path)]), \
                 patch.object(push_transaction, 'connection') as connect, \
                 patch.object(push_transaction, 'make_context') as context:
                self.assertEqual(push_transaction.main(), 0)
                connect.assert_not_called()
                context.assert_not_called()

    def test_explicit_send_flag(self):
        with patch.object(push_transaction, 'connection') as connect:
            with self.assertRaises(ValueError):
                push_transaction.send_transaction(self.transaction, 'host', 7900, None)
            connect.assert_not_called()

    def test_non_testnet_refused(self):
        for network in (0x68, 0x60):
            tx = bytearray(self.transaction)
            tx[109] = network
            with patch.object(push_transaction, 'connection') as connect:
                with self.assertRaises(common.ProtocolError):
                    push_transaction.send_transaction(bytes(tx), 'host', 7900, None, enabled=True)
                connect.assert_not_called()

    def test_send_has_no_ack(self):
        tls = MagicMock()
        with patch.object(push_transaction, 'connection') as connect:
            connect.return_value.__enter__.return_value = (tls, time.monotonic()+10)
            push_transaction.send_transaction(self.transaction, 'host', 7900, None, enabled=True)
        tls.sendall.assert_called_once_with(push_transaction.make_request(self.transaction))
        tls.recv.assert_not_called()

    def test_cli_uses_ascii_hex_file(self):
        with tempfile.TemporaryDirectory() as work:
            path = pathlib.Path(work) / 'tx.hex'
            path.write_text(self.transaction.hex())
            run = subprocess.run([sys.executable, str(ROOT/'push_transaction.py'),
                                  'testnet1.symbol-mikun.net', str(path)],
                                 capture_output=True, text=True, timeout=5)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)['sent'], False)
        self.assertTrue(json.loads(run.stdout)['signature_valid'])


class PushTLSTests(unittest.TestCase):
    setUpClass = classmethod(legacy.TLSTests.setUpClass.__func__)
    tearDownClass = classmethod(legacy.TLSTests.tearDownClass.__func__)
    context = legacy.TLSTests.context

    def test_cli_sends_one_packet_without_waiting_for_ack(self):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        cert = self.base / 'server/cert'
        context.load_cert_chain(str(cert/'node.full.crt.pem'), str(cert/'node.key.pem'))
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(str(self.base/'client/cert/ca.crt.pem'))
        state = {}
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        listener.settimeout(5)
        def handle():
            try:
                with listener:
                    tcp, _ = listener.accept()
                    with tcp:
                        tcp.settimeout(5)
                        with context.wrap_socket(tcp, server_side=True) as tls:
                            header = common.recv_exact(tls, 8, time.monotonic()+5)
                            size, kind = common.HEADER.unpack(header)
                            state['type'] = kind
                            state['payload'] = common.recv_exact(tls, size-8, time.monotonic()+5)
                            # No response is written. Client must finish without an acknowledgement.
            except OSError as exc:
                state['error'] = str(exc)
        port = listener.getsockname()[1]
        thread = threading.Thread(target=handle, daemon=True)
        thread.start()
        tx = create_transfer().serialize()
        cert = self.base / 'client/cert'
        with tempfile.TemporaryDirectory() as work:
            path = pathlib.Path(work)/'tx.hex'
            path.write_text(tx.hex())
            run = subprocess.run([
                sys.executable, str(ROOT/'push_transaction.py'), '127.0.0.1', str(path), '--send',
                '--port', str(port), '--cert', str(cert/'node.full.crt.pem'), '--key', str(cert/'node.key.pem'),
            ], capture_output=True, text=True, timeout=15)
        thread.join(6)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(state.get('type'), 9)
        self.assertEqual(state.get('payload'), tx)
        self.assertNotIn('error', state)
        self.assertTrue(json.loads(run.stdout)['sent'])


if __name__ == "__main__":
    unittest.main()
