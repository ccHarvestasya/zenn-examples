# Symbol P2P 通信のサンプル

記事の回ごとにディレクトリを分けています。各回の README にある実行手順を、そのディレクトリで実行してください。依存ファイルは各回に同梱しているため、他の回からコピーする必要はありません。

```bash
git clone https://github.com/ccHarvestasya/zenn-examples.git
cd zenn-examples/symbol-p2p/01-connect
```

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

第1回は Python 側の接続先認証を省略する学習用コードです。第2回以降の既存の通信コードは接続先の CA ファイルを指定する実装を同梱しており、同じ設定ではありません。通信しないデモから試せる回は、各回の README に案内しています。

共通の処理にも各回のコピーを置き、記事を単独で再現できる構成にしています。
