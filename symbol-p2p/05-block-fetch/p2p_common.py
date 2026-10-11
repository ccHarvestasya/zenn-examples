"""Bounded one-shot P2P I/O; uses this lesson's TLS setup."""
from contextlib import contextmanager
import socket
import time

from chain_statistics import HEADER, ProtocolError, TIMEOUT, make_context, recv_exact

MAX_PACKET = 8 * 1024 * 1024  # Local client policy, not a protocol limit.


def packet(packet_type: int, payload: bytes = b'') -> bytes:
    size = HEADER.size + len(payload)
    if not 0 <= packet_type <= 0xffffffff or size > MAX_PACKET:
        raise ProtocolError('パケットのタイプまたはサイズが範囲外です')
    return HEADER.pack(size, packet_type) + payload


def read_packet(sock, expected_type: int, deadline: float, max_size=MAX_PACKET) -> bytes:
    size, packet_type = HEADER.unpack(recv_exact(sock, HEADER.size, deadline))
    if packet_type != expected_type or not HEADER.size <= size <= max_size:
        raise ProtocolError(f'応答ヘッダーが不正です: size={size}, type={packet_type}')
    return recv_exact(sock, size - HEADER.size, deadline)


def write_packet(sock, data: bytes, deadline: float) -> None:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('送信期限を超えました')
    sock.settimeout(remaining)
    sock.sendall(data)


@contextmanager
def connection(host: str, port: int, context):
    if not 1 <= port <= 65535:
        raise ValueError('port は 1〜65535 で指定してください')
    with socket.create_connection((host, port), timeout=TIMEOUT) as tcp:
        with context.wrap_socket(tcp, server_hostname=host) as tls:
            yield tls, time.monotonic() + TIMEOUT


def exchange(host, port, context, request, expected_type, max_size=MAX_PACKET):
    with connection(host, port, context) as (tls, deadline):
        write_packet(tls, request, deadline)
        return read_packet(tls, expected_type, deadline, max_size)
