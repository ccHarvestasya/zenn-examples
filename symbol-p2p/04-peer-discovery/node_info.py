"""TLS helpers and NetworkNode decoding for the peer discovery example."""
from dataclasses import dataclass
import ssl
import struct
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
