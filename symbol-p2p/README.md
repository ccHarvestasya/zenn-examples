# Symbol P2P 通信：無料サンプル

原稿：[REST API を使わずに Symbol ノードと通信する](../../articles/symbol-p2p-python.md)。コードと証明書生成手順は記事にも全文掲載。

| ファイル | 役割 |
| --- | --- |
| `chain_statistics.py` | 標準ライブラリで、認証付き TLS 接続から Chain Statistics を 1 回取得 |
| `generate_certificates.sh` | 検証用のランダムな Ed25519 証明書を生成。既存の `cert` は上書きしない |
| `test_chain_statistics.py` | 第1回：バイナリ処理、CLI の失敗、ローカル TLS 通信を検証 |
| `node_info.py` | 第2・3回：Pull Ping の生成、ノード情報解析、デモと TLS 取得 |
| `test_node_info.py` | 第2・3回：可変長データの境界、途中切断、ローカル TLS 取得を検証 |
| [NODE_INFO_VALIDATION.md](NODE_INFO_VALIDATION.md) | ノード情報のソースとの照合、検証結果、未検証事項 |
| [VALIDATION.md](VALIDATION.md) | 確認した仕様、検証環境、実行結果、未検証事項 |

## 実行

新しい作業ディレクトリに Python とシェルの 2 ファイルを保存する。Ubuntu 24.04、Python 3.12 以上、OpenSSL コマンドが必要。pip の追加パッケージや有料版コードは不要。

```bash
bash generate_certificates.sh
```

接続先の運用者から信頼できる経路で得た CA を `peer-ca.crt.pem` に保存し、別経路で得た指紋と照合する。自分自身の `cert/ca.crt.pem` と接続先の CA は別物。詳細は記事を参照。

```bash
openssl x509 -in peer-ca.crt.pem -noout -dates -fingerprint -sha256
openssl verify -check_ss_sig -CAfile peer-ca.crt.pem peer-ca.crt.pem
python3 chain_statistics.py YOUR_NODE_HOST --port 7900 --peer-ca peer-ca.crt.pem
```

`YOUR_NODE_HOST` は、その CA に対応する自分のノードまたは公開ノードのホスト名/IP に置き換える。CA を未認証の通信から自動的に取得・信頼する処理はない。

## テスト

このディレクトリで実行する。ローカル TCP ソケットと OpenSSL CLI が必要。テスト自身が一時ディレクトリに証明書を生成するので、接続先の設定も実ノードも不要。

```bash
python3 -m unittest -v
```

第1回 13 件、ノード情報 25 件、合計 38 件成功。実 Catapult 通信、Ubuntu 標準の OpenSSL ライブラリ、Python 3.13 以降は未検証。TLS モックは Catapult 独自の認証を再現しない。詳細と制作環境用のコマンドは [検証記録](VALIDATION.md)に記載。

鍵、証明書、接続先の設定は Git に追加しない。将来の共通化を考え、パケット生成・受信・解析・TLS 設定・CLI を分けているが、無料サンプルは単独で動作する。

## 第2・3回：Node Discovery Pull Ping

[第2回のパケット解説](../../articles/symbol-p2p-packets-python.md)／[第3回の情報取得](../../articles/symbol-p2p-node-info.md)。同じディレクトリの `chain_statistics.py` の受信・TLS 設定を再利用する。第1回の実装を変更せず、`node_info.py` とテストを追加した。

```bash
python3 node_info.py --demo
python3 -m unittest test_node_info.NodeInfoTests -v
```

上記は通信せず、模擬データを解析する。証明書とネットワーク接続は不要。ノード情報だけの TLS 模擬通信も含める場合は `python3 -m unittest test_node_info -v`。

接続先の確認済み CA とクライアント証明書を用意した場合の書式：

```bash
python3 node_info.py --host YOUR_NODE_HOST --port 7900 \
  --peer-ca peer-ca.crt.pem --cert cert/node.full.crt.pem --key cert/node.key.pem
```

実 Catapult 接続は未検証。取得した公開鍵と CA 公開鍵、ネットワーク情報と期待するネットワークの一致の検査は実装していない。解析成功をノード情報の信頼性の証明とは扱わない。
