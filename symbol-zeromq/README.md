# Symbol ZeroMQの通知サンプル

Node.js v26.5.0 / zeromq 6.8.0 / symbol-sdk 3.3.3。実行検証はLinuxで行っています。

```bash
npm ci
npm run check
npm test
npm run demo
```

`demo`は実Brokerを使わず、公式の送信形式に合わせたデータをローカルTCP上で配信・購読します。XPUBの購読通知を待ってから配信するため、起動時の購読反映待ちを固定のsleepで代用しません。デモの取引は署名なしの検証用データで、チェーンの状態を示すものではありません。

## Brokerに接続する

```bash
node monitor.ts tcp://127.0.0.1:7902 block finalizedBlock dropBlocks
node monitor.ts tcp://127.0.0.1:7902 confirmedAdded unconfirmedAdded unconfirmedRemoved
node monitor.ts tcp://127.0.0.1:7902 partialAdded partialRemoved cosignature status
node monitor.ts tcp://127.0.0.1:7902 confirmedAdded/TD6TLAMJMDD3DC3S6SNFLGH2T5YSUNKNWM7N4VY
```

接続先・アドレスは自分の環境の値に変更します。アドレスフィルターはMainnetまたはTestnetの通常アドレスに対応しています。終了はCtrl+Cです。

## ファイル

| ファイル      | 内容                                                         |
| ------------- | ------------------------------------------------------------ |
| `topics.ts`   | マーカー・アドレス購読フィルター・配送先トピックの読み取り   |
| `decode.ts`   | 10種類の通知をフレーム数・固定長を確認してデコード           |
| `monitor.ts`  | Brokerを購読してJSON Linesを表示                             |
| `fixtures.ts` | 公式実装のフレーム構造に合わせた検証用データ                 |
| `demo.ts`     | XPUB/SUBによるローカル配信・購読                             |
| `test/`       | バイナリ解析・アドレスフィルター・不正通知・終了処理のテスト |

出力はSDKモデルのJSONです。RESTのフィールド名・数値表現などへの変換は行いません。取引関連の`address`は、Brokerが配送用に付けた関連アドレスであり、転送先に限定されません。

フレームの構造を確認するコードであり、取引・連署の暗号学的検証、永続化、切断中の通知補完は含みません。

## 検証と根拠

公式ソースはSymbolのcommit `dbff03b4096622d1bc1fce611358e05cfa7b0296`を確認しました。

- [マーカー](https://github.com/symbol/symbol/blob/dbff03b4096622d1bc1fce611358e05cfa7b0296/client/catapult/extensions/zeromq/src/ZeroMqEntityPublisher.h)
- [フレーム構造と関連アドレスごとの配信](https://github.com/symbol/symbol/blob/dbff03b4096622d1bc1fce611358e05cfa7b0296/client/catapult/extensions/zeromq/src/ZeroMqEntityPublisher.cpp)
- [ブロックのsize補正などRESTの処理](https://github.com/symbol/symbol/blob/dbff03b4096622d1bc1fce611358e05cfa7b0296/client/rest/src/connection/serverMessageHandlers.js)

型チェック、9件のテスト、ローカルZeroMQでの全10種類の送受信・デコードを確認しました。実Brokerへの接続、ノード設定の変更後の動作、Windowsでの実行は今回未検証です。

記事原稿は親リポジトリの`articles/symbol-zeromq-01-blocks.md`、`symbol-zeromq-02-transactions.md`、`symbol-zeromq-03-partial-status.md`です。元原稿はワークスペースのdraftにあるZeroMQ1～3と、REST・MongoDBを外したBroker構成の記事です。
