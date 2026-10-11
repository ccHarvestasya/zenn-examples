# 第8回：トランザクションの送信

[記事原稿](https://github.com/ccHarvestasya/zenn/blob/main/articles/symbol-p2p-08-transaction-announce.md)

リポジトリ取得後、`symbol-p2p/08-transaction-announce/` に移動して実行します。このディレクトリに必要な Python の依存ファイルを同梱しています。Python 3.12 以上を使用し、追加の Python パッケージは不要です。

```bash
python3 fixture_data.py generated-fixtures
python3 push_transaction.py generated-fixtures/transaction.hex
```

上のコマンドはパケットを構築・表示するだけで、送信しません。生成するデータの署名は無効です。送信には私設ネットワークと明示的な実行オプションが必要です。

クライアント証明書は各回で共通の `../common/cert/` を使います。まだ作成していない場合だけ、`bash ../common/generate_certificates.sh` を実行してください。回ごとに鍵を作り直す必要はありません。

## ファイル

- [chain_statistics.py](chain_statistics.py)
- [entities.py](entities.py)
- [fixture_data.py](fixture_data.py)
- [p2p_common.py](p2p_common.py)
- [push_transaction.py](push_transaction.py)

