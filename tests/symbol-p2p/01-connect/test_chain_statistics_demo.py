"""Validate the article's learning client against a local mutual-TLS server."""
import ssl
import subprocess
import sys
import unittest

import chain_statistics_demo as client
import tls_test_support as fixture

ROOT = fixture.ROOT


class DemoTLSTests(unittest.TestCase):
    serve = fixture.TLSTests.serve

    @classmethod
    def setUpClass(cls):
        fixture.TLSTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        fixture.TLSTests.tearDownClass.__func__(cls)

    def test_cli_round_trip_without_peer_ca(self):
        port, thread, state = self.serve()
        cert = self.base / 'client/cert'
        run = subprocess.run([
            sys.executable, str(ROOT / 'chain_statistics_demo.py'),
            '127.0.0.1', '--port', str(port),
            '--cert', str(cert / 'node.full.crt.pem'),
            '--key', str(cert / 'node.key.pem'),
        ], capture_output=True, text=True, timeout=15)
        thread.join(6)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout, 'chain height: 123\nfinalized height: 120\n'
                         'chain score: 18446744073709551618\n')
        self.assertEqual(state.get('request'), client.make_request())
        self.assertEqual(state.get('tls'), 'TLSv1.3')
        self.assertNotIn('error', state)

    def test_without_client_certificate_no_request_is_sent(self):
        port, thread, state = self.serve()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        with self.assertRaises(OSError):
            client.query('127.0.0.1', port, context)
        thread.join(6)
        self.assertNotIn('request', state)

    def test_missing_client_files_fail_before_connecting(self):
        run = subprocess.run([
            sys.executable, str(ROOT / 'chain_statistics_demo.py'),
            '127.0.0.1', '--cert', str(self.base / 'missing.pem'),
        ], capture_output=True, text=True, timeout=5)
        self.assertEqual(run.returncode, 1)
        self.assertIn('通信失敗:', run.stderr)
        self.assertEqual(run.stdout, '')


if __name__ == '__main__':
    unittest.main()
