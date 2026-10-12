# 第10回：セキュリティと実装範囲

[記事原稿](https://github.com/ccHarvestasya/zenn/blob/main/articles/symbol-p2p-10-security.md)

この回は第1〜9回の実装範囲を整理する記事です。新しい実行用サンプルはありません。

- TLS 接続では、接続先の証明書検証を `CERT_NONE` で省略しています。Catapult 独自の相互検証は再現していません。
- 第5・6回は SDK でブロックと取引を解析しますが、ブロック署名や状態遷移は検証しません。
- 第7回は Finalization Proof の構造を解析しますが、署名や投票重みは検証しません。
- 第8回は入力を Testnet の通常 Transfer V1 に限定し、SDK で署名を検証しますが、ノードの受理・取り込み・確定は確認しません。
- 第9回は Wireshark 4.2.2 の dumpcap・TShark で実ノードとの通信をキャプチャし、同じ実行の鍵ログで要求・応答の復号を確認しています。GUI 操作は未検証です。

実行方法は各回の README を参照してください。クライアント証明書は共通の `../common/cert/` を使います。
