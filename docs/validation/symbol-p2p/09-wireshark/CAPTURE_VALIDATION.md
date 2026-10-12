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
