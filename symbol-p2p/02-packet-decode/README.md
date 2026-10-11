# 第2回：パケットの解析

[記事原稿](https://github.com/ccHarvestasya/zenn/blob/main/articles/symbol-p2p-02-packet-decode.md)

リポジトリ取得後、`symbol-p2p/02-packet-decode/` に移動して実行します。このディレクトリに必要な Python の依存ファイルを同梱しています。Python 3.12 以上を使用し、追加の Python パッケージは不要です。

共通のクライアント証明書を用意してから、接続先を指定して実行します。

```bash
python3 node_info.py testnet1.symbol-mikun.net --port 7900
```

第1回と同じく、Python 側では `CERT_NONE` で接続先の証明書検証を省略する学習用の接続です。

2026年10月12日に Testnet ノードから情報を取得しました。出力例は記事に掲載しています。

クライアント証明書は各回で共通の `../common/cert/` を使います。まだ作成していない場合だけ、`bash ../common/generate_certificates.sh` を実行してください。回ごとに鍵を作り直す必要はありません。

## ファイル

- [chain_statistics.py](chain_statistics.py)
- [node_info.py](node_info.py)

