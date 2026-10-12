# Symbol P2P 通信のサンプル

記事の回ごとにディレクトリを分けています。各回の README にある実行手順を、そのディレクトリで実行してください。Python の依存ファイルは各回に同梱し、クライアント証明書と生成スクリプトは `common/` にまとめています。

```bash
git clone https://github.com/ccHarvestasya/zenn-examples.git
cd zenn-examples/symbol-p2p/01-connect
```

## 共通のクライアント証明書

初回に一度だけ生成します。上のコマンドで `01-connect/` に移動した状態で実行してください。

```bash
bash ../common/generate_certificates.sh
```

生成先は `symbol-p2p/common/cert/` です。詳しい手順は [common/README.md](common/README.md) にあります。CA 証明書は3650日、Node 証明書は365日有効です。各回のコードはこの証明書を既定で読み込みます。既存の証明書は上書きせず、回ごとに異なる鍵を作らずに使い回します。

| 回 | ディレクトリ | テーマ |
| --- | --- | --- |
| 1 | [01-connect](01-connect/) | 接続とチェーン統計 |
| 2 | [02-packet-decode](02-packet-decode/) | パケットの解析 |
| 3 | [03-node-info](03-node-info/) | ノード情報の取得 |
| 4 | [04-peer-discovery](04-peer-discovery/) | ピア探索 |
| 5 | [05-block-fetch](05-block-fetch/) | ブロックの取得 |
| 6 | [06-block-transactions](06-block-transactions/) | ブロック内トランザクションの解析 |
| 7 | [07-finalization](07-finalization/) | ファイナライズ情報 |
| 8 | [08-transaction-announce](08-transaction-announce/) | トランザクションの送信 |
| 9 | [09-wireshark](09-wireshark/) | Wireshark による通信観察 |
| 10 | [10-security](10-security/) | セキュリティと実装範囲 |

第1〜8回は Python 側の接続先認証を省略する学習用コードです。第9回以降の既存の通信コードは接続先の CA ファイルを指定する実装を同梱しており、同じ設定ではありません。第1〜8回は接続先を指定して実行します。通信しないデモがある回は、各回の README に案内しています。

共通の処理にも各回のコピーを置き、記事を単独で再現できる構成にしています。
