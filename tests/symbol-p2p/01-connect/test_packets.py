import struct
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
import chain_statistics_demo as client
from tls_test_support import Stream, FRAME, ROOT

class PacketTests(unittest.TestCase):
    def read(self, stream):
        return client.read_statistics(stream, time.monotonic() + 10)

    def test_cli_invalid_port(self):
        run = subprocess.run([
            sys.executable, str(ROOT / 'chain_statistics_demo.py'), '127.0.0.1',
            '--port', '0',
        ], capture_output=True, text=True, timeout=5)
        self.assertEqual(run.returncode, 2)
        self.assertIn('port は', run.stderr)

    def test_request_wire_bytes(self):
        self.assertEqual(client.make_request(), bytes.fromhex('0800000005000000'))

    def test_all_fragment_sizes_and_coalesced_next_packet(self):
        for chunk_size in range(1, len(FRAME) + 1):
            with self.subTest(chunk_size=chunk_size):
                stream = Stream(FRAME + b'next packet', chunk_size)
                result = self.read(stream)
                self.assertEqual((result.height, result.finalized_height), (123, 120))
                self.assertEqual(result.score, 18446744073709551618)
                self.assertEqual(stream.data, b'next packet')

    def test_all_truncated_frames(self):
        for size in range(len(FRAME)):
            with self.subTest(size=size), self.assertRaises(ConnectionError):
                self.read(Stream(FRAME[:size]))

    def test_invalid_sizes_rejected_before_payload(self):
        for size in (0, 7, 8, 39, 41, 0xffffffff):
            stream = Stream(struct.pack('<II', size, 5) + b'body')
            with self.subTest(size=size), self.assertRaises(client.ProtocolError):
                self.read(stream)
            self.assertEqual(stream.data, b'body')

    def test_wrong_type(self):
        with self.assertRaises(client.ProtocolError):
            self.read(Stream(struct.pack('<II', 40, 0x132)))

    def test_uint64_boundaries(self):
        stream = Stream(struct.pack('<IIQQQQ', 40, 5, 0, 0, 2**64-1, 2**64-1))
        self.assertEqual(self.read(stream).score, 2**128-1)

    def test_socket_timeout_propagates(self):
        stream = Stream(FRAME)
        with patch.object(stream, 'recv', side_effect=TimeoutError('socket timeout')):
            with self.assertRaises(TimeoutError):
                self.read(stream)

    def test_deadline_not_reset_by_fragments(self):
        with patch.object(client.time, 'monotonic', side_effect=[0, 0.4, 0.8, 1.2]):
            with self.assertRaises(TimeoutError):
                client.recv_exact(Stream(b'abcd', 1), 4, 1.0)

