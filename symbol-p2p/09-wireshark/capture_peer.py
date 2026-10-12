"""Query a Testnet node and optionally log this client's TLS session secrets."""
import argparse
import json
import os
from pathlib import Path
import socket
import ssl
import struct
import sys
import time

CERT_DIRECTORY = Path(__file__).resolve().parent.parent / "common" / "cert"
HEADER = struct.Struct('<II')
TIMEOUT = 10.0
PULL_PING = 0x111


def recv_exact(sock, size: int, deadline: float) -> bytes:
    data = bytearray()
    while len(data) < size:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("応答全体の受信がタイムアウトしました")
        sock.settimeout(remaining)
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError(f"受信途中で切断されました: {len(data)}/{size} bytes")
        data.extend(chunk)
    return bytes(data)


def make_context(cert: str, key: str) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    # Learning example only: the peer certificate is NOT verified.
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.maximum_version = ssl.TLSVersion.TLSv1_3
    context.set_ecdh_curve("X25519")
    context.load_cert_chain(certfile=cert, keyfile=key)
    return context


def reserve_keylog(path):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.close(fd)


def query(host, port, cert, key, keylog=None):
    context = make_context(cert, key)
    if keylog:
        reserve_keylog(keylog)
        context.keylog_filename = str(keylog)
    request = HEADER.pack(HEADER.size, PULL_PING)
    with socket.create_connection((host, port), timeout=TIMEOUT) as tcp:
        with context.wrap_socket(tcp, server_hostname=host) as tls:
            deadline = time.monotonic() + TIMEOUT
            tls.sendall(request)
            header = recv_exact(tls, HEADER.size, deadline)
            size, packet_type = HEADER.unpack(header)
            if packet_type != PULL_PING or not 89 <= size <= 599:
                raise ValueError('Pull Ping の応答ヘッダーが不正です')
            body = recv_exact(tls, size - HEADER.size, deadline)
            node_size = struct.unpack_from('<I', body)[0]
            if node_size != len(body):
                raise ValueError('NetworkNode.Size が応答本文の長さと一致しません')
            return {
                'tls': tls.version(), 'cipher': tls.cipher()[0],
                'request_hex': request.hex(' '),
                'response_header_hex': header.hex(' '),
                'response_size': size, 'node_size': node_size,
                'keylog_enabled': keylog is not None,
            }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('host', help='接続先のホスト名または IP')
    parser.add_argument('--port', type=int, default=7900)
    parser.add_argument('--cert', default=str(CERT_DIRECTORY / 'node.full.crt.pem'))
    parser.add_argument('--key', default=str(CERT_DIRECTORY / 'node.key.pem'))
    parser.add_argument('--keylog', help='この接続のセッション鍵を保存する新しいファイル')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port は 1〜65535 で指定してください')
    try:
        result = query(args.host, args.port, args.cert, args.key, args.keylog)
    except (OSError, ValueError) as exc:
        print(f'取得・記録失敗: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
