# 第8章：トランザクションの送信

[書籍の章原稿](https://github.com/ccHarvestasya/zenn/blob/main/books/symbol-p2p-python/08-transaction-announce.md)

リポジトリ取得後、`symbol-p2p/08-transaction-announce/` に移動します。Python 3.12 以上と Python 版 Symbol SDK 3.3.2 を使用します。

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 prepare_transfer.py signed-transaction.hex
python3 push_transaction.py testnet1.symbol-mikun.net signed-transaction.hex --port 7900
```

既定では署名と形式を検査し、パケットを組み立てるだけで接続しません。作成コードは、環境変数 `SYMBOL_PRIVATE_KEY` があればその鍵を、なければメモリ内で生成する一時鍵を使用します。秘密鍵は保存・表示しません。一時アカウントには残高がなく、送信前チェック用です。

実送信には、手数料を支払える残高を持つTestnetアカウントの署名済みペイロードを使い、`--send` を付けます。詳細は対応する章の実行手順を参照してください。公開ノードでの送信・受理・ブロック取り込みは未検証です。

クライアント証明書は共通の `../common/cert/` を使います。まだ作成していない場合だけ、`bash ../common/generate_certificates.sh` を実行してください。

第1〜7章と同じく、接続先の証明書検証は `CERT_NONE` で省略しています。送信の完了だけで受理・ブロック取り込みは確認できません。

## ファイル

- [prepare_transfer.py](prepare_transfer.py)：SDKで署名済みの自己宛てTransferを作成
- [push_transaction.py](push_transaction.py)：取引の形式・署名の検査とP2P送信
- [p2p_common.py](p2p_common.py)：TLS設定とパケット送受信
- [requirements.txt](requirements.txt)：SDKのバージョン

入力は署名済みの Testnet 通常 Transfer V1 に限定します。Aggregate や他の種別・バージョンは接続前に拒否します。署名検証は残高・期限・ノードの受理を保証しません。
