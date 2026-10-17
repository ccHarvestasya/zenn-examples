# 第6章：ブロック内トランザクションの解析

[書籍の章原稿](https://github.com/ccHarvestasya/zenn/blob/main/books/symbol-p2p-python/06-block-transactions.md)

リポジトリ取得後、`symbol-p2p/06-block-transactions/` に移動して実行します。Python 3.12 以上を使用し、第5章と同じ Python 版 Symbol SDK 3.3.2 でブロックを解析します。

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

共通のクライアント証明書を用意してから、接続先と取得したい高さを指定します。

```bash
python3 block_transactions.py testnet1.symbol-mikun.net --port 7900 --height 3795221
```

2026年10月12日に Testnet ノードから、Aggregate Bondedと内側のTransferを取得しました。出力例は対応する章に掲載しています。高さ `0` は最新高を要求し、取引0件の場合もあります。

クライアント証明書は共通の `../common/cert/` を使います。まだ作成していない場合だけ、`bash ../common/generate_certificates.sh` を実行してください。

第1〜5章と同じく、接続先の証明書検証は `CERT_NONE` で省略しています。署名・連署・TransactionsHash の検証やAliasの解決も行いません。

## ファイル

- [block_transactions.py](block_transactions.py)：ブロック取得と取引情報の表示
- [p2p_common.py](p2p_common.py)：TLS設定とパケット送受信
- [requirements.txt](requirements.txt)：SDKのバージョン
