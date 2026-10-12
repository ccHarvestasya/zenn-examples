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

from symbolchain import sc
import block_transactions as sample
import p2p_common as common
from fixture_data import block_fixture, transaction_fixture, demo_block
import tls_test_support as legacy

ROOT = pathlib.Path(__file__).resolve().parents[3] / "symbol-p2p" / pathlib.Path(__file__).resolve().parent.name


class TransactionTests(unittest.TestCase):
    def test_transfer_fields(self):
        tx = sample.parse_block(demo_block())["transactions"][0]
        self.assertEqual(tx["type_name"], "TRANSFER")
        self.assertEqual(tx["transfer"]["plain_text"], "hello")
        self.assertEqual(tx["transfer"]["recipient_unresolved_hex"], "33" * 24)
        self.assertEqual(tx["max_fee_raw"], 0)

    def test_aggregate_and_embedded_fields(self):
        agg = sample.parse_block(demo_block())["transactions"][1]["aggregate"]
        self.assertEqual(agg["cosignatures_count"], 1)
        inner = agg["embedded"][0]
        self.assertEqual(inner["transfer"]["plain_text"], "hello")
        self.assertNotIn("max_fee_raw", inner)
        self.assertNotIn("deadline_raw", inner)

    def test_mosaic_raw_values(self):
        tx = sc.TransferTransactionV1()
        mosaic = sc.UnresolvedMosaic()
        mosaic.mosaic_id = sc.UnresolvedMosaicId(0x8000000000000123)
        mosaic.amount = sc.Amount(123456789)
        tx.mosaics = [mosaic]
        result = sample.transaction_info(tx)["transfer"]["mosaics"]
        self.assertEqual(result, [{"unresolved_id": "0x8000000000000123", "amount_raw": 123456789}])

    def test_message_bytes_are_preserved(self):
        tx = sc.TransferTransactionV1()
        for message in (b"", b"\1cipher", b"\0a\xff\x1b"):
            tx.message = message
            result = sample.transaction_info(tx)["transfer"]
            self.assertEqual(result["message_hex"], message.hex().upper())
            self.assertEqual("plain_text" in result, message[:1] == b"\0")
        self.assertIn("\\xff", result["plain_text"])
        self.assertIn("\\u001b", json.dumps(result, ensure_ascii=True))

    def test_other_transaction_common_fields(self):
        result = sample.transaction_info(sc.AccountKeyLinkTransactionV1())
        self.assertIn("note", result)
        self.assertNotIn("transfer", result)

    def test_aggregate_versions_and_bonded(self):
        for cls in (sc.AggregateCompleteTransactionV1, sc.AggregateCompleteTransactionV2,
                    sc.AggregateCompleteTransactionV3, sc.AggregateBondedTransactionV3):
            self.assertEqual(sample.transaction_info(cls())["aggregate"]["embedded"], [])

    def test_empty_block_and_three_types(self):
        for kind in (0x8043, 0x8143, 0x8243):
            self.assertEqual(sample.parse_block(block_fixture(kind))["transactions"], [])

    def test_header_truncation_and_trailing_data(self):
        raw = demo_block()
        for length in range(376):
            with self.subTest(length=length), self.assertRaises(common.ProtocolError):
                sample.parse_block(raw[:length])
        with self.assertRaises(common.ProtocolError):
            sample.parse_block(raw + b"extra")

    def test_corrupt_lengths_and_padding(self):
        raw = demo_block()
        for offset in (0, 4, 376, 543, 544, 704):
            changed = bytearray(raw)
            changed[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(common.ProtocolError):
                sample.parse_block(bytes(changed))

    def test_requested_height(self):
        self.assertEqual(sample.parse_block(demo_block(), 0)["height"], 42)
        with self.assertRaises(common.ProtocolError):
            sample.parse_block(demo_block(), 43)

    def test_wire_request(self):
        self.assertEqual(sample.make_request(42), bytes.fromhex("10000000040000002a00000000000000"))
        for height in (-1, 2**64):
            with self.assertRaises(ValueError):
                sample.make_request(height)

    def test_cli_requires_host(self):
        run = subprocess.run([sys.executable, str(ROOT / "block_transactions.py")], capture_output=True, text=True)
        self.assertEqual(run.returncode, 2)


class TransactionTLSTests(unittest.TestCase):
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

    def test_tls_round_trip(self):
        port, thread, state = self.serve_block(demo_block())
        result = sample.query("127.0.0.1", port, self.context(), 42)
        thread.join(6)
        self.assertEqual(result, sample.parse_block(demo_block()))
        self.assertEqual(state.get("request"), sample.make_request(42))
        self.assertNotIn("error", state)

    def test_cli_round_trip(self):
        port, thread, state = self.serve_block(demo_block())
        cert = self.base / "client/cert"
        run = subprocess.run([
            sys.executable, str(ROOT / "block_transactions.py"), "127.0.0.1",
            "--port", str(port), "--height", "42",
            "--cert", str(cert / "node.full.crt.pem"), "--key", str(cert / "node.key.pem"),
        ], capture_output=True, text=True, timeout=15)
        thread.join(6)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout), sample.parse_block(demo_block()))
        self.assertNotIn("error", state)

    def test_empty_reply(self):
        port, thread, state = self.serve_block(b"")
        with self.assertRaises(common.ProtocolError):
            sample.query("127.0.0.1", port, self.context(), 42)
        thread.join(6)
        self.assertNotIn("error", state)


if __name__ == "__main__":
    unittest.main()
