"""Fetch a block over P2P and deserialize it with the Symbol SDK."""
import argparse
from pathlib import Path
import json
import struct
import sys

from symbolchain import sc
from p2p_common import ProtocolError, exchange, make_context, packet

CERT_DIRECTORY = Path(__file__).resolve().parent.parent / "common" / "cert"

PULL_BLOCK = 4


def make_request(height: int) -> bytes:
    if not 0 <= height <= 0xffffffffffffffff:
        raise ValueError('height は uint64 の範囲で指定してください')
    return packet(PULL_BLOCK, struct.pack('<Q', height))


def parse_block(data: bytes, expected_height=None) -> dict:
    try:
        block = sc.BlockFactory.deserialize(data)
        # Reject truncated data, trailing bytes and noncanonical encodings.
        if block.serialize() != data or block.version != 1:
            raise ValueError('ブロックの長さ・形式・バージョンが不正です')
    except (AssertionError, IndexError, KeyError, ValueError) as exc:
        raise ProtocolError(f'SDK でブロックを解析できません: {exc}') from exc
    if expected_height not in (None, 0, block.height.value):
        raise ProtocolError('要求した高さと応答の高さが一致しません')
    return {
        'size': block.size,
        'version': block.version,
        'network': block.network.value,
        'type': block.type_.value,
        'type_name': block.type_.name,
        'signature': str(block.signature),
        'signer': str(block.signer_public_key),
        'height': block.height.value,
        'timestamp_ms_since_network_epoch': block.timestamp.value,
        'difficulty': block.difficulty.value,
        'previous_block_hash': str(block.previous_block_hash),
        'transactions_hash': str(block.transactions_hash),
        'transactions': [
            {'size': tx.size, 'type': tx.type_.value, 'type_name': tx.type_.name,
             'signer': str(tx.signer_public_key),
             'max_fee': tx.fee.value, 'deadline': tx.deadline.value}
            for tx in block.transactions
        ],
    }


def query(host, port, context, height):
    payload = exchange(host, port, context, make_request(height), PULL_BLOCK)
    if not payload:
        raise ProtocolError('空の応答です。要求した高さが保管範囲外の可能性があります')
    return parse_block(payload, height)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--height', type=int, default=0, help='0 は接続先の最新高')
    parser.add_argument('host', help='接続先のホスト名または IP')
    parser.add_argument('--port', type=int, default=7900)
    parser.add_argument('--cert', default=str(CERT_DIRECTORY / "node.full.crt.pem"))
    parser.add_argument('--key', default=str(CERT_DIRECTORY / "node.key.pem"))
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port は 1〜65535 で指定してください')
    try:
        make_request(args.height)
        context = make_context(args.cert, args.key)
        result = query(args.host, args.port, context, args.height)
    except (OSError, ValueError) as exc:
        print(f'取得・解析失敗: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
