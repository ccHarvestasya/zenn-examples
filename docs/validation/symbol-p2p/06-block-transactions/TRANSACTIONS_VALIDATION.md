# 第6回の検証

2026-10-12 14:21 JST、Python 3.12.3 / OpenSSL 3.5.2 / symbol-sdk-python 3.3.2。

P2PのPull Blockで高さ3795221を取得。既存の共通証明書を再利用し、CERT_NONEとTLS1.3を使用した。SDKでブロックを復元し、受信本文との再シリアライズ一致と要求高を照合した。署名・連署・TransactionsHash・チェーンの合意やAlias解決は検証していない。

```bash
python3 block_transactions.py testnet1.symbol-mikun.net --port 7900 --height 3795221
```

```json
{
  "height": 3795221,
  "block_type": "NORMAL",
  "network": "0x98",
  "transactions": [
    {
      "type": "0x4241",
      "type_name": "AGGREGATE_BONDED",
      "version": 3,
      "network": "0x98",
      "signer": "929B86AE072B44B7CF6C1D51454A721C8111EB142CF2507139071773F0740E45",
      "size": 1000,
      "max_fee_raw": 2500000,
      "deadline_raw": 124537357395,
      "aggregate": {
        "transactions_hash": "C4E28C723401BB08EBFDA8E294E723EC6C378981815DDE90E8F474F7F6816A58",
        "embedded": [
          {
            "type": "0x4154",
            "type_name": "TRANSFER",
            "version": 1,
            "network": "0x98",
            "signer": "929B86AE072B44B7CF6C1D51454A721C8111EB142CF2507139071773F0740E45",
            "size": 219,
            "transfer": {
              "recipient_unresolved_hex": "98CBE94CC1C48E8AD8C562CA874A6CC28EAF687C7FD4C799",
              "mosaics": [],
              "message_hex": "00E3809057726170E99B86E7B484E38091E3808CE3808CE3818BE3828FE38184E38184E3808DE381AEE58FAFE8A696E58C96E383BBE4BEA1E580A4E58C96E38397E383ADE382B8E382A7E382AFE38388E3808D2D3E20E382B3E383B3E38386E3838A20434E542D46413031364436312D433142322D343531462D384231422D453234343642353444393230",
              "plain_text": "\u3010Wrap\u96c6\u7d04\u3011\u300c\u300c\u304b\u308f\u3044\u3044\u300d\u306e\u53ef\u8996\u5316\u30fb\u4fa1\u5024\u5316\u30d7\u30ed\u30b8\u30a7\u30af\u30c8\u300d-> \u30b3\u30f3\u30c6\u30ca CNT-FA016D61-C1B2-451F-8B1B-E2446B54D920"
            }
          },
          {
            "type": "0x4154",
            "type_name": "TRANSFER",
            "version": 1,
            "network": "0x98",
            "signer": "9F767212131031DAEB80DFCA3503476802C450D7C3A16FF4C5C08D48131C9783",
            "size": 183,
            "transfer": {
              "recipient_unresolved_hex": "98CBE94CC1C48E8AD8C562CA874A6CC28EAF687C7FD4C799",
              "mosaics": [],
              "message_hex": "00E3809057726170E99B86E7B484E38091E3808C4149E4BEA1E580A4E58886E69E90E382A2E38397E383AA34E3808D2D3E20E382B3E383B3E38386E3838A20434E542D46413031364436312D433142322D343531462D384231422D453234343642353444393230",
              "plain_text": "\u3010Wrap\u96c6\u7d04\u3011\u300cAI\u4fa1\u5024\u5206\u6790\u30a2\u30d7\u30ea4\u300d-> \u30b3\u30f3\u30c6\u30ca CNT-FA016D61-C1B2-451F-8B1B-E2446B54D920"
            }
          },
          {
            "type": "0x4154",
            "type_name": "TRANSFER",
            "version": 1,
            "network": "0x98",
            "signer": "F42C515D1E146557A9E3B7D3AFF6115A1F0CBAA45FEABF63757EF70387548897",
            "size": 212,
            "transfer": {
              "recipient_unresolved_hex": "98CBE94CC1C48E8AD8C562CA874A6CC28EAF687C7FD4C799",
              "mosaics": [
                {
                  "unresolved_id": "0x2D408A6532372270",
                  "amount_raw": 1
                }
              ],
              "message_hex": "00E3809057726170E99B86E7B484E38091E3808CE4BEA1E580A4E68BA1E5BCB5E382B3E383B3E382B5E383ABE38386E382A3E383B3E382B034E3808D2D3E20E382B3E383B3E38386E3838A20434E542D46413031364436312D433142322D343531462D384231422D453234343642353444393230",
              "plain_text": "\u3010Wrap\u96c6\u7d04\u3011\u300c\u4fa1\u5024\u62e1\u5f35\u30b3\u30f3\u30b5\u30eb\u30c6\u30a3\u30f3\u30b04\u300d-> \u30b3\u30f3\u30c6\u30ca CNT-FA016D61-C1B2-451F-8B1B-E2446B54D920"
            }
          }
        ],
        "cosignatures_count": 2
      }
    }
  ]
}
```

取引を含むブロック高の選択だけ、公開RESTの直近100ブロックのメタ情報を使用した。SDK版サンプルと記事の実行コマンドはP2Pのみ。Aggregate Bonded V3が1件、Embedded Transfer V1が3件、連署2件を確認した。

## 開発用の検証

模擬データはtestsに移動し、読者用の --demo と --file を削除。通信処理は第5回のp2p_common.pyをコピーし、同じSDK依存をrequirements.txtに固定した。

関連テスト15件が成功。Transferの各フィールド、AggregateとEmbeddedの表示差、Mosaicの生値、非UTF8・制御文字、別種別の共通フィールド、Aggregateの複数バージョン、ブロック種別、切断・余分なバイト、不正長とパディング、要求高、TLSとCLIの往復、空応答を検証した。

```bash
PATH=/home/harvestasya/symbol/client/catapult/deps/openssl/bin:$PATH /tmp/symbol-p2p-sdk-venv/bin/python -m unittest discover -s ../../tests/symbol-p2p/06-block-transactions -v
```

記事の2ファイルの全文コードと、実行結果の一致を確認。SDKのAPIはインストールしたsymbolchain.scの実装で照合し、固定コミットのTransferTransaction.hとAggregateTransaction.hでも構造を確認した。
