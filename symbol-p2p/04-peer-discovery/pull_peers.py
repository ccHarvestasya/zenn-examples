"""Read Symbol Node_Discovery_Pull_Peers without REST."""
import argparse
from pathlib import Path
import json
import socket
import ssl
from dataclasses import dataclass
import struct
import sys
import time

HEADER = struct.Struct("<II")
TIMEOUT = 10.0


class ProtocolError(ValueError):
    pass


NODE_FIXED = struct.Struct("<II32s32sIHBBB")


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

    @property
    def version_text(self) -> str:
        return ".".join(str((self.version >> shift) & 255) for shift in (24, 16, 8, 0))

    @property
    def role_names(self) -> list[str]:
        known = {1: "Peer", 2: "API", 4: "Voting", 0x40: "IPv4", 0x80: "IPv6"}
        names = [name for bit, name in known.items() if self.roles & bit]
        unknown = self.roles & ~0xC7
        if unknown:
            names.append(f"Unknown(0x{unknown:X})")
        return names or ["None"]

    def to_dict(self) -> dict:
        return {
            "node_size": self.size,
            "version": f"0x{self.version:08X}",
            "version_text": self.version_text,
            "identity_key": self.identity_key.hex().upper(),
            "generation_hash_seed": self.generation_hash_seed.hex().upper(),
            "roles": f"0x{self.roles:08X}",
            "role_names": self.role_names,
            "port": self.port,
            "network_identifier": f"0x{self.network_identifier:02X}",
            "network_name": {0x68: "Mainnet", 0x98: "Testnet"}.get(
                self.network_identifier, "Unknown"),
            "host_size": len(self.host),
            "friendly_name_size": len(self.friendly_name),
            # UTF-8 is a display choice, not an assumption about the wire format.
            "host": self.host.decode("utf-8", errors="backslashreplace"),
            "friendly_name": self.friendly_name.decode("utf-8", errors="backslashreplace"),
            "host_hex": self.host.hex(),
            "friendly_name_hex": self.friendly_name.hex(),
        }


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
