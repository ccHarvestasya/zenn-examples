# 第5回 Pull Block の検証

2026-10-12 13:35 JST、Python 3.12.3 / Python が利用する OpenSSL 3.5.2。

`05-block-fetch/` で、既存の `common/cert/` のクライアント証明書と秘密鍵を再利用して、読み取り専用の要求を1回送信した。Python 側の接続先証明書検証は `CERT_NONE`。ブロックの署名・VRF・TransactionsHash・チェーンの合意は検証していない。

```bash
python3 pull_block.py testnet1.symbol-mikun.net --port 7900 --height 0
```

```json
{
  "size": 376,
  "version": 1,
  "network": 152,
  "type": 33091,
  "signature": "2B5FA18186CFD7B3468B50D39196F905C4BE7D9D8C9C47EF41502F0FA0259219633FCBF0952AFBA15F162452910461E1A3D56E94C761EB9726D4892B8BD88F05",
  "signer": "3DF6B81E7F3A6A0770F75B0033F210EAA040A55F399601A11C7BEDCF10BE4B12",
  "height": 3795183,
  "timestamp_ms_since_network_epoch": 124529250383,
  "difficulty": 12620785567943,
  "computed_hash": "6EA9BD0B4FF7EEF435AC0BBEF93915B0CACD40471C4E2F87F44C06C138413403",
  "previous_block_hash": "3930774523F4F7990D09A9CA94F5FF590596C3003404DADE41818FB69245C927",
  "transactions_hash": "0000000000000000000000000000000000000000000000000000000000000000",
  "transactions": []
}
```

最新高として3795183、Normalブロック376バイトを取得した。トランザクションは0件。値は取得時点のもの。

## 開発用の検証

位置引数HOST、共通証明書、`CERT_NONE` のCLIに統一。`chain_statistics.py` を削除し、TLSと受信処理を `p2p_common.py` に移した。模擬データ生成の `fixture_data.py` は開発用テストに移動し、読者向けCLIの `--file` と `--peer-ca` を削除した。

関連テスト17件が成功。3種類のブロックヘッダー、切断位置、要求高、取引境界とパディング、ハッシュ範囲、上限付き受信、分割受信、空応答、ローカルTLS接続とCLI出力を検証した。

```bash
PATH=/home/harvestasya/symbol/client/catapult/deps/openssl/bin:$PATH python3 -m unittest discover -s ../../tests/symbol-p2p/05-block-fetch -v
```

記事と掲載した3ファイルのコードの一致、実際の出力との一致、両リポジトリの `git diff --check` を確認した。

固定コミット `dbff03b4096622d1bc1fce611358e05cfa7b0296` の ChainHandlers.cpp / HeightRequestProcessor.h で高さ0の扱いと空応答、Block.cpp / EntityHasher.cpp でブロック種別ごとのヘッダー・ハッシュ範囲を照合した。実ノードの実装版との一致は未確認。

## SDK による解析への変更

2026年10月12日 13:49 JST、Python 3.12.3 / OpenSSL 3.5.2 / symbol-sdk-python 3.3.2。SDK を一時仮想環境にインストールして検証。

`sc.BlockFactory.deserialize()` に P2P 共通ヘッダーを除いた本文を渡し、復元後に `serialize()` との一致と要求高を確認する構成に変更。手書きのエンティティパーサー `entities.py` とブロックハッシュ計算を削除。SDK のモデルから JSON 用の値を取り出す。署名・VRF・TransactionsHash・チェーンの合意の検証は実施していない。

SDK版の同じCLIで最新高を1回取得した。

```json
{
  "size": 376,
  "version": 1,
  "network": 152,
  "type": 33091,
  "type_name": "NORMAL",
  "signature": "6C651538D39A0A84A353E59606C9A1CC6EA14AEC03A0E4FB33A9D5173F8C7D639079D2D78CB3DBC39337454DD4BF4A5B60D4DA6579709774EC40075D46C35907",
  "signer": "36EAF65AFA6805A2CFE768492F699130182E079D9ACD9B4C9A52827172159EB2",
  "height": 3795211,
  "timestamp_ms_since_network_epoch": 124530123841,
  "difficulty": 12869534042914,
  "previous_block_hash": "D5F0E7867C3CE1B354203FB7732E6ECFF9BEC3792AFA26DC8FAF14C4FF46838D",
  "transactions_hash": "0000000000000000000000000000000000000000000000000000000000000000",
  "transactions": []
}
```

関連テスト17件が成功。Normal / Nemesis / Importance、壊れた長さ・予約領域・バージョン、ヘッダー不足、要求高不一致、トランザクション境界、余分なバイト、上限付き受信とローカルTLS/CLIの往復を確認した。

```bash
PATH=/home/harvestasya/symbol/client/catapult/deps/openssl/bin:$PATH /tmp/symbol-p2p-sdk-venv/bin/python -m unittest discover -s ../../tests/symbol-p2p/05-block-fetch -v
```

SDK API はインストールしたパッケージの `symbolchain.sc` の BlockFactory / Block / NormalBlockV1 の実装で確認。記事の2ファイルの全文コードと実ファイル、出力例と実行結果の一致を確認した。
