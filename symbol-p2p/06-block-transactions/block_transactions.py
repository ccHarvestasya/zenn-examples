"""Fetch a Symbol block and inspect Transfer and Aggregate transactions."""
import argparse
import json
from pathlib import Path
import struct
import sys

from symbolchain import sc
from p2p_common import ProtocolError, exchange, make_context, packet

CERT_DIRECTORY = Path(__file__).resolve().parent.parent / "common" / "cert"
PULL_BLOCK = 4


def transaction_info(tx, embedded=False):
    result = {
        "type": f"0x{tx.type_.value:04X}", "type_name": tx.type_.name,
        "version": tx.version, "network": f"0x{tx.network.value:02X}",
        "signer": str(tx.signer_public_key), "size": tx.size,
    }
    if not embedded:
        result.update(max_fee_raw=tx.fee.value, deadline_raw=tx.deadline.value)
    if tx.type_ == sc.TransactionType.TRANSFER:
        message = tx.message
        result["transfer"] = {
            "recipient_unresolved_hex": str(tx.recipient_address),
            "mosaics": [
                {"unresolved_id": f"0x{mosaic.mosaic_id.value:016X}",
                 "amount_raw": mosaic.amount.value}
                for mosaic in tx.mosaics
            ],
            "message_hex": message.hex().upper(),
        }
        if message[:1] == b"\x00":
            result["transfer"]["plain_text"] = message[1:].decode(
                "utf-8", errors="backslashreplace")
    elif tx.type_ in (sc.TransactionType.AGGREGATE_COMPLETE,
                      sc.TransactionType.AGGREGATE_BONDED):
        result["aggregate"] = {
            "transactions_hash": str(tx.transactions_hash),
            "embedded": [transaction_info(inner, True) for inner in tx.transactions],
            "cosignatures_count": len(tx.cosignatures),
        }
    else:
        result["note"] = "このサンプルでは共通フィールドのみ表示"
    return result


def parse_block(raw: bytes, expected_height=None):
    try:
        block = sc.BlockFactory.deserialize(raw)
        if block.serialize() != raw or block.version != 1:
            raise ValueError("ブロックの長さ・形式・バージョンが不正です")
    except (AssertionError, IndexError, KeyError, ValueError) as exc:
        raise ProtocolError(f"SDK でブロックを解析できません: {exc}") from exc
    if expected_height not in (None, 0, block.height.value):
        raise ProtocolError("要求した高さと応答の高さが一致しません")
    return {
        "height": block.height.value, "block_type": block.type_.name,
        "network": f"0x{block.network.value:02X}",
        "transactions": [transaction_info(tx) for tx in block.transactions],
    }


def make_request(height):
    if not 0 <= height <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError("height は uint64 の範囲で指定してください")
    return packet(PULL_BLOCK, struct.pack("<Q", height))


def query(host, port, context, height):
    raw = exchange(host, port, context, make_request(height), PULL_BLOCK)
    if not raw:
        raise ProtocolError("空の応答です。要求した高さが保管範囲外の可能性があります")
    return parse_block(raw, height)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="接続先のホスト名または IP")
    parser.add_argument("--height", type=int, default=0, help="0 は接続先の最新高")
    parser.add_argument("--port", type=int, default=7900)
    parser.add_argument("--cert", default=str(CERT_DIRECTORY / "node.full.crt.pem"))
    parser.add_argument("--key", default=str(CERT_DIRECTORY / "node.key.pem"))
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port は 1〜65535 で指定してください")
    try:
        make_request(args.height)
        context = make_context(args.cert, args.key)
        result = query(args.host, args.port, context, args.height)
    except (OSError, ValueError) as exc:
        print(f"取得・解析失敗: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
