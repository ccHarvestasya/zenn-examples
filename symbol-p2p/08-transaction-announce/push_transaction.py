"""Inspect a serialized signed transaction; send only to owned loopback nodes."""
import argparse
import ipaddress
import json
from pathlib import Path
import sys

from entities import transaction_header
from p2p_common import MAX_PACKET, ProtocolError, connection, make_context, packet, write_packet

CERT_DIRECTORY = Path(__file__).resolve().parent.parent / "common" / "cert"

PUSH_TRANSACTIONS = 9


def make_request(transaction: bytes) -> bytes:
    transaction_header(transaction)
    if not any(transaction[8:72]) or not any(transaction[72:104]):
        raise ProtocolError('空の署名または公開鍵は送信用入力にできません')
    # This checks shape only, not cryptographic signature or plugin-specific body.
    return packet(PUSH_TRANSACTIONS, transaction)


def send_transaction(transaction, host, port, context, *, enabled=False, private_network=False):
    data = make_request(transaction)
    if not enabled or not private_network:
        raise ValueError('送信には enabled と private_network の明示が必要です')
    if not ipaddress.ip_address(host).is_loopback:
        raise ValueError('送信先は自分で管理するループバック IP に限定します')
    if transaction_header(transaction)['network'] == 0x68:
        raise ValueError('Mainnet 識別子のトランザクションは送信しません')
    with connection(host, port, context) as (tls, deadline):
        write_packet(tls, data, deadline)
    # Push_Transactions has no acknowledgement response. Do not read one.


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('payload_file', help='署名済み通常トランザクションの hex ファイル')
    parser.add_argument('--send', action='store_true')
    parser.add_argument('--confirm-private-network', action='store_true')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=7900)
    parser.add_argument('--peer-ca')
    parser.add_argument('--cert', default=str(CERT_DIRECTORY / "node.full.crt.pem"))
    parser.add_argument('--key', default=str(CERT_DIRECTORY / "node.key.pem"))
    args = parser.parse_args()
    if args.send and (not args.confirm_private_network or not args.peer_ca):
        parser.error('--send には --confirm-private-network と --peer-ca が必要です')
    try:
        with Path(args.payload_file).open('rb') as source:
            raw = source.read(2 * MAX_PACKET + 1)
        if len(raw) > 2 * MAX_PACKET:
            raise ProtocolError('hex ファイルが上限を超えています')
        transaction = bytes.fromhex(raw.decode('ascii'))
        request = make_request(transaction)
        info = transaction_header(transaction)
        if args.send:
            # Check target before loading keys or establishing any connection.
            if not ipaddress.ip_address(args.host).is_loopback or info['network'] == 0x68:
                raise ValueError('自分の検証網のループバック接続先だけを指定してください')
            context = make_context(args.peer_ca, args.cert, args.key)
            send_transaction(transaction, args.host, args.port, context,
                             enabled=True, private_network=True)
    except (OSError, ValueError) as exc:
        print(f'入力・送信失敗: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(dict(packet_size=len(request), transaction_size=len(transaction),
                          type=f"0x{info['type']:04X}", sent=args.send,
                          acceptance='未確認', confirmation='未確認'), ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
