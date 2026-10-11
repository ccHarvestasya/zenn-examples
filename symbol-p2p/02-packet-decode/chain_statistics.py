"""Query one Symbol Chain_Statistics packet over authenticated TLS."""
import argparse
from pathlib import Path
from dataclasses import dataclass
import socket
import ssl
import struct
import sys
import time

CERT_DIRECTORY = Path(__file__).resolve().parent.parent / "common" / "cert"

HEADER = struct.Struct("<II")
STATISTICS = struct.Struct("<QQQQ")
CHAIN_STATISTICS = 5
RESPONSE_SIZE = HEADER.size + STATISTICS.size
TIMEOUT = 10.0


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class ChainStatistics:
    height: int
    finalized_height: int
    score_high: int
    score_low: int

    @property
    def score(self) -> int:
        return (self.score_high << 64) | self.score_low


def make_request() -> bytes:
    return HEADER.pack(HEADER.size, CHAIN_STATISTICS)


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


def read_statistics(sock, deadline: float) -> ChainStatistics:
    size, packet_type = HEADER.unpack(recv_exact(sock, HEADER.size, deadline))
    # This example accepts only the fixed-size Chain_Statistics response.
    if size != RESPONSE_SIZE:
        raise ProtocolError(f"応答サイズが不正です: {size} (期待値 {RESPONSE_SIZE})")
    if packet_type != CHAIN_STATISTICS:
        raise ProtocolError(f"応答タイプが不正です: {packet_type} (期待値 5)")
    payload = recv_exact(sock, STATISTICS.size, deadline)
    return ChainStatistics(*STATISTICS.unpack(payload))


def make_context(peer_ca: str, cert: str, key: str) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    # Identity is bound to the pre-trusted peer CA, not to a DNS name.
    context.check_hostname = False
    context.verify_mode = ssl.CERT_REQUIRED
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.maximum_version = ssl.TLSVersion.TLSv1_3
    context.set_ecdh_curve("X25519")
    context.load_verify_locations(cafile=peer_ca)
    context.load_cert_chain(certfile=cert, keyfile=key)
    return context


def query(host: str, port: int, context: ssl.SSLContext) -> ChainStatistics:
    with socket.create_connection((host, port), timeout=TIMEOUT) as tcp:
        with context.wrap_socket(tcp, server_hostname=host) as tls:
            # The TLS handshake is complete before any application packet is sent.
            deadline = time.monotonic() + TIMEOUT
            tls.settimeout(TIMEOUT)
            tls.sendall(make_request())
            return read_statistics(tls, deadline)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host")
    parser.add_argument("--port", type=int, default=7900)
    parser.add_argument("--peer-ca", required=True)
    parser.add_argument("--cert", default=str(CERT_DIRECTORY / "node.full.crt.pem"))
    parser.add_argument("--key", default=str(CERT_DIRECTORY / "node.key.pem"))
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port は 1〜65535 で指定してください")
    try:
        context = make_context(args.peer_ca, args.cert, args.key)
        result = query(args.host, args.port, context)
    except (OSError, ValueError) as exc:
        print(f"通信失敗: {exc}", file=sys.stderr)
        return 1
    print(f"chain height: {result.height}")
    print(f"finalized height: {result.finalized_height}")
    print(f"chain score: {result.score}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
