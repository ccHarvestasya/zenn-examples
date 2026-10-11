# 無料第1回：技術検証結果と未検証事項

この文書は CA ファイルを使う実装の過去の検証記録です。現在の第1回の学習用コードは、[第1回の検証記録](../01-connect/DEMO_VALIDATION.md) を参照してください。

対象：[第1回の旧稿](https://github.com/ccHarvestasya/zenn/blob/main/articles/symbol-p2p-01-connect.md) と、このディレクトリの無料サンプル。記事は `published: false`。公開・配布操作は行っていない。

## 確認した仕様

調査コミット：[`symbol/symbol@dbff03b4096622d1bc1fce611358e05cfa7b0296`](https://github.com/symbol/symbol/tree/dbff03b4096622d1bc1fce611358e05cfa7b0296)。実ノードの稼働版との一致は未確認。

以下のパスは `client/catapult/` からの相対パス。

| 確認事項 | 結果 | 一次ソース |
| --- | --- | --- |
| パケットタイプ | `Chain_Statistics = 5` | `src/catapult/ionet/PacketType.h` |
| 共通ヘッダー | Size と Type は uint32、全体 8 バイト。Size はヘッダーを含む | `ionet/PacketHeader.h` |
| 要求 | 本文なし、全体 8 バイト | `api/RemoteChainApi.cpp`、`handlers/ChainHandlers.cpp` |
| 応答 | Header + Height + FinalizedHeight + ScoreHigh + ScoreLow。後ろの 4 フィールドは各 8 バイト、全体 40 バイト | `api/ChainPackets.h`、`handlers/ChainHandlers.cpp` |
| バイト順 | Catapult は little endian 環境が前提。構造をパディングなしで転送。Python は `<II` と `<QQQQ` を指定 | `docs/README.md`、`ionet/PacketHeader.h`、`api/ChainPackets.h` |
| スコア | 上位と下位の 64 ビットから `(high << 64) \| low` で復元 | `api/RemoteChainApi.cpp`、`model/ChainScore.h` |
| 待ち受け | 標準設定は 7900。運用設定で変わる | `resources/config-node.properties` |
| TLS | TLS 1.3、鍵交換のグループは X25519、相互証明書検証 | `ionet/PacketSocketOptions.cpp`、`ionet/PacketSocket.cpp` |
| Symbol 証明書 | 2 枚チェーン、Ed25519 公開鍵を検査。自己署名 CA の例外処理で自己署名を検証し、CA 公開鍵をノード識別に使う | `crypto/CatapultCertificateProcessor.cpp`、`crypto/CertificateUtils.cpp`、`ionet/PacketSocketOptions.cpp` |
| REST 比較 | 通常の `/chain/info` は MongoDB の統計と最新確定ブロックを取得 | `client/rest/src/routes/chainRoutes.js`（リポジトリルートから）、ローカル OpenAPI の ChainInfoDTO |

[公式のノード構成説明](https://docs.symbol.dev/concepts/node.html)も確認。手元の `docs/knowledge/symbol-technicalref-jp.pdf` の 12.2 にある X25519 証明書の表記は、実装の Ed25519 検査と異なるため、現行ソースを優先した。

## 無料コードの設計範囲

`make_request()`、`recv_exact()`、`read_statistics()`、`make_context()`、`query()` に責務を分け、CLI を `main()` に置く。将来の共通化の出発点として使えるが、現在は Chain Statistics 専用の 1 回の問い合わせに限定する。将来の有料ライブラリへの依存、未実装の import、SDK、REST 呼び出しはない。

信頼した接続先 CA だけをロードし、`CERT_REQUIRED` で署名チェーンと有効期間などを検証する。ホスト名照合は使わない。CA 入手時の信頼が必要であり、DNS 名との対応、同じ CA による別の通信証明書の区別、接続先のチェーン情報の正当性は保証しない。Catapult 独自のチェーン枚数・鍵型検査を Python 側が完全再現するものではない。

## 実行検証

- OS：Ubuntu 24.04.5 LTS。
- Python：CPython 3.12.3。
- Python の TLS ライブラリ：OpenSSL 3.5.2。
- 証明書生成：CLI とライブラリの版が一致する OpenSSL 3.5.2。

制作環境の `/usr/bin/openssl` は CLI 3.0.13 / ライブラリ 3.5.2 という組み合わせで、`req` が SIGSEGV になった。以下では既存の Catapult 開発環境の OpenSSL を PATH に指定した。このパス指定は制作環境用であり、読者の Ubuntu で必要となる一般的な手順ではない。

ワークスペースルートから実行：

```bash
PATH=/home/harvestasya/symbol/client/catapult/deps/openssl/bin:$PATH \
  python3 zenn/examples/tests/run_tests.py
```

サンプルのディレクトリでの通常のコマンド：

```bash
python3 -m unittest -v
```

**結果：13 件成功。**

| テスト範囲 | 確認内容 |
| --- | --- |
| 要求生成 | `08 00 00 00 05 00 00 00` の固定バイト列と一致 |
| 分割・結合 | 1〜40 バイト単位の受信で同じ値。後続パケットを読み込まない |
| 切断 | 0〜39 バイトの各位置で切断すると例外 |
| 異常応答 | サイズ 0 / 7 / 8 / 39 / 41 / uint32 最大、違うタイプを拒否。本文を読む前に停止 |
| 整数 | 非ゼロのスコア上位・下位と、uint128 最大値を精度損失なく復元 |
| タイムアウト | ソケットのタイムアウトと、分割受信で延長されない全体の期限 |
| TLS と CLI | 独立したクライアント/サーバー CA、TLS 1.3、要求受信、CLI の終了コードと出力 |
| 認証の否定テスト | 接続先 CA が違う、クライアント証明書がない場合は統計要求の受信に至らない |
| CLI の失敗 | 存在しない CA ファイルは終了コード 1、不正ポートは 2 |

TLS テストで観測した出力：

```text
chain height: 123
finalized height: 120
chain score: 18446744073709551618
```

これは模擬サーバーの固定データ。実ノードの観測値ではない。テストの秘密鍵は一時ディレクトリで生成・削除する。実行する Python はテストを起動した `sys.executable` を使う。

## 未検証事項と、次に確認する条件

| 未検証事項 | 理由・確認条件 |
| --- | --- |
| 実 Catapult との統計取得 | 既知の稼働ノードと信頼済み CA を用意していない。自前 Testnet / 私設網でサーバーの版、設定、CA、期待する統計値を固定して確認する |
| Catapult による生成証明書の受け入れ | 通常の OpenSSL モックは独自検証コールバックを再現しない。実 Catapult のログと成功応答で確認する |
| Ubuntu 標準の OpenSSL 3.0.13 ライブラリ | 制作環境は別のライブラリを読み込んでいる。クリーンな Ubuntu 24.04 で証明書生成から通信まで確認する |
| Python 3.13 以降 | 今回は 3.12.3 のみ実行。対象の版で SSLContext と証明書の組み合わせを確認する |
| 有効期限切れ・改ざん証明書の否定テスト | 今回の TLS テストは異なる CA と証明書なしを対象にした。期限と改ざんを分けた追加データで確認する |
| 再接続・接続再利用・同時要求 | 無料版には実装しない。共通ヘッダーに要求 ID はないため、並列の応答対応を推測で実装しない |
| Node Discovery・ブロック取得 | タイプとハンドラー、構造定義の存在を確認。Python の実装、解析テスト、実ノードへの要求は未実施 |

未認証で取り出した公開ノードの CA を自動的に信頼する操作は行っていない。実ノードの確認なしに「動作確認済み」と書かない。

## 発展候補の調査結果

同じ固定コミットで追加確認したもの：

- `PacketType.h`：Pull Ping `0x111`、Pull Peers `0x113`、Pull Block `4`、Pull Blocks `8`。
- `extensions/nodediscovery/src/handlers/NodeDiscoveryHandlers.cpp`：Pull Ping はローカルの NetworkNode、Pull Peers はノード集合を返すハンドラー。
- `ionet/NetworkNode.h` / `.cpp`：固定フィールドの後に HostSize / FriendlyNameSize に対応する可変長データを置く。
- `extensions/nodediscovery/src/NodePingUtils.cpp`：エンティティ長の検査、ネットワーク識別と identity key の照合。
- `api/ChainPackets.h`：Pull Block 要求は 16 バイト、Pull Blocks 要求は 24 バイト。
- `handlers/ChainHandlers.cpp` と `model/Block.h`：ブロック読み出しと型によって異なるヘッダー/フッターの定義。

これらは続編の採否を判断する根拠であり、有料版の完成機能の一覧ではない。企画書や有料版専用の本文・コードは公開サンプルに含めない。
