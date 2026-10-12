# 第7回の検証

2026年10月12日 14:29 JST。Python 3.12.3 / OpenSSL 3.5.2。既存の共通証明書を再利用して、testnet1.symbol-mikun.net:7900に読み取り専用で3回要求した。CERT_NONE、TLS1.3。Proofの署名と投票重みは検証していない。

```bash
python3 finalization.py testnet1.symbol-mikun.net --port 7900 --stats
```

```json
{
  "epoch": 5273,
  "point": 8,
  "height": 3795264,
  "hash": "73E17EBE8AD7583BF7ED144C0B39FC0FF143AF1B67B0C4EADF166B6EDDD64020"
}
```

```bash
python3 finalization.py testnet1.symbol-mikun.net --port 7900 --proof-height 3795264
```

```json
null
```

```bash
python3 finalization.py testnet1.symbol-mikun.net --port 7900 --proof-epoch 5273
```

```json
{
  "version": 1,
  "epoch": 5273,
  "point": 8,
  "height": 3795264,
  "hash": "73E17EBE8AD7583BF7ED144C0B39FC0FF143AF1B67B0C4EADF166B6EDDD64020",
  "groups": [
    {
      "stage": "precommit",
      "height": 3795264,
      "hashes": [
        "73E17EBE8AD7583BF7ED144C0B39FC0FF143AF1B67B0C4EADF166B6EDDD64020"
      ],
      "signatures_count": 6
    },
    {
      "stage": "prevote",
      "height": 3795248,
      "hashes": [
        "CD71EBC2646F6F5DAB0085E7F1E0231B64978F14AA204D6E9C3573DA998BBD72",
        "7EF2D4AC8931EA63E8FB54726F4792C0B96A9C3C5DE8DC2928F41F0569BB5B21",
        "2C8C79012E855D136FB8FCE189B6496115CFF58206B5EF51ADC9EAC9ACA56BCA",
        "19992C688A3C66F9C986050FBD4DFA6F86B61C2ABA47B58E2B276BF2910A33F6",
        "06DB38B42ECE657E1FC0B5352CE9822118C579190EAB5C02150288AEBA6B23DF",
        "49D3F576D1FB6CEC3D972F74A551AE0AD0824D4B693422CD37AC1B8B7442A1CA",
        "4BCD4B4644FFF6E50F1D60F4CAEF121ECFF7A013E7499DF10570AA2B39E62EC0",
        "C36CE5F2967619E48A90F8A4576BDDA7AA173D656FD33D8588D96966BDDDBDA9",
        "B6F39E97B28EE4A5D4788F9D34E10B35B1D87EBCDECF6084CB875786A70EE23C",
        "2F1E014114452A979D4E3CF86B024B8EDA77D86EE8FDEA6CB4800339E08B7783",
        "8DFA0A6D63543D46D2E91B9BDDD340D34A7F16B34BEABC8128396FD7BC8EA29D",
        "646C27B5B76915AA038455723A216F7C533E2BA8FE907B562A1BC119F00E11A5",
        "8BFD1C9B0AE72ABB84362C079B0C2FFB521D15DCC2B7EA700E2E71A41C9BB46F",
        "6301B1A6D46446744EA56A92C7FEB64B2B6A5E3C5EFA90A7D26AD188CCAB509F",
        "A956655792E3C6F4B3C6683DDE408D99C46A057DE4DFE02BF4CDF1AABC9C5B63",
        "41BF61294440E0D49E399F9949F38EF75D92E3996F7D3B993B39211B25F1E6C2",
        "73E17EBE8AD7583BF7ED144C0B39FC0FF143AF1B67B0C4EADF166B6EDDD64020"
      ],
      "signatures_count": 6
    }
  ]
}
```

統計とエポック指定のProofは高さ3795264と同じハッシュを示した。高さ指定は空応答。理由は調査しておらず、空応答を未確定と解釈しない。固定コミットと実ノード実装版の一致は未確認。

## 開発用テスト

16件が成功。要求バイト、統計の48バイト、Proofとグループ境界・長さ・バージョン・ステージ、署名とハッシュ件数、空応答、要求値の照合、受信上限、3種類の要求のローカルTLS通信、CLIを検証した。

```bash
PATH=/home/harvestasya/symbol/client/catapult/deps/openssl/bin:$PATH python3 -m unittest discover -s ../../tests/symbol-p2p/07-finalization -v
```

模擬パケットとローカルTLSサーバーはtests配下に配置。読者用CLIの--demoと--peer-caを削除、位置引数のHOSTに統一。TLS設定は第5・6回と同じp2p_common.pyにまとめ、chain_statistics.pyを削除。SDK3.3.2には完全なFinalizationProofモデルがないことを確認し、Proofと統計の解析にはstructを使用した。

記事の2ファイルの掲載コードと実ファイル、実出力との一致を確認。固定コミットのProofHandlers.cppとFinalizationMessageGroup.hで構造と空応答を照合した。
