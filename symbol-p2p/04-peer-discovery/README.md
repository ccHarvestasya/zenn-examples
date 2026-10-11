# 第4回：ピア探索

[記事原稿](https://github.com/ccHarvestasya/zenn/blob/main/articles/symbol-p2p-04-peer-discovery.md)

リポジトリ取得後、`symbol-p2p/04-peer-discovery/` に移動して実行します。このディレクトリに必要な Python の依存ファイルを同梱しています。Python 3.12 以上を使用し、追加の Python パッケージは不要です。

```bash
python3 pull_peers.py --demo
```

上のコマンドは通信しないデモです。通信機能があるコードでは、同梱の `chain_statistics.py` が接続先の CA ファイルを使う TLS 設定を提供します。第1回の学習用コードとは設定が異なります。実ノードへの接続条件は記事を参照してください。

クライアント証明書は各回で共通の `../common/cert/` を使います。まだ作成していない場合だけ、`bash ../common/generate_certificates.sh` を実行してください。回ごとに鍵を作り直す必要はありません。

## ファイル

- [chain_statistics.py](chain_statistics.py)
- [node_info.py](node_info.py)
- [pull_peers.py](pull_peers.py)
