# 開発者向けの検証

記事の読者向けコードは `../symbol-p2p/` にあります。このディレクトリは、サンプルを変更する開発者向けです。

第5・6回の検証には Symbol SDK が必要です。リポジトリルートで仮想環境を作り、依存をインストールしてから実行します。

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r symbol-p2p/05-block-fetch/requirements.txt
python3 tests/run_tests.py
```

各回のコードを別の Python プロセスで読み込み、テストを実行します。TLS テストには OpenSSL CLI とループバック通信が必要です。鍵は一時ディレクトリ内で生成・削除します。検証記録は `../docs/validation/symbol-p2p/` にあります。
