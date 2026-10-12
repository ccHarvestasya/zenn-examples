"""Read Catapult Finalization Statistics and Proof over P2P (not a verifier)."""
import argparse
from pathlib import Path
import json
import struct
import sys

from p2p_common import ProtocolError, exchange, make_context, packet

CERT_DIRECTORY = Path(__file__).resolve().parent.parent / "common" / "cert"

STATISTICS = 0x132
PROOF_AT_EPOCH = 0x133
PROOF_AT_HEIGHT = 0x134
PROOF_RESPONSE = 0x135
STAT_FIELDS = struct.Struct('<IIQ32s')
PROOF_HEADER = struct.Struct('<IIIIQ32s')
GROUP_HEADER = struct.Struct('<IIIIQ')
SIGNATURE_SIZE = 192  # Two (32-byte public key + 64-byte signature) pairs.
MAX_PROOF_PACKET = 1024 * 1024  # Example's cap, not a protocol limit.


def make_request(kind: str, value: int | None = None) -> tuple[bytes, int, int]:
    if kind == 'stats':
        return packet(STATISTICS), STATISTICS, 8 + STAT_FIELDS.size
    if kind == 'height' and value is not None and 1 <= value < 2**64:
        return packet(PROOF_AT_HEIGHT, struct.pack('<Q', value)), PROOF_RESPONSE, MAX_PROOF_PACKET
    if kind == 'epoch' and value is not None and 1 <= value < 2**32:
        return packet(PROOF_AT_EPOCH, struct.pack('<I', value)), PROOF_RESPONSE, MAX_PROOF_PACKET
    raise ValueError('不正な要求種別または値です')


def parse_statistics(data: bytes) -> dict:
    if len(data) != STAT_FIELDS.size:
        raise ProtocolError('統計応答は48バイトの本文が必要です')
    epoch, point, height, block_hash = STAT_FIELDS.unpack(data)
    return {'epoch': epoch, 'point': point, 'height': height, 'hash': block_hash.hex().upper()}


def parse_proof(data: bytes) -> dict | None:
    if not data:
        return None  # Empty Pull_Finalization_Proof response: no proof found.
    if len(data) < PROOF_HEADER.size:
        raise ProtocolError('Proof ヘッダーが不足しています')
    size, version, epoch, point, height, block_hash = PROOF_HEADER.unpack_from(data)
    if size != len(data) or version != 1:
        raise ProtocolError('Proof サイズまたは対応バージョンが不正です')
    result = {'version': version, 'epoch': epoch, 'point': point,
              'height': height, 'hash': block_hash.hex().upper(), 'groups': []}
    cursor = PROOF_HEADER.size
    while cursor < len(data):
        remaining = len(data) - cursor
        if remaining < GROUP_HEADER.size:
            raise ProtocolError('MessageGroup ヘッダーが途中で切れています')
        group_size, hash_count, signature_count, stage, first_height = GROUP_HEADER.unpack_from(data, cursor)
        expected = GROUP_HEADER.size + 32 * hash_count + SIGNATURE_SIZE * signature_count
        if stage not in (0, 1) or group_size != expected or group_size > remaining:
            raise ProtocolError('MessageGroup のサイズまたはステージが不正です')
        hash_start = cursor + GROUP_HEADER.size
        hashes = [data[hash_start + i * 32:hash_start + (i + 1) * 32].hex().upper()
                  for i in range(hash_count)]
        result['groups'].append({'stage': 'prevote' if stage == 0 else 'precommit',
                                 'height': first_height, 'hashes': hashes,
                                 'signatures_count': signature_count})
        cursor += group_size
    return result


def query(host, port, context, kind, value=None):
    request, expected_type, cap = make_request(kind, value)
    data = exchange(host, port, context, request, expected_type, cap)
    result = parse_statistics(data) if kind == 'stats' else parse_proof(data)
    if result is not None and kind in ('height', 'epoch') and result[kind] != value:
        raise ProtocolError('要求した高さまたはエポックと Proof が一致しません')
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--proof-height', type=int, help='指定高の Finalization Proof')
    mode.add_argument('--proof-epoch', type=int, help='指定 epoch の Finalization Proof')
    parser.add_argument('host', help='接続先のホスト名または IP')
    parser.add_argument('--port', type=int, default=7900)
    parser.add_argument('--cert', default=str(CERT_DIRECTORY / "node.full.crt.pem"))
    parser.add_argument('--key', default=str(CERT_DIRECTORY / "node.key.pem"))
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port は1〜65535を指定してください')
    try:
        kind = ('height' if args.proof_height is not None
                else 'epoch' if args.proof_epoch is not None else 'stats')
        value = args.proof_height if kind == 'height' else args.proof_epoch
        make_request(kind, value)
        context = make_context(args.cert, args.key)
        result = query(args.host, args.port, context, kind, value)
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 0
    except (OSError, ValueError) as exc:
        print(f'取得・解析失敗: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
