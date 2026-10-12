"""Read Symbol Node_Discovery_Pull_Peers without REST."""
import argparse
from pathlib import Path
import json
import socket
import struct
import sys
import time

from node_info import HEADER, NODE_FIXED, ProtocolError, TIMEOUT, make_context, parse_payload, recv_exact

CERT_DIRECTORY = Path(__file__).resolve().parent.parent / "common" / "cert"

PULL_PEERS = 0x113
MIN_NODE_SIZE = NODE_FIXED.size
MAX_NODE_SIZE = MIN_NODE_SIZE + 2 * 255
MAX_PACKET_SIZE = 256 * 1024  # Client limit, not a Catapult protocol limit.


def make_request() -> bytes:
    return HEADER.pack(HEADER.size, PULL_PEERS)


def parse_packet(packet: bytes) -> list:
    if len(packet) < HEADER.size:
        raise ProtocolError("ヘッダーが不足しています")

    total, packet_type = HEADER.unpack_from(packet)
    if packet_type != PULL_PEERS:
        raise ProtocolError(f"応答のタイプが違います: 0x{packet_type:X}")
    if not HEADER.size <= total <= MAX_PACKET_SIZE:
        raise ProtocolError(f"パケットサイズが不正です: {total}")
    if len(packet) != total:
        raise ProtocolError("パケットの宣言長と受信長が違います")

    payload = memoryview(packet)[HEADER.size:]
    pos = 0
    peers = []
    while pos < len(payload):
        remaining = len(payload) - pos
        if remaining < 4:
            raise ProtocolError("NetworkNode.Size が読み取れません")
        (size,) = struct.unpack_from("<I", payload, pos)
        if not MIN_NODE_SIZE <= size <= MAX_NODE_SIZE:
            raise ProtocolError(f"不正な NetworkNode.Size: {size}")
        if size > remaining:
            raise ProtocolError("NetworkNode が本文の末尾を超えています")
        peers.append(parse_payload(payload[pos:pos + size].tobytes()))
        pos += size

    return peers


def read_peers(sock, deadline: float) -> list:
    header = recv_exact(sock, HEADER.size, deadline)
    total, packet_type = HEADER.unpack(header)
    if packet_type != PULL_PEERS:
        raise ProtocolError(f"想定外の応答タイプ: 0x{packet_type:X}")
    if not HEADER.size <= total <= MAX_PACKET_SIZE:
        raise ProtocolError(f"応答サイズが範囲外です: {total}")
    body = recv_exact(sock, total - HEADER.size, deadline)
    return parse_packet(header + body)


def query(host: str, port: int, context) -> list:
    with socket.create_connection((host, port), timeout=TIMEOUT) as tcp:
        with context.wrap_socket(tcp, server_hostname=host) as tls:
            tls.settimeout(TIMEOUT)
            deadline = time.monotonic() + TIMEOUT
            tls.sendall(make_request())
            return read_peers(tls, deadline)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="接続先のホスト名または IP")
    parser.add_argument("--port", type=int, default=7900)
    parser.add_argument("--cert", default=str(CERT_DIRECTORY / "node.full.crt.pem"))
    parser.add_argument("--key", default=str(CERT_DIRECTORY / "node.key.pem"))
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port は 1〜65535 で指定してください")

    try:
        context = make_context(args.cert, args.key)
        peers = query(args.host, args.port, context)
    except (OSError, ValueError) as exc:
        print(f"取得失敗: {exc}", file=sys.stderr)
        return 1

    print(f"peer candidates: {len(peers)}")
    for peer in peers:
        info = peer.to_dict()
        summary = {
            "host": info["host"],
            "port": peer.port,
            "roles": info["role_names"],
            "network": info["network_name"],
            "key_prefix": info["identity_key"][:16],
        }
        print(json.dumps(summary, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
