# 第1章：接続とチェーン統計

[書籍の章原稿](https://github.com/ccHarvestasya/zenn/blob/main/books/symbol-p2p-python/01-connect.md)

リポジトリ取得後、`symbol-p2p/01-connect/` に移動して実行します。このディレクトリに必要な Python の依存ファイルを同梱しています。Python 3.12 以上を使用し、追加の Python パッケージは不要です。

```bash
# 初回のみ（作成済みなら省略）
bash ../common/generate_certificates.sh
python3 chain_statistics_demo.py testnet1.symbol-mikun.net --port 7900
```

Python 側では接続先の証明書検証を省略する学習用コードです。対応する章には Testnet から取得した出力例を掲載しています。生成した鍵は Git に追加せず、本書の学習中は同じ鍵を使い、不要になったら削除してください。

クライアント証明書は各章で共通の `../common/cert/` を使います。まだ作成していない場合だけ、`bash ../common/generate_certificates.sh` を実行してください。章ごとに鍵を作り直す必要はありません。

## ファイル

- [chain_statistics_demo.py](chain_statistics_demo.py)

