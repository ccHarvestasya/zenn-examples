# 第5回：ブロックの取得

[記事原稿](https://github.com/ccHarvestasya/zenn/blob/main/articles/symbol-p2p-05-block-fetch.md)

リポジトリ取得後、`symbol-p2p/05-block-fetch/` に移動して実行します。このディレクトリに必要な依存ファイルを同梱しています。Python 3.12 以上を使用し、追加の Python パッケージは不要です。

```bash
python3 fixture_data.py generated-fixtures
python3 pull_block.py --file generated-fixtures/normal-block.bin --height 42
```

上のコマンドは通信しないデモです。通信機能があるコードでは、同梱の `chain_statistics.py` が接続先の CA ファイルを使う TLS 設定を提供します。第1回の学習用コードとは設定が異なります。実ノードへの接続条件は記事を参照してください。

## ファイル

- [chain_statistics.py](chain_statistics.py)
- [entities.py](entities.py)
- [fixture_data.py](fixture_data.py)
- [generate_certificates.sh](generate_certificates.sh)
- [p2p_common.py](p2p_common.py)
- [pull_block.py](pull_block.py)

