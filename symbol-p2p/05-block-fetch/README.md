# 第5章：ブロックの取得

[書籍の章原稿](https://github.com/ccHarvestasya/zenn/blob/main/books/symbol-p2p-python/05-block-fetch.md)

リポジトリ取得後、`symbol-p2p/05-block-fetch/` に移動して実行します。必要な通信処理を同梱しています。ブロック本体は Python 版 Symbol SDK 3.3.2 で解析します。Python 3.12 以上を使用します。

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

共通のクライアント証明書を用意してから、接続先と取得したい高さを指定して実行します。

```bash
python3 pull_block.py testnet1.symbol-mikun.net --port 7900 --height 0
```

高さ `0` は接続先の最新高です。第1〜4章と同じく、Python 側では `CERT_NONE` で接続先の証明書検証を省略する学習用の接続です。ブロックの署名や VRF、TransactionsHash の検証も行いません。

2026年10月12日に Testnet ノードから高さ `3795211` のブロックを取得しました。出力例は対応する章に掲載しています。

クライアント証明書は各章で共通の `../common/cert/` を使います。まだ作成していない場合だけ、`bash ../common/generate_certificates.sh` を実行してください。章ごとに鍵を作り直す必要はありません。

## ファイル

- [pull_block.py](pull_block.py)：Pull Block の要求、SDK によるブロック解析、CLI
- [p2p_common.py](p2p_common.py)：TLS 設定、上限付きパケット送受信
- [requirements.txt](requirements.txt)：使用する SDK のバージョン
