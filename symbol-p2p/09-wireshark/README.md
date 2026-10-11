# 第9回：Wireshark による通信観察

[記事原稿](https://github.com/ccHarvestasya/zenn/blob/main/articles/symbol-p2p-09-wireshark.md)

リポジトリ取得後、`symbol-p2p/09-wireshark/` に移動して実行します。このディレクトリに必要な依存ファイルを同梱しています。Python 3.12 以上を使用し、追加の Python パッケージは不要です。

```bash
env -u SSLKEYLOGFILE python3 capture_lab.py --port 37900
```

ローカルの TLS サーバーとクライアントを起動します。キャプチャ・復号手順は記事を参照してください。外部ノードへ接続しません。

## ファイル

- [capture_lab.py](capture_lab.py)
- [chain_statistics.py](chain_statistics.py)
- [generate_certificates.sh](generate_certificates.sh)
- [node_info.py](node_info.py)

