"""One owned loopback TLS exchange; optional secret logging for local inspection."""
import argparse
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time

from chain_statistics import HEADER, make_context, recv_exact
import node_info

ROOT = Path(__file__).resolve().parent


def reserve_keylog(path: str):
    # New file only, no symlink following; do not log keys by default.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.close(fd)


def run_lab(port: int, keylog=None) -> dict:
    if not 0 <= port <= 65535:
        raise ValueError('port は 0〜65535 で指定してください。0 は自動割当です')
    with tempfile.TemporaryDirectory() as work:
        directory = Path(work)
        for name in ('client', 'server'):
            path = directory / name
            path.mkdir()
            subprocess.run(['bash', str(ROOT.parent / 'common/generate_certificates.sh'), str(path / 'cert')],
                           cwd=path, check=True, capture_output=True)
        client_cert = directory / 'client/cert'
        server_cert = directory / 'server/cert'
        context = make_context(str(server_cert / 'ca.crt.pem'),
                               str(client_cert / 'node.full.crt.pem'),
                               str(client_cert / 'node.key.pem'))
        if keylog:
            reserve_keylog(keylog)
            context.keylog_filename = keylog
        server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server.minimum_version = ssl.TLSVersion.TLSv1_3
        server.maximum_version = ssl.TLSVersion.TLSv1_3
        server.load_cert_chain(str(server_cert / 'node.full.crt.pem'),
                               str(server_cert / 'node.key.pem'))
        server.verify_mode = ssl.CERT_REQUIRED
        server.load_verify_locations(str(client_cert / 'ca.crt.pem'))
        listener = socket.socket()
        listener.bind(('127.0.0.1', port))
        listener.listen(1)
        port = listener.getsockname()[1]
        listener.settimeout(10)
        state = {}

        def respond():
            try:
                with listener:
                    tcp, _ = listener.accept()
                    with tcp:
                        tcp.settimeout(10)
                        with server.wrap_socket(tcp, server_side=True) as tls:
                            request = recv_exact(tls, HEADER.size, time.monotonic() + 10)
                            if request != node_info.make_request():
                                raise ValueError('予期しない要求です')
                            state.update(tls=tls.version(), request_hex=request.hex())
                            for part in (node_info.DEMO_PACKET[:3], node_info.DEMO_PACKET[3:]):
                                tls.sendall(part)
            except (OSError, ValueError) as exc:
                state['error'] = str(exc)

        thread = threading.Thread(target=respond, daemon=True)
        thread.start()
        try:
            result = node_info.query('127.0.0.1', port, context)
        finally:
            thread.join(12)
        if thread.is_alive() or 'error' in state:
            raise RuntimeError(f'模擬サーバーが完了しませんでした: {state.get("error")}')
        return dict(state, response_size=len(node_info.DEMO_PACKET),
                    friendly_name=result.to_dict()['friendly_name'], keylog_enabled=bool(keylog))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=37900)
    parser.add_argument('--keylog', help='新しい秘密ログのパス。自分の模擬通信だけに使用')
    args = parser.parse_args()
    try:
        result = run_lab(args.port, args.keylog)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f'検証通信失敗: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
