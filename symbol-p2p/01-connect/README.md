# 第1回：接続とチェーン統計

[記事原稿](https://github.com/ccHarvestasya/zenn/blob/main/articles/symbol-p2p-01-connect.md)

リポジトリ取得後、`symbol-p2p/01-connect/` に移動して実行します。このディレクトリに必要な依存ファイルを同梱しています。Python 3.12 以上を使用し、追加の Python パッケージは不要です。

```bash
bash generate_certificates.sh
python3 chain_statistics_demo.py testnet1.symbol-mikun.net --port 7900
```

Python 側では接続先の証明書検証を省略する学習用コードです。記事には Testnet から取得した出力例を掲載しています。生成した鍵は Git に追加せず、不要になった検証用の鍵は削除してください。

## ファイル

- [chain_statistics_demo.py](chain_statistics_demo.py)
- [generate_certificates.sh](generate_certificates.sh)

