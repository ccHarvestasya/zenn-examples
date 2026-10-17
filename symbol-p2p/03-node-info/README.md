# 第3章：ノード情報の取得

[書籍の章原稿](https://github.com/ccHarvestasya/zenn/blob/main/books/symbol-p2p-python/03-node-info.md)

リポジトリ取得後、`symbol-p2p/03-node-info/` に移動して実行します。`node_info.py` に必要な通信処理を含めています。Python 3.12 以上を使用し、追加の Python パッケージは不要です。

共通のクライアント証明書を用意してから、接続先を指定して実行します。

```bash
python3 node_info.py testnet1.symbol-mikun.net --port 7900
```

第1章と同じく、Python 側では `CERT_NONE` で接続先の証明書検証を省略する学習用の接続です。

2026年10月12日に Testnet ノードから情報を取得しました。出力例は対応する章に掲載しています。

クライアント証明書は各章で共通の `../common/cert/` を使います。まだ作成していない場合だけ、`bash ../common/generate_certificates.sh` を実行してください。章ごとに鍵を作り直す必要はありません。

## ファイル

- [node_info.py](node_info.py)

