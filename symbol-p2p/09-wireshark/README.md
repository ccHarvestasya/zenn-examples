# 付録候補：Wireshark による通信観察

[付録候補の原稿](https://github.com/ccHarvestasya/zenn/blob/main/article-notes/symbol-p2p-python/appendix-candidates/wireshark.md)

本編の目次には含めない補助サンプルです。

リポジトリ取得後、`symbol-p2p/09-wireshark/` に移動して実行します。Python 3.12 以上を使用し、追加の Python パッケージは不要です。

```bash
python3 capture_peer.py testnet1.symbol-mikun.net --port 7900
```

共通のクライアント証明書を `../common/cert/` から読み込みます。まだ作成していない場合だけ、`bash ../common/generate_certificates.sh` を実行してください。

第1〜8章と同じく、接続先の証明書検証は `CERT_NONE` で省略する学習用コードです。ノード情報を取得する読み取り通信だけを行います。

`--keylog` に新しいファイルを指定すると、この接続のセッション鍵ログを生成します。2026年10月12日に実ノードへの通信を dumpcap でキャプチャし、Wireshark 4.2.2 の TShark に同じ実行の鍵ログを渡して、要求8バイト・応答125バイトを復号・照合しました。GUI 操作は未検証です。手順と実出力は付録候補の原稿を参照してください。

鍵ログとキャプチャはGitに追加せず、不要になったものを削除してください。

## ファイル

- [capture_peer.py](capture_peer.py)：TLS接続、応答ヘッダー、任意の鍵ログ
