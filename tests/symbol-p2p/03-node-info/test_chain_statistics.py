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
from unittest.mock import patch

import chain_statistics as client

# Explicit wire bytes, with nonzero high and low halves of the score.
FRAME = bytes.fromhex(
    '28000000 05000000'
    '7b00000000000000 7800000000000000'
    '0100000000000000 0200000000000000'
)
ROOT = pathlib.Path(__file__).resolve().parents[3] / "symbol-p2p" / pathlib.Path(__file__).resolve().parent.name


class Stream:
    def __init__(self, data, chunk_size=100):
        self.data = data
        self.chunk_size = chunk_size

    def settimeout(self, timeout):
        self.timeout = timeout

    def recv(self, size):
        size = min(size, self.chunk_size)
        result, self.data = self.data[:size], self.data[size:]
        return result


class PacketTests(unittest.TestCase):
    def read(self, stream):
        return client.read_statistics(stream, time.monotonic() + 10)

    def test_cli_missing_ca_returns_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            run = subprocess.run([
                sys.executable, str(ROOT / 'chain_statistics.py'), '127.0.0.1',
                '--peer-ca', str(pathlib.Path(directory) / 'missing.pem'),
            ], capture_output=True, text=True, timeout=5)
        self.assertEqual(run.returncode, 1)
        self.assertIn('通信失敗:', run.stderr)
        self.assertEqual(run.stdout, '')

    def test_cli_invalid_port(self):
        run = subprocess.run([
            sys.executable, str(ROOT / 'chain_statistics.py'), '127.0.0.1',
            '--peer-ca', 'unused.pem', '--port', '0',
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


class TLSTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = pathlib.Path(cls.temp.name)
        for name in ('client', 'server'):
            directory = cls.base / name
            directory.mkdir()
            subprocess.run(['bash', str(ROOT / 'generate_certificates.sh')],
                           cwd=directory, check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def serve(self):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.maximum_version = ssl.TLSVersion.TLSv1_3
        context.set_ecdh_curve('X25519')
        context.verify_mode = ssl.CERT_REQUIRED
        cert = self.base / 'server/cert'
        context.load_cert_chain(str(cert / 'node.full.crt.pem'), str(cert / 'node.key.pem'))
        context.load_verify_locations(str(self.base / 'client/cert/ca.crt.pem'))
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
                            state['tls'] = tls.version()
                            state['request'] = client.recv_exact(tls, 8, time.monotonic() + 5)
                            # Split both header and payload across writes.
                            for part in (FRAME[:3], FRAME[3:9], FRAME[9:]):
                                tls.sendall(part)
            except (OSError, ValueError) as exc:
                state['error'] = exc

        thread = threading.Thread(target=handle, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 6)
        return port, thread, state

    def context(self, trusted='server'):
        cert = self.base / 'client/cert'
        return client.make_context(str(self.base / trusted / 'cert/ca.crt.pem'),
                                   str(cert / 'node.full.crt.pem'), str(cert / 'node.key.pem'))

    def test_cli_authenticated_round_trip(self):
        port, thread, state = self.serve()
        cert = self.base / 'client/cert'
        run = subprocess.run([
            sys.executable, str(ROOT / 'chain_statistics.py'), '127.0.0.1', '--port', str(port),
            '--peer-ca', str(self.base / 'server/cert/ca.crt.pem'),
            '--cert', str(cert / 'node.full.crt.pem'), '--key', str(cert / 'node.key.pem'),
        ], capture_output=True, text=True, timeout=15)
        thread.join(6)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout, 'chain height: 123\nfinalized height: 120\n'
                         'chain score: 18446744073709551618\n')
        self.assertEqual(state.get('tls'), 'TLSv1.3')
        self.assertEqual(state.get('request'), client.make_request())
        self.assertNotIn('error', state)

    def test_wrong_peer_ca_rejected(self):
        port, thread, state = self.serve()
        with self.assertRaises(ssl.SSLCertVerificationError):
            client.query('127.0.0.1', port, self.context('client'))
        thread.join(6)
        self.assertNotIn('request', state)

    def test_no_client_certificate_rejected(self):
        port, thread, state = self.serve()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.load_verify_locations(str(self.base / 'server/cert/ca.crt.pem'))
        with self.assertRaises(OSError):
            client.query('127.0.0.1', port, context)
        thread.join(6)
        self.assertNotIn('request', state)


if __name__ == '__main__':
    unittest.main()
