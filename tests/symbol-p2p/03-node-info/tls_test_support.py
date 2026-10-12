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

import node_info as client

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




class TLSTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = pathlib.Path(cls.temp.name)
        for name in ('client', 'server'):
            directory = cls.base / name
            directory.mkdir()
            subprocess.run(['bash', str(ROOT.parent / 'common/generate_certificates.sh'), str(directory / 'cert')],
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

    def context(self):
        cert = self.base / 'client/cert'
        return client.make_context(str(cert / 'node.full.crt.pem'), str(cert / 'node.key.pem'))





