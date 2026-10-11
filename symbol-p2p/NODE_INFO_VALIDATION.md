# 無料第2・3回：ノード情報パケットの検証記録

記事：`../../articles/symbol-p2p-node-info.md`（第3回）、`../../articles/symbol-p2p-packets-python.md`（第2回）（`published: false`）。サンプル：`node_info.py`、テスト：`test_node_info.py`。第1回のコードとテストは変更していない。第1回記事はテスト対象を明示するコマンドだけ調整した。コミット・push・公開操作は行っていない。

## 一次ソースとの照合

対象は [symbol/symbol の固定コミット dbff03b4096622d1bc1fce611358e05cfa7b0296](https://github.com/symbol/symbol/tree/dbff03b4096622d1bc1fce611358e05cfa7b0296)。以下はリポジトリルートからのパス。

| 確認項目 | 根拠 | 結果 |
| --- | --- | --- |
| Type とヘッダー | `client/catapult/src/catapult/ionet/PacketType.h`、`PacketHeader.h` | Pull Ping = `0x111`、uint32 × 2 = 8 bytes |
| 要求と応答 | `client/catapult/extensions/nodediscovery/src/handlers/NodeDiscoveryHandlers.cpp` | 本文なし要求。ローカル NetworkNode を 1 件返す |
| ノードの配置 | `client/catapult/src/catapult/ionet/NetworkNode.h` | パディングなしの固定部の後に Host と FriendlyName |
| バイト配列の幅 | `client/catapult/src/catapult/types.h` | IdentityKey / GenerationHashSeed は各 32 bytes |
| Version の幅 | `client/catapult/src/catapult/ionet/NodeVersion.h` | uint32 |
| Roles の幅・値 | `client/catapult/src/catapult/ionet/NodeRoles.h` | uint32、Peer = 1。未知ビットを勝手に無効と扱わない |
| ネットワークの幅・値 | `client/catapult/src/catapult/model/NetworkIdentifier.h` | uint8、Testnet = 0x98。デモの seed は架空 |
| 長さとコピー | `client/catapult/src/catapult/ionet/NetworkNode.cpp` | 81 + HostSize + FriendlyNameSize、終端文字を追加せずバイト列をコピー |
| 既存のサイズ検証 | `client/catapult/tests/catapult/ionet/NetworkNodeTests.cpp` | sizeof(NetworkNode) = 81、可変部最大 255 × 2 の計算 |
| Catapult 側の解析 | `client/catapult/extensions/nodediscovery/src/NodePingUtils.cpp` | エンティティ長検証、識別鍵・ネットワークの互換性検査は別の処理 |

第1回と同じ little endian 前提を採用。Python は `<II` / `<II32s32sIHBBB` を明示する。鍵と seed は整数として逆順にしない。構造は文字列の UTF-8 を保証しないため、bytes として保持し、表示時のデコードだけを分ける。

## C++ のレイアウト確認

取得した固定コミットの NetworkNode / Node / 型定義ヘッダーを優先して include し、未取得の utility ヘッダー等は既存のローカル Catapult 開発環境を利用した。構造を Python 側で書き直した模造の C++ struct ではなく、実際の Catapult のヘッダーに対して `sizeof` と `offsetof` を実行した。Catapult サーバー本体や既存の C++ テスト一式を実行した結果ではない。

```text
PacketHeader=8
NetworkNode=81
Size=0
Version=4
IdentityKey=8
NetworkGenerationHashSeed=40
Roles=72
Port=76
NetworkIdentifier=78
HostSize=79
FriendlyNameSize=80
```

この offset は本文先頭からの位置。記事のパケット全体の位置は 8 を足した値。Python の固定部は 81 bytes、デモは Header 8 + 固定部 81 + Host 9 + Name 4 = 102 bytes、NetworkNode.Size は 94。

## 実行検証

Ubuntu 24.04.5 LTS / CPython 3.12.3 / Python が読み込む OpenSSL 3.5.2。証明書生成は CLI とライブラリが一致する OpenSSL 3.5.2 を使用。制作環境の `/usr/bin/openssl` の版の不一致については第1回の `VALIDATION.md` を参照。

通信不要のデモと解析テスト（サンプルのディレクトリ）：

```bash
python3 node_info.py --demo
python3 -m unittest test_node_info.NodeInfoTests -v
```

結果：23 件成功。デモ出力は記事の JSON と一致。

ルートの制作環境から、TLS と第1回の回帰テストも含めて実行したコマンド：

```bash
PATH=/home/harvestasya/symbol/client/catapult/deps/openssl/bin:$PATH \
  python3 -m unittest discover -s zenn/examples/symbol-p2p -v
```

結果：38 件成功（第1回 13、ノード情報 25）。通常の環境ではサンプルのディレクトリで `python3 -m unittest -v` を使う。ノード情報の TLS テストは第1回の証明書セットアップとループバックサーバーを再利用するが、第1回のファイルは編集しない。

| ノード情報の確認範囲 | 結果 |
| --- | --- |
| 固定要求バイト列 | `0800000011010000` と一致 |
| 各フィールドの値 | 手書きの固定パケットを解析し、整数・32 bytes 配列・名前を個別に照合 |
| 固定部・可変部 | 固定部不足、長さフィールドの不整合、ノード長と外側の長さの不一致を拒否 |
| サイズ上限 | 89〜599 bytes。範囲外と別タイプは本文を読む前に拒否 |
| 空・最大長 | Host / Name が空、片方が空、両方 255 bytes を解析 |
| 生のバイト列 | UTF-8 の日本語、不正 UTF-8、NUL、端末制御文字を bytes として保持。JSON は制御文字をエスケープ |
| 分割受信 | 1〜102 bytes 単位で同じ結果。後続パケットを読み込まない |
| 切断 | デモの各位置での切断をオフラインの完全パケット解析とストリーム受信の両方で検査 |
| 期限 | ヘッダー受信後に期限が切れた場合は本文を読まずに失敗 |
| CLI | オフライン JSON 出力、接続時の CA 未指定の拒否、TLS モックへの CLI 取得 |
| TLS 模擬通信 | TLS 1.3 で実際に要求 `0x111` を送信。分割した模擬応答を query() が解析 |

TLS の模擬サーバーは通常の OpenSSL 相互認証を使い、Catapult 本体や独自証明書コールバックを実行しない。固定パケットの往復試験は暗号化経路と受信コードの確認であり、実ノードが同じ値を返したという証拠ではない。

## 自己レビュー

執筆・レビュースキルの観点に従い、完成原稿からフィールド配置、長さ、エンディアン、実行コマンド、表示結果を再照合した。同じ作成者による自己レビューであり、別のレビュアーによる独立レビューではない。

- コードブロックと `node_info.py` の全文一致を確認。
- サンプルのデモ出力と記事の JSON の一致を確認。
- フィールド順・サイズ・境界検査を上記の C++ 定義と照合。
- 応答 Size と NetworkNode.Size を区別し、余分なデータも拒否。
- 599 bytes が汎用のパケット上限であるという誤説明はない。
- 名前は UTF-8 の仕様と断定せず、バイト列を保持。
- 前回の TLS・証明書生成の説明を繰り返さず、必要なファイルと取得手順を明示。
- Zenn 形式、`published: false`、Markdown の描画を確認。

解析の検証範囲で構造定義との不一致は見つからなかった。公開前に必要な実環境の確認は次のとおり。

## 未検証事項と残る懸念

- **実 Catapult への接続**：確認済み CA と既知の稼働ノードがない。実ノードにクライアント証明書が受け入れられること、ハンドラーが有効であること、返された情報の解析は未確認。
- **CA と応答 IdentityKey の一致、期待するネットワークとの一致**：今回は検査しない。TLS の認証から応答内容の正当性を推測しない。監視や自動探索へ発展させる際に必要。
- **Ubuntu 標準の OpenSSL 3.0 系ライブラリと Python 3.13 以降**：未実行。Python 3.12.3 / OpenSSL 3.5.2 の成功を全環境へ一般化しない。
- **接続先の実装版**：固定コミットの構造のみ確認。将来のフィールド追加は現在の厳密な長さ検証では拒否する可能性がある。
- **並列要求・再接続・複数ノード監視**：未実装。今回は 1 接続で 1 要求のみ。返された host に自動接続する処理もない。
- **Catapult を丸ごと用いた統合テスト**：未実施。C++ のサイズ確認はコンパイルしたヘッダーの確認であり、サーバー通信の確認ではない。

## ノード情報取得の記事向けの追加確認

- `client/catapult/extensions/nodediscovery/src/api/RemoteNodeApi.cpp`：本文なし要求、単一 NetworkNode の解析。Pull Peers のメソッドは今回実装しない。
- `client/catapult/src/catapult/ionet/NodeVersion.cpp`：major / minor / revision / build を上位から詰める。0x01020304 → 1.2.3.4 の表示を確認。
- `client/catapult/src/catapult/ionet/NodeRoles.h`：Peer / Api / Voting / IPv4 / IPv6 のフラグを表示。未知ビットを保持。
- `client/rest/src/routes/nodeRoutes.js`：`/node/info` は Pull Ping を送って応答をデコードし、設定由来の nodePublicKey を追加。NetworkNode 自体に nodePublicKey フィールドはない。
- `client/rest/src/sockets/nodeInfoCodec.js`：IdentityKey は REST の publicKey に対応。
- `openapi/spec/core/node/schemas/NodeInfoDTO.yml`：REST のフィールドを照合。REST を呼び出した実測比較ではない。

表示の追加テストはバージョンの 0 / 最大値、複合・未知ロール、既知・未知ネットワークを対象とした。CLI の TLS 取得テストも追加し、モックが受けた要求と出力 JSON を照合した。
