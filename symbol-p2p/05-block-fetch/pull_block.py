"""Fetch/decode one block. Computed hash is not proof of block validity."""
import argparse
from pathlib import Path
import hashlib
import json
import struct
import sys

from entities import entity_header, transaction_header
from p2p_common import ProtocolError, exchange, make_context, packet

CERT_DIRECTORY = Path(__file__).resolve().parent.parent / "common" / "cert"

PULL_BLOCK = 4
HEADER_SIZES = {0x8043: 424, 0x8143: 376, 0x8243: 424}


def make_request(height: int) -> bytes:
    if not 0 <= height <= 0xffffffffffffffff:
        raise ValueError('height は uint64 の範囲で指定してください')
    return packet(PULL_BLOCK, struct.pack('<Q', height))


def parse_block(data: bytes, expected_height=None) -> dict:
    result = entity_header(data)
    header_size = HEADER_SIZES.get(result['type'])
    if header_size is None or len(data) < header_size or result['version'] != 1:
        raise ProtocolError('未対応のブロック種別・バージョン、またはヘッダー不足です')
    height, timestamp, difficulty = struct.unpack_from('<QQQ', data, 112)
    if expected_height not in (None, 0, height):
        raise ProtocolError('要求した高さと応答の高さが一致しません')
    # Normal block's four-byte padding is excluded from its hash data buffer.
    hash_end = 372 if result['type'] == 0x8143 else 424
    if result['type'] == 0x8143 and data[372:376] != bytes(4):
        raise ProtocolError('通常ブロックの予約領域が不正です')
    block_hash = hashlib.sha3_256(data[8:104] + data[108:hash_end]).hexdigest().upper()
    transactions = []
    offset = header_size
    while offset < len(data):
        if len(data) - offset < 4:
            raise ProtocolError('トランザクション長が不足しています')
        size = struct.unpack_from('<I', data, offset)[0]
        if size < 128 or size > len(data) - offset:
            raise ProtocolError('トランザクション境界が不正です')
        transactions.append(transaction_header(data[offset:offset + size]))
        offset += size
        if offset < len(data):
            padding = (-size) % 8
            if len(data) - offset <= padding or any(data[offset:offset + padding]):
                raise ProtocolError('中間パディングまたは次のトランザクションが不正です')
            offset += padding
    result.update(height=height, timestamp_ms_since_network_epoch=timestamp,
                  difficulty=difficulty, computed_hash=block_hash,
                  previous_block_hash=data[216:248].hex().upper(),
                  transactions_hash=data[248:280].hex().upper(),
                  transactions=transactions)
    return result


def query(host, port, context, height):
    payload = exchange(host, port, context, make_request(height), PULL_BLOCK)
    if not payload:
        raise ProtocolError('空の応答です。要求した高さが保管範囲外の可能性があります')
    return parse_block(payload, height)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--height', type=int, default=0, help='0 は接続先の最新高')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--file', help='オフラインのブロック本体バイナリ')
    mode.add_argument('--host')
    parser.add_argument('--port', type=int, default=7900)
    parser.add_argument('--peer-ca')
    parser.add_argument('--cert', default=str(CERT_DIRECTORY / "node.full.crt.pem"))
    parser.add_argument('--key', default=str(CERT_DIRECTORY / "node.key.pem"))
    args = parser.parse_args()
    if args.host and not args.peer_ca:
        parser.error('--peer-ca が必要です')
    try:
        make_request(args.height)
        if args.file:
            from pathlib import Path
            from p2p_common import MAX_PACKET
            with Path(args.file).open('rb') as source:
                data = source.read(MAX_PACKET + 1)
            if len(data) > MAX_PACKET:
                raise ProtocolError('入力ファイルがクライアントの上限を超えています')
            result = parse_block(data, args.height)
        else:
            context = make_context(args.peer_ca, args.cert, args.key)
            result = query(args.host, args.port, context, args.height)
    except (OSError, ValueError) as exc:
        print(f'取得・解析失敗: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
