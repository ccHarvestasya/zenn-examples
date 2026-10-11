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


if __name__ == "__main__":
    unittest.main()
