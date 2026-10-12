import json
import pathlib
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import capture_peer as sample
from node_fixture import NODE_PACKET
import tls_test_support as support


class KeylogTests(unittest.TestCase):
    def test_new_file_permissions_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as work:
            path = pathlib.Path(work)/'secret.keylog'
            sample.reserve_keylog(path)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                sample.reserve_keylog(path)

    def test_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as work:
            target = pathlib.Path(work)/'target'
            target.write_text('keep')
            link = pathlib.Path(work)/'link'
            link.symlink_to(target)
            with self.assertRaises(OSError):
                sample.reserve_keylog(link)
            self.assertEqual(target.read_text(), 'keep')

    def test_fragmented_reads(self):
        stream = support.Stream(NODE_PACKET + b'next', 1)
        self.assertEqual(sample.recv_exact(stream, len(NODE_PACKET), time.monotonic()+1), NODE_PACKET)
        self.assertEqual(stream.data, b'next')

    def test_truncated_stream(self):
        with self.assertRaises(ConnectionError):
            sample.recv_exact(support.Stream(b'x'), 2, time.monotonic()+1)

    def test_cli_requires_host(self):
        run = subprocess.run([sys.executable, str(support.ROOT/'capture_peer.py')],
                             capture_output=True, text=True, timeout=5)
        self.assertEqual(run.returncode, 2)


class CaptureTLSTests(unittest.TestCase):
    setUpClass = classmethod(support.TLSTests.setUpClass.__func__)
    tearDownClass = classmethod(support.TLSTests.tearDownClass.__func__)
    serve = support.TLSTests.serve

    def query(self, port, keylog=None):
        cert = self.base/'client/cert'
        return sample.query('127.0.0.1', port,
                            str(cert/'node.full.crt.pem'), str(cert/'node.key.pem'), keylog)

    def test_with_and_without_keylog(self):
        with tempfile.TemporaryDirectory() as work:
            path = pathlib.Path(work)/'secret.keylog'
            for keylog in (None, path):
                with patch.object(support, 'FRAME', NODE_PACKET):
                    port, thread, state = self.serve()
                    result = self.query(port, keylog)
                    thread.join(6)
                self.assertEqual(result['tls'], 'TLSv1.3')
                self.assertEqual(result['request_hex'], '08 00 00 00 11 01 00 00')
                self.assertEqual(result['response_size'], 102)
                self.assertEqual(result['node_size'], 94)
                self.assertEqual(result['keylog_enabled'], keylog is not None)
                self.assertNotIn('error', state)
            self.assertGreater(path.stat().st_size, 0)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_bad_response_type_and_size(self):
        for header in (struct.pack('<II', 102, 5), struct.pack('<II', 600, 0x111)):
            with patch.object(support, 'FRAME', header):
                port, thread, state = self.serve()
                with self.assertRaises(ValueError):
                    self.query(port)
                thread.join(6)

    def test_mismatched_node_size(self):
        data = bytearray(NODE_PACKET)
        struct.pack_into('<I', data, 8, 93)
        with patch.object(support, 'FRAME', bytes(data)):
            port, thread, state = self.serve()
            with self.assertRaises(ValueError):
                self.query(port)
            thread.join(6)

    def test_cli_records_connection_metadata(self):
        with patch.object(support, 'FRAME', NODE_PACKET):
            port, thread, state = self.serve()
            cert = self.base/'client/cert'
            run = subprocess.run([
                sys.executable, str(support.ROOT/'capture_peer.py'), '127.0.0.1',
                '--port', str(port), '--cert', str(cert/'node.full.crt.pem'),
                '--key', str(cert/'node.key.pem'),
            ], capture_output=True, text=True, timeout=15)
            thread.join(6)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)['response_header_hex'], '66 00 00 00 11 01 00 00')
        self.assertNotIn('error', state)


if __name__ == '__main__':
    unittest.main()
