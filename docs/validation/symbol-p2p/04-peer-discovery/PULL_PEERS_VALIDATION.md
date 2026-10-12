# 第4回 Pull Peers の検証

2026-10-12 10:56 JST、Python 3.12.3 / Python が利用する OpenSSL 3.5.2。

`04-peer-discovery/` で以下を1回実行し、14件の候補を取得した。第1〜3回と同じ `common/cert/` のクライアント証明書と秘密鍵を再利用。接続先検証は `CERT_NONE`。候補への接続は実施していない。

```bash
python3 pull_peers.py testnet1.symbol-mikun.net --port 7900
```

```text
peer candidates: 14
{"host": "46.250.248.67", "port": 7901, "roles": ["Peer", "API"], "network": "Testnet", "key_prefix": "598DDD4C5E9BF6A0"}
{"host": "3.113.237.186", "port": 7900, "roles": ["Peer", "API"], "network": "Testnet", "key_prefix": "22F62745DF1B3E34"}
{"host": "001-sai-dual.symboltest.net", "port": 7900, "roles": ["Peer", "API", "Voting"], "network": "Testnet", "key_prefix": "07D38BAE29464C1F"}
{"host": "401-sai-dual.symboltest.net", "port": 7900, "roles": ["Peer", "API", "Voting"], "network": "Testnet", "key_prefix": "C1773740461C97FF"}
{"host": "201-sai-dual.symboltest.net", "port": 7900, "roles": ["Peer", "API"], "network": "Testnet", "key_prefix": "645E2E56B5F8680B"}
{"host": "13.115.208.50", "port": 7900, "roles": ["Peer", "API"], "network": "Testnet", "key_prefix": "119C3736D185D00A"}
{"host": "spv.dusanjp.com", "port": 7900, "roles": ["Peer", "API", "Voting"], "network": "Testnet", "key_prefix": "F099AB5ADF1920E7"}
{"host": "20.48.92.124 # Use your domain or IP address", "port": 7900, "roles": ["Peer", "API"], "network": "Testnet", "key_prefix": "8F9A40918AF946D4"}
{"host": "testnet2.symbol-mikun.net", "port": 7900, "roles": ["Peer", "API"], "network": "Testnet", "key_prefix": "D20C4BFCE4AA22D8"}
{"host": "t.sakia.harvestasya.com", "port": 7950, "roles": ["Peer", "API", "Voting"], "network": "Testnet", "key_prefix": "B502FCBDA9147ABD"}
{"host": "sym-test-03.opening-line.jp", "port": 7900, "roles": ["Peer", "API"], "network": "Testnet", "key_prefix": "3809A332F423B78E"}
{"host": "symbol-azure.0009.co", "port": 7900, "roles": ["Peer", "API"], "network": "Testnet", "key_prefix": "CC1287250B978C06"}
{"host": "2.dusanjp.com", "port": 7900, "roles": ["Peer", "API", "Voting"], "network": "Testnet", "key_prefix": "8A66BDB319C210B5"}
{"host": "sym-test-01.opening-line.jp", "port": 7900, "roles": ["Peer", "API"], "network": "Testnet", "key_prefix": "69080A34AE5AC693"}
```

公開ノードの応答は取得時点のもの。表示に含まれる不正なホスト文字列も補正せず掲載した。

## 開発用の検証

`--demo`、`--host`、`--peer-ca` を削除し、位置引数の接続先と共通証明書のCLIに統一。チェーン統計コードを削除し、`node_info.py` には必要なTLS・受信処理とNetworkNodeパーサーだけを残した。固定パケットとローカルTLSサーバーは読者用ディレクトリには含めない。

16件のテストが成功。0件・複数件の応答、不正なレコード長と文字列長、端数、外側の長さ・種別・上限、分割受信、途中切断、タイムアウト、TLS 1.3の往復、位置引数CLIの出力を検証した。

```bash
PATH=/home/harvestasya/symbol/client/catapult/deps/openssl/bin:$PATH python3 -m unittest discover -s ../../tests/symbol-p2p/04-peer-discovery -v
```

ソースの照合先は記事に記載した固定コミット `dbff03b4096622d1bc1fce611358e05cfa7b0296`。NodeDiscoveryHandlers.cppのバッチ生成、HandlerFactory.hの空応答、nodePeersCodec.jsの連続レコード解析を確認した。

## サンプルの単一ファイル化

TLS・受信処理とNetworkNodeパーサーを `pull_peers.py` にまとめ、依存先の `node_info.py` を削除した。記事の全文コードとREADMEを更新し、関連テスト16件が成功。
