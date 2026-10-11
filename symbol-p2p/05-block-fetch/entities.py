"""Decode common entity fields only; no signature or plugin validation."""
import struct
from chain_statistics import ProtocolError

ENTITY = struct.Struct('<II64s32sIBBH')
TX_HEADER_SIZE = 128


def entity_header(data: bytes) -> dict:
    if len(data) < ENTITY.size:
        raise ProtocolError('エンティティの共通ヘッダーが不足しています')
    size, reserved1, signature, signer, reserved2, version, network, kind = ENTITY.unpack_from(data)
    if size != len(data) or reserved1 or reserved2:
        raise ProtocolError('エンティティの長さまたは予約領域が不正です')
    return dict(size=size, version=version, network=network, type=kind,
                signature=signature.hex().upper(), signer=signer.hex().upper())


def transaction_header(data: bytes) -> dict:
    result = entity_header(data)
    if len(data) < TX_HEADER_SIZE or result['type'] >> 14 != 1:
        raise ProtocolError('通常トランザクションの共通形式ではありません')
    fee, deadline = struct.unpack_from('<QQ', data, 112)
    return dict(result, max_fee=fee, deadline=deadline,
                type_specific_bytes=len(data) - TX_HEADER_SIZE)
