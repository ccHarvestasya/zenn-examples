"""Read one Symbol Node_Discovery_Pull_Ping response (or an offline fixture)."""
import argparse
from dataclasses import dataclass
import json
import socket
import struct
import sys
import time

from chain_statistics import HEADER, ProtocolError, TIMEOUT, make_context, recv_exact

PULL_PING = 0x111
NODE_FIXED = struct.Struct("<II32s32sIHBBB")
MIN_PACKET_SIZE = HEADER.size + NODE_FIXED.size
MAX_PACKET_SIZE = MIN_PACKET_SIZE + 2 * 255

# Synthetic packet: test-network identifier, deliberately fictitious key/seed.
DEMO_PACKET = bytes.fromhex(
    "66000000 11010000 5e000000 04030201"
    "000102030405060708090a0b0c0d0e0f"
    "101112131415161718191a1b1c1d1e1f"
    "202122232425262728292a2b2c2d2e2f"
    "303132333435363738393a3b3c3d3e3f"
    "01000000 dc1e 98 09 04"
    "6c6f63616c686f7374 6e6f6465"
)


@dataclass(frozen=True)
class NodeInfo:
    size: int
    version: int
    identity_key: bytes
    generation_hash_seed: bytes
    roles: int
    port: int
    network_identifier: int
    host: bytes
    friendly_name: bytes

    def to_dict(self) -> dict:
        return {
            "node_size": self.size,
            "version": f"0x{self.version:08X}",
            "identity_key": self.identity_key.hex().upper(),
            "generation_hash_seed": self.generation_hash_seed.hex().upper(),
            "roles": f"0x{self.roles:08X}",
            "port": self.port,
            "network_identifier": f"0x{self.network_identifier:02X}",
            "host_size": len(self.host),
            "friendly_name_size": len(self.friendly_name),
            # UTF-8 is a display choice, not an assumption about the wire format.
            "host": self.host.decode("utf-8", errors="backslashreplace"),
            "friendly_name": self.friendly_name.decode("utf-8", errors="backslashreplace"),
            "host_hex": self.host.hex(),
            "friendly_name_hex": self.friendly_name.hex(),
        }


def make_request() -> bytes:
    return HEADER.pack(HEADER.size, PULL_PING)


def parse_header(header: bytes) -> int:
    if len(header) != HEADER.size:
        raise ProtocolError("ヘッダーは 8 バイト必要です")
    size, packet_type = HEADER.unpack(header)
    if packet_type != PULL_PING:
        raise ProtocolError(f"応答タイプが不正です: 0x{packet_type:X}")
    if not MIN_PACKET_SIZE <= size <= MAX_PACKET_SIZE:
        raise ProtocolError(f"Pull Ping 応答サイズが範囲外です: {size}")
    return size


def parse_payload(payload: bytes) -> NodeInfo:
    if len(payload) < NODE_FIXED.size:
        raise ProtocolError("NetworkNode の固定部が不足しています")
    size, version, key, seed, roles, port, network, host_size, name_size = (
        NODE_FIXED.unpack_from(payload)
    )
    expected = NODE_FIXED.size + host_size + name_size
    if size != expected or len(payload) != expected:
        raise ProtocolError(
            f"ノード長が一致しません: 宣言={size}, 実際={len(payload)}, 計算={expected}"
        )
    host_end = NODE_FIXED.size + host_size
    return NodeInfo(size, version, key, seed, roles, port, network,
                    payload[NODE_FIXED.size:host_end], payload[host_end:expected])


def parse_packet(packet: bytes) -> NodeInfo:
    size = parse_header(packet[:HEADER.size])
    if len(packet) != size:
        raise ProtocolError(f"パケット長が一致しません: 宣言={size}, 実際={len(packet)}")
    return parse_payload(packet[HEADER.size:])


def read_node_info(sock, deadline: float) -> NodeInfo:
    header = recv_exact(sock, HEADER.size, deadline)
    size = parse_header(header)
    payload = recv_exact(sock, size - HEADER.size, deadline)
    return parse_payload(payload)


def query(host: str, port: int, context) -> NodeInfo:
    with socket.create_connection((host, port), timeout=TIMEOUT) as tcp:
        with context.wrap_socket(tcp, server_hostname=host) as tls:
            deadline = time.monotonic() + TIMEOUT
            tls.settimeout(TIMEOUT)
            tls.sendall(make_request())
            return read_node_info(tls, deadline)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--demo", action="store_true", help="通信せず模擬パケットを解析")
    mode.add_argument("--host", help="接続先のホスト名または IP")
    parser.add_argument("--port", type=int, default=7900)
    parser.add_argument("--peer-ca")
    parser.add_argument("--cert", default="cert/node.full.crt.pem")
    parser.add_argument("--key", default="cert/node.key.pem")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port は 1〜65535 で指定してください")
    if args.host and not args.peer_ca:
        parser.error("接続には --peer-ca が必要です")
    try:
        if args.demo:
            result = parse_packet(DEMO_PACKET)
        else:
            context = make_context(args.peer_ca, args.cert, args.key)
            result = query(args.host, args.port, context)
    except (OSError, ValueError) as exc:
        print(f"取得・解析失敗: {exc}", file=sys.stderr)
        return 1
    # JSON escapes terminal control characters in untrusted node strings.
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
