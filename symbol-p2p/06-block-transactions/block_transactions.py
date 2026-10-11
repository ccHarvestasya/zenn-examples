"""Decode Symbol block transaction layouts (offline; not a verifier)."""
import argparse
import json
from pathlib import Path
import struct

from fixture_data import block_fixture, transaction_fixture

BLOCK_HEAD = {0x8043: 424, 0x8143: 376, 0x8243: 424}
TRANSFER = 0x4154
AGGREGATES = {0x4141, 0x4241}
MAX_FILE = 8 * 1024 * 1024  # This reader's limit, not a protocol limit.


def invalid(message):
    raise ValueError(message)


def records(payload: bytes, minimum: int, pad_last: bool):
    """Split size-prefixed entities; embedded payload pads even the last."""
    offset = 0
    while offset < len(payload):
        remaining = len(payload) - offset
        if remaining < 4:
            invalid("Size フィールドが途中で切れています")
        (size,) = struct.unpack_from("<I", payload, offset)
        if not minimum <= size <= remaining:
            invalid("エンティティの Size が不正です")
        end = offset + size
        yield payload[offset:end]
        padding = (-size) % 8
        if end == len(payload) and not pad_last:
            offset = end
            continue
        if end + padding > len(payload) or any(payload[end:end + padding]):
            invalid("8バイト境界のパディングが不正です")
        offset = end + padding
        if not pad_last and offset == len(payload):
            invalid("ブロックの最後の取引にパディングがあります")


def transfer(tx: bytes, embedded: bool):
    base = 48 if embedded else 128
    if len(tx) < base + 32:
        invalid("Transfer の固定部が不足しています")
    recipient = tx[base:base + 24]
    message_size, count = struct.unpack_from("<HB", tx, base + 24)
    if any(tx[base + 27:base + 32]):
        invalid("Transfer の予約領域が0ではありません")
    expected = base + 32 + count * 16 + message_size
    if len(tx) != expected:
        invalid("Transfer の Mosaic 数やメッセージ長が不正です")
    mosaics = []
    pos = base + 32
    for _ in range(count):
        mosaic_id, amount = struct.unpack_from("<QQ", tx, pos)
        mosaics.append({"unresolved_id": f"0x{mosaic_id:016X}", "amount_raw": amount})
        pos += 16
    message = tx[pos:]
    result = {"recipient_unresolved_hex": recipient.hex().upper(),
              "mosaics": mosaics, "message_hex": message.hex().upper()}
    if message[:1] == b"\x00":
        result["plain_text"] = message[1:].decode("utf-8", errors="replace")
    return result


def header(tx: bytes, embedded: bool):
    minimum = 48 if embedded else 128
    if len(tx) < minimum:
        invalid("共通ヘッダーが不足しています")
    size, reserved = struct.unpack_from("<II", tx)
    if size != len(tx) or reserved:
        invalid("共通ヘッダーの長さ・予約領域が不正です")
    signer_at = 8 if embedded else 72
    version_at = 44 if embedded else 108
    if any(tx[signer_at + 32:version_at]):
        invalid("共通ヘッダーの予約領域が不正です")
    version, network, kind = struct.unpack_from("<BBH", tx, version_at)
    if kind & 0xC000 != 0x4000:
        invalid("トランザクション種別が不正です")
    result = {"type": f"0x{kind:04X}", "version": version,
              "network": f"0x{network:02X}",
              "signer": tx[signer_at:signer_at + 32].hex().upper(),
              "size": size}
    if not embedded:
        fee, deadline = struct.unpack_from("<QQ", tx, 112)
        result.update(max_fee_raw=fee, deadline_raw=deadline)
    if kind == TRANSFER and version == 1:
        result["transfer"] = transfer(tx, embedded)
    elif kind in AGGREGATES and not embedded and version == 3:
        result["aggregate"] = aggregate(tx)
    else:
        result["note"] = "この形式は共通ヘッダーのみ解析"
    return result


def aggregate(tx: bytes):
    if len(tx) < 168:
        invalid("Aggregate V3 ヘッダーが不足しています")
    (payload_size,) = struct.unpack_from("<I", tx, 160)
    if any(tx[164:168]) or payload_size % 8:
        invalid("Aggregate の予約領域・PayloadSize が不正です")
    tail = len(tx) - 168 - payload_size
    if tail < 0 or tail % 104:
        invalid("Aggregate の cosignature 領域が不正です")
    embedded_data = tx[168:168 + payload_size]
    embedded = [header(item, True) for item in records(embedded_data, 48, True)]
    return {"transactions_hash": tx[128:160].hex().upper(),
            "payload_size": payload_size, "embedded": embedded,
            "cosignatures_count": tail // 104}


def parse_block(raw: bytes):
    if len(raw) < 112:
        invalid("ブロック共通部が不足しています")
    (size,) = struct.unpack_from("<I", raw)
    if size != len(raw):
        invalid("ブロック本体の Size が一致しません")
    version, network, block_type = struct.unpack_from("<BBH", raw, 108)
    start = BLOCK_HEAD.get(block_type)
    if version != 1 or start is None or len(raw) < start:
        invalid("未対応のブロックヘッダーです")
    (height,) = struct.unpack_from("<Q", raw, 112)
    items = [header(item, False) for item in records(raw[start:], 128, False)]
    return {"height": height, "block_type": f"0x{block_type:04X}",
            "network": f"0x{network:02X}", "transactions": items}


def demo_block():
    # Synthetic values and invalid signatures: never broadcast this fixture.
    ordinary = transaction_fixture(b"\x00hello")
    embedded = bytearray(48 + len(ordinary) - 128)
    struct.pack_into("<I", embedded, 0, len(embedded))
    embedded[8:40] = ordinary[72:104]
    struct.pack_into("<BBH", embedded, 44, 1, 0x98, TRANSFER)
    embedded[48:] = ordinary[128:]
    payload = bytes(embedded) + bytes((-len(embedded)) % 8)
    agg = bytearray(168 + len(payload) + 104)
    struct.pack_into("<I", agg, 0, len(agg))
    agg[8:72] = b"\x11" * 64
    agg[72:104] = b"\x22" * 32
    struct.pack_into("<BBHQQ", agg, 108, 3, 0x98, 0x4141, 0, 123456)
    struct.pack_into("<I", agg, 160, len(payload))
    agg[168:168 + len(payload)] = payload
    return block_fixture(transactions=(ordinary, bytes(agg)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--demo", action="store_true")
    choice.add_argument("--file", type=Path, help="P2P ヘッダーを除いたブロック本体")
    args = parser.parse_args()
    try:
        if args.demo:
            raw = demo_block()
        else:
            with args.file.open("rb") as source:
                raw = source.read(MAX_FILE + 1)
            if len(raw) > MAX_FILE:
                invalid("ファイルがクライアント上限を超えています")
        print(json.dumps(parse_block(raw), indent=2, ensure_ascii=False))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"解析失敗: {exc}\n")


if __name__ == "__main__":
    main()
