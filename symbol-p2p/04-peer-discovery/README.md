# 第4回：ピア探索

[記事原稿](https://github.com/ccHarvestasya/zenn/blob/main/articles/symbol-p2p-04-peer-discovery.md)

リポジトリ取得後、`symbol-p2p/04-peer-discovery/` に移動して実行します。`pull_peers.py` に必要な通信処理とノード情報のパーサーを含めています。Python 3.12 以上を使用し、追加の Python パッケージは不要です。

共通のクライアント証明書を用意してから、接続先を指定して実行します。

```bash
python3 pull_peers.py testnet1.symbol-mikun.net --port 7900
```

第1〜3回と同じく、Python 側では `CERT_NONE` で接続先の証明書検証を省略する学習用の接続です。取得した候補への接続は行いません。

2026年10月12日に Testnet ノードから14件の候補を取得しました。出力例は記事に掲載しています。

クライアント証明書は各回で共通の `../common/cert/` を使います。まだ作成していない場合だけ、`bash ../common/generate_certificates.sh` を実行してください。回ごとに鍵を作り直す必要はありません。

## ファイル

- [pull_peers.py](pull_peers.py)
