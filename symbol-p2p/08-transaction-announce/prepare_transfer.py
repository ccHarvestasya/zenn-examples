"""Create a signed Testnet self-transfer without announcing it."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from symbolchain.CryptoTypes import PrivateKey
from symbolchain.facade.SymbolFacade import SymbolFacade


def create_transfer(private_key=None):
    facade = SymbolFacade('testnet')
    key = private_key or PrivateKey.random()
    key_pair = facade.KeyPair(key)
    recipient = facade.network.public_key_to_address(key_pair.public_key)
    deadline = facade.network.from_datetime(datetime.now(timezone.utc)).add_hours(2)
    tx = facade.transaction_factory.create({
        'type': 'transfer_transaction_v1',
        'signer_public_key': key_pair.public_key,
        'recipient_address': recipient,
        'fee': 1000000, 'deadline': deadline.timestamp,
        'mosaics': [], 'message': b'\x00Symbol P2P example',
    })
    signature = facade.sign_transaction(key_pair, tx)
    facade.transaction_factory.attach_signature(tx, signature)
    return tx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    key_text = os.environ.get('SYMBOL_PRIVATE_KEY')
    tx = create_transfer(PrivateKey(key_text) if key_text else None)
    # Refuse to overwrite an existing payload; never write the private key.
    with args.output.open('x') as file:
        file.write(tx.serialize().hex().upper() + '\n')
    print(json.dumps({'payload_file': str(args.output),
                      'temporary_account': key_text is None,
                      'transaction_size': tx.size}, indent=2))


if __name__ == '__main__':
    main()
