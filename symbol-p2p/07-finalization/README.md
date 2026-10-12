# 第7回：ファイナライズ情報

[記事原稿](https://github.com/ccHarvestasya/zenn/blob/main/articles/symbol-p2p-07-finalization.md)

リポジトリ取得後、`symbol-p2p/07-finalization/` に移動して実行します。Python 3.12 以上を使用し、追加の Python パッケージは不要です。

共通のクライアント証明書を用意してから、接続先と取得する情報を指定します。

```bash
python3 finalization.py testnet1.symbol-mikun.net --port 7900 --stats
```

2026年10月12日に Testnet ノードから統計とエポック指定の Proof を取得しました。統計で返されたエポック・高さを使い、次のように要求できます。

```bash
python3 finalization.py testnet1.symbol-mikun.net --port 7900 --proof-epoch 5273
python3 finalization.py testnet1.symbol-mikun.net --port 7900 --proof-height 3795264
```

このとき高さ指定は空応答となり、`null` を表示しました。実出力は記事に掲載しています。空の応答だけで、ブロックが未確定とは判断しません。

クライアント証明書は共通の `../common/cert/` を使います。まだ作成していない場合だけ、`bash ../common/generate_certificates.sh` を実行してください。

第1〜6回と同じく、接続先の証明書検証は `CERT_NONE` で省略しています。Proof の署名や投票重みの検証も行いません。

## ファイル

- [finalization.py](finalization.py)：要求の作成、統計・Proof の解析と表示
- [p2p_common.py](p2p_common.py)：TLS設定とパケット送受信
