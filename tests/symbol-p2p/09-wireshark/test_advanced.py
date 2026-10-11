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

ROOT = pathlib.Path(__file__).resolve().parents[3] / "symbol-p2p" / pathlib.Path(__file__).resolve().parent.name

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


if __name__ == "__main__":
    unittest.main()
