# 第7回：ファイナライズ情報

[記事原稿](https://github.com/ccHarvestasya/zenn/blob/main/articles/symbol-p2p-07-finalization.md)

リポジトリ取得後、`symbol-p2p/07-finalization/` に移動して実行します。このディレクトリに必要な依存ファイルを同梱しています。Python 3.12 以上を使用し、追加の Python パッケージは不要です。

```bash
python3 finalization.py --demo
```

上のコマンドは通信しないデモです。通信機能があるコードでは、同梱の `chain_statistics.py` が接続先の CA ファイルを使う TLS 設定を提供します。第1回の学習用コードとは設定が異なります。実ノードへの接続条件は記事を参照してください。

## ファイル

- [chain_statistics.py](chain_statistics.py)
- [finalization.py](finalization.py)
- [generate_certificates.sh](generate_certificates.sh)
- [p2p_common.py](p2p_common.py)
