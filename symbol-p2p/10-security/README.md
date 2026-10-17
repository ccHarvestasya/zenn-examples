# 第9章：セキュリティと実装範囲

[書籍の章原稿](https://github.com/ccHarvestasya/zenn/blob/main/books/symbol-p2p-python/09-security.md)

この章では第1〜8章の実装範囲を整理します。新しい実行用サンプルはありません。

- TLS 接続では、接続先の証明書検証を `CERT_NONE` で省略しています。Catapult 独自の相互検証は再現していません。
- 第5・6章は SDK でブロックと取引を解析しますが、ブロック署名や状態遷移は検証しません。
- 第7章は Finalization Proof の構造を解析しますが、署名や投票重みは検証しません。
- 第8章は入力を Testnet の通常 Transfer V1 に限定し、SDK で署名を検証しますが、ノードの受理・取り込み・確定は確認しません。

実行方法は各章の README を参照してください。クライアント証明書は共通の `../common/cert/` を使います。
