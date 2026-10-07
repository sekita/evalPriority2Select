# evalPriority2Select

`evalPriority2Select.py` は、評価表（tableE）と優先度表（tableP）を Markdown の見出し形式で受け取り、優先度の高い評価項目から順に選択肢を絞り込む選択木を、別プログラムで図へ変換しやすい見出し形式として出力する Python プログラムである。

出力は `heading2diagram.py` などの後段処理へ渡し、Mermaid や PlantUML へ変換することを想定している。中間ノードには `六角;`、枝ラベルには `|評価値|` を用いる。

## 1. フォルダ構成

```text
evalPriority2Select_github/
├── evalPriority2Select.py
├── README.md
├── README_jp.md
├── .gitignore
├── docs/
│   ├── evalTable_format.md
│   ├── priority_format.md
│   ├── selectTree_format.md
│   └── troubleshooting.md
├── examples/
│   ├── evalTable.md
│   ├── priorityA.md
│   ├── priorityB.md
│   ├── OselTreeA.md
│   └── OselTreeB.md
└── tests/
    └── test_examples.py
```

通常の利用では、この README と `docs/` 内の形式ガイドを参照すればよい。

## 2. 必要環境

Python 3 を使用する。実装が使用するのは `argparse`、`os`、`re`、`sys`、`unicodedata` という標準ライブラリのみであり、追加パッケージのインストールは不要である。

入力ファイルは UTF-8（BOM 付きも可）または Shift_JIS（CP932）を受け付ける。出力は常に UTF-8（BOM なし）である。

## 3. 最短の使い方

リポジトリのルートで次を実行する。

```bash
python evalPriority2Select.py \
  --tableE examples/evalTable.md \
  --tableP examples/priorityA.md \
  -o OselTreeA.md
```

標準出力へ出す場合は `-o` / `--output` を省略する。

```bash
python evalPriority2Select.py \
  --tableE examples/evalTable.md \
  --tableP examples/priorityA.md
```

引数は次のとおりである。

| 引数 | 必須 | 内容 |
| --- | --- | --- |
| `--tableE` | 必須 | 評価用見出し形式のファイル |
| `--tableP` | 必須 | 優先度用見出し形式のファイル |
| `-o`, `--output` | 任意 | 出力先。省略時は標準出力 |

成功時の終了コードは `0`、仕様上の入力エラーや出力エラーは `1`、コマンドライン引数の誤りは `argparse` の既定で `2` である。

## 4. 評価表（tableE）の概要

最初の `#` ブロックをヘッダ、その後の `#` ブロックを選択肢として扱う。

```text
# 改善案
## 高効果
## 低導入費用
## 低リスク

# 案A
## ◎
## 〇
## △

# 案B
## 〇
## ◎
## ◎
```

ヘッダの `##` の順番が評価項目の列順であり、各選択肢の `##` は同じ順番で評価値を書く必要がある。

詳細は [docs/evalTable_format.md](docs/evalTable_format.md) を参照する。

## 5. 優先度表（tableP）の概要

最初の `#` ブロックは必ずヘッダとして置く。2番目以降の `#` が順位であり、その直下の最初の `##` に評価項目名を書く。

```text
# 順位
## 評価項目

# 1
## 高効果

# 2
## 低リスク

# 3
## 低導入費用
```

順位は整数として解釈され、数値の昇順で処理される。

詳細は [docs/priority_format.md](docs/priority_format.md) を参照する。

## 6. 評価値の順序

標準では評価値を次の順で枝として出力する。

```text
◎ → 〇 → △ → ×
```

`○` と `◯` は `〇`、`✕`・半角 `x`・半角 `X` は `×`、`▲` は `△` と同じものとして比較する。

上記以外の評価値も使用できる。その場合は既知の4値より後ろに、評価表全体で最初に現れた順で並ぶ。

## 7. 出力形式

出力全体は必ず次の構成になる。

```text
tableE: evalTable.md, tableP: priorityA.md

# 六角;高効果
## |◎|六角;低運用費用
### |◎|AI導入
...
```

1行目は入力ファイル名、2行目は空行、3行目以降が選択木である。1行目は `#` で始まらないため、見出しを読む後段プログラムからはノードとして扱われない想定である。

`examples/OselTreeA.md` と `examples/OselTreeB.md` は、プログラムが実際に出力する先頭2行を含む完全な出力例である。

見出し・枝・葉の厳密な書式は [docs/selectTree_format.md](docs/selectTree_format.md) を参照する。

## 8. サンプル実行

### 優先度A

```bash
python evalPriority2Select.py \
  --tableE examples/evalTable.md \
  --tableP examples/priorityA.md \
  -o examples/OselTreeA.md
```

### 優先度B

```bash
python evalPriority2Select.py \
  --tableE examples/evalTable.md \
  --tableP examples/priorityB.md \
  -o examples/OselTreeB.md
```

同じ評価表でも優先度表を変更すると、選択木の分岐順が変わる。

## 9. テスト

添付例に対する回帰テストを実行できる。

```bash
python -m unittest discover -s tests -v
```

テストでは A/B の両方について、終了コード、標準エラー出力、および生成された完全出力が `examples/OselTreeA.md` / `examples/OselTreeB.md` と一致することを確認する。


## 10. 作成時の重要な注意

見出しとして認識させる `#` は必ず行頭に置く。`#` の前へ空白を置くと、その行は見出しとして使われず警告になる。

評価表では、各選択肢の評価値の個数をヘッダの評価項目数と一致させる。少ない場合はエラー、多い場合は超過分を無視して警告となる。

優先度表では、先頭のヘッダブロックを省略しない。プログラムは最初のブロックを無条件にヘッダとして読み飛ばすためである。

評価項目名は評価表と優先度表で照合される。全角・半角と一部の空白差は正規化されるが、意味の異なる名称は一致しない。

選択肢名・評価項目名・評価値に `|` を含めると、後段の見出し形式で枝ラベルの区切りと衝突する可能性があるため避けるのが安全である。

## 11. 関連資料

- [評価表の作り方](docs/evalTable_format.md)
- [優先度表の作り方](docs/priority_format.md)
- [出力見出し形式](docs/selectTree_format.md)
- [エラー・警告と注意事項](docs/troubleshooting.md)
