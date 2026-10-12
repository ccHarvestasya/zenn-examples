# 第9回の検証

2026年10月12日 14:53 JST。Python 3.12.3 / OpenSSL 3.5.2。

共通証明書を再利用し、testnet1.symbol-mikun.net:7900へPull Pingを1回送った。鍵ログは一時ディレクトリに作成して、内容を表示せず検証後に削除。TLS1.3、CERT_NONE。

```bash
python3 capture_peer.py testnet1.symbol-mikun.net --port 7900 --keylog <一時ディレクトリ>/peer.keylog
```

```json
{
  "tls": "TLSv1.3",
  "cipher": "TLS_AES_256_GCM_SHA384",
  "request_hex": "08 00 00 00 11 01 00 00",
  "response_header_hex": "7d 00 00 00 11 01 00 00",
  "response_size": 125,
  "node_size": 117,
  "keylog_enabled": true
}
```

鍵ログは992バイト、権限0600。実際の鍵値は検証記録に含めない。制作環境にはWireshark、dumpcap、tsharkがなく、キャプチャ、GUI操作、復号は未検証。記事に掲載した復号後の照合対象はPythonで受信したヘッダー・長さから得た値であり、pcapから読み取った値ではない。

## 開発用の検証

9件が成功。鍵ログの新規作成と権限、既存・symlinkパス拒否、分割受信、途中切断、既定CLI、鍵ログの有無、応答タイプと全長、NetworkNode長、ローカルTLSによるCLIのメタ情報を確認した。

```bash
PATH=/home/harvestasya/symbol/client/catapult/deps/openssl/bin:$PATH python3 -m unittest discover -s ../../tests/symbol-p2p/09-wireshark -v
```

読者用のローカル模擬サーバーcapture_lab.pyとその依存ファイルを削除し、単一のcapture_peer.pyに置き換えた。固定パケットとTLSサーバーは開発用テストに配置した。記事の全文コードと実ファイル、実出力との一致を確認した。

WiresharkのTLS公式wiki、dumpcapマニュアル、Python SSLContext.keylog_filenameの公式説明で、鍵ログ・フィルター・復号設定を照合した。実際のキャプチャ例は捏造していない。

## 実ノードとの通信のキャプチャと復号

2026年10月12日 15:47 JST に追加検証。TShark / Dumpcap (Wireshark) 4.2.2、Ubuntu 4.2.2-1.1build3、Python 3.12.3 / OpenSSL 3.5.2。

Ubuntu パッケージを /tmp に展開。通常ユーザーでホスト側のキャプチャ権限がないため、自分専用の user/network/mount namespace を作り、slirp4netns で外部通信を接続した。模擬サーバーは使用せず、共通証明書を使って testnet1.symbol-mikun.net:7900 へ Pull Ping を1回送信した。名前解決にはホスト側で取得した接続先 IP の一時 hosts を、その namespace 内だけで使用。システムの設定変更や sudo によるインストールは行っていない。

dumpcap -i any、host testnet1.symbol-mikun.net and tcp port 7900 のフィルターで、接続開始前から12秒間キャプチャした。19パケットを取得、ドロップ0。読者手順の60秒は、別ターミナルでの実行時間を確保するための値であり、検証では12秒とした。

同じ実行のキャプチャと鍵ログを、以下の指定で TShark に読み込んだ。

```bash
tshark -r peer.pcapng -d tcp.port==7900,tls \
  -o tls.keylog_file:peer.keylog -q -z follow,tls,raw,0
```

復号結果:

```text
===================================================================
Follow: tls,raw
Filter: tcp.stream eq 0
Node 0: 161.97.163.38:7900
Node 1: 10.0.2.100:50524
	0800000011010000
7d00000011010000
750000000903000107b29046e1e45b5162319ea40e271a8ecc1073c73f6881af528895ae3685856f49d6e1ce276a85b70eafe52349aacca389302e7a9754bcf1221e79494fc665a407000000dc1e98190b746573746e6574312e73796d626f6c2d6d696b756e2e6e65746d696b756e5f7465737431
===================================================================
```

方向ごとの16進行を連結してバイト列へ変換し、要求8バイト、応答125バイト、Type 0x111、NetworkNode 117バイトを確認。Python の request_hex / response_header_hex / response_size / node_size と一致。鍵ログを指定しない対照では、TLS アプリケーションの平文行は0件。GUI 操作は未検証。

秘密情報を含む鍵ログとキャプチャは、照合と公開可能な結果の記録後に削除。この記事・リポジトリには鍵ログやキャプチャを追加していない。
