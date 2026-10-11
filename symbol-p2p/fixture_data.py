"""Synthetic binary fixtures: signatures/VRF/addresses are NOT valid for sending."""
import argparse
from pathlib import Path
import struct


def transaction_fixture(message=b'') -> bytes:
    data = bytearray(160 + len(message))
    struct.pack_into('<I', data, 0, len(data))
    data[8:72] = b'\x11' * 64
    data[72:104] = b'\x22' * 32
    struct.pack_into('<BBHQQ', data, 108, 1, 0x98, 0x4154, 0, 123456)
    data[128:152] = b'\x33' * 24  # Fictitious address.
    struct.pack_into('<H', data, 152, len(message))
    data[160:] = message
    return bytes(data)


def block_fixture(kind=0x8143, height=42, transactions=()) -> bytes:
    size = 376 if kind == 0x8143 else 424
    data = bytearray(size)
    data[8:72] = b'\x11' * 64
    data[72:104] = b'\x22' * 32
    struct.pack_into('<BBHQQQ', data, 108, 1, 0x98, kind, height, 123456, 100)
    data[216:248] = b'\x33' * 32
    for index, transaction in enumerate(transactions):
        data.extend(transaction)
        if index < len(transactions) - 1:
            data.extend(bytes((-len(transaction)) % 8))
    struct.pack_into('<I', data, 0, len(data))
    return bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', help='新しい生成先ディレクトリ')
    args = parser.parse_args()
    directory = Path(args.directory)
    directory.mkdir()  # Refuse to overwrite an existing fixture directory.
    (directory / 'normal-block.bin').write_bytes(block_fixture())
    (directory / 'transaction.hex').write_text(transaction_fixture().hex() + '\n')
    print('模擬データを生成しました。署名は無効です。transaction.hex を実送信しないでください。')


if __name__ == '__main__':
    main()
