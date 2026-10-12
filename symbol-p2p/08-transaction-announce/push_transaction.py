"""Inspect a signed Testnet Transfer V1; announce only with --send."""
import argparse
import json
from pathlib import Path
import sys

from symbolchain import sc
from symbolchain.CryptoTypes import Signature
from symbolchain.facade.SymbolFacade import SymbolFacade
from p2p_common import MAX_PACKET, ProtocolError, connection, make_context, packet, write_packet

CERT_DIRECTORY = Path(__file__).resolve().parent.parent / "common" / "cert"
PUSH_TRANSACTIONS = 9


def inspect_transaction(data):
    try:
        tx = sc.TransactionFactory.deserialize(data)
        if tx.serialize() != data:
            raise ValueError('トランザクションの長さまたは形式が不正です')
        if tx.network != sc.NetworkType.TESTNET:
            raise ValueError('このサンプルは Testnet の取引だけを扱います')
        if not isinstance(tx, sc.TransferTransactionV1):
            raise ValueError('このサンプルは通常の Transfer V1 だけを扱います')
        facade = SymbolFacade('testnet')
        if not facade.verify_transaction(tx, Signature(tx.signature.bytes)):
            raise ValueError('Testnet の generation hash seed を使った署名検証に失敗しました')
    except (AssertionError, IndexError, KeyError, ValueError) as exc:
        raise ProtocolError(f'入力を検証できません: {exc}') from exc
    return tx


def make_request(transaction):
    inspect_transaction(transaction)
    return packet(PUSH_TRANSACTIONS, transaction)


def send_transaction(transaction, host, port, context, *, enabled=False):
    data = make_request(transaction)
    if not enabled:
        raise ValueError('送信には enabled の明示が必要です')
    with connection(host, port, context) as (tls, deadline):
        write_packet(tls, data, deadline)
    # Push_Transactions has no acknowledgement response. Do not read one.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('host', help='接続先のホスト名または IP')
    parser.add_argument('payload_file', help='署名済み Testnet 通常取引の hex ファイル')
    parser.add_argument('--send', action='store_true')
    parser.add_argument('--port', type=int, default=7900)
    parser.add_argument('--cert', default=str(CERT_DIRECTORY / "node.full.crt.pem"))
    parser.add_argument('--key', default=str(CERT_DIRECTORY / "node.key.pem"))
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port は 1〜65535 で指定してください')
    try:
        with Path(args.payload_file).open('rb') as source:
            raw = source.read(2 * MAX_PACKET + 1)
        if len(raw) > 2 * MAX_PACKET:
            raise ProtocolError('hex ファイルが上限を超えています')
        transaction = bytes.fromhex(raw.decode('ascii'))
        request = make_request(transaction)
        tx = inspect_transaction(transaction)
        if args.send:
            context = make_context(args.cert, args.key)
            send_transaction(transaction, args.host, args.port, context, enabled=True)
    except (OSError, ValueError) as exc:
        print(f'入力・送信失敗: {exc}', file=sys.stderr)
        return 1
    print(json.dumps({'packet_size': len(request), 'transaction_size': tx.size,
                      'type': tx.type_.name, 'signature_valid': True,
                      'sent': args.send, 'acceptance': '未確認',
                      'confirmation': '未確認'}, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
