#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""評価用見出し形式(tableEval)と優先度用見出し形式(tablePri)から、
ダイアグラム生成用の見出し形式(selectFlow)を生成する。

使用例:
    python evalPriority2Select.py --tableE tableEval.md --tableP tablePri.md --output selectFlow.md
    python evalPriority2Select.py --tableE tableEval.md --tableP tablePri.md -o selectFlow.md

入力ファイルは UTF-8（BOM 付きも可）または Shift_JIS（CP932）で読み込む。
出力は常に UTF-8（BOM なし）である。
"""

import argparse
import os
import re
import sys
import unicodedata

# --------------------------------------------------------------------------
# 定数
# --------------------------------------------------------------------------

# 評価値のソート順（良い順）。値が小さいほど先に出力される。
valueRankTable = {
    "◎": 0,
    "〇": 1,
    "△": 2,
    "×": 3,
}

# 正規化の前に適用する異体字の別名変換表。
valueAliasTable = {
    "○": "〇",   # U+25CB
    "◯": "〇",   # U+25EF
    "✕": "×",    # U+2715
    "x": "×",
    "X": "×",
    "▲": "△",
}

# 中間ノードに付与する形状指定。
shapePrefix = "六角;"

# 葉ノードで複数の選択肢を列挙するときの区切り。
# バックスラッシュ + n の2文字であり、実際の改行文字ではない。
choiceSeparator = "、\\n"

headingPattern = re.compile(r"^(#+)\s*(.*)$")

# 入力ファイルの文字コード。先頭から順に試し、最初に解読できたものを採用する。
# utf-8-sig は先頭の BOM を除去する（BOM がなければ通常の UTF-8 と同じ）。
inputEncodingList = ("utf-8-sig", "cp932")

# 出力の1行目に書く入力ファイル名の行。# で始めないので見出しにはならない。
sourceLineFormat = "tableE: {tableEName}, tableP: {tablePName}"


# --------------------------------------------------------------------------
# エラー
# --------------------------------------------------------------------------


class SpecError(Exception):
    """仕様上の入力エラー。メッセージを表示して終了コード1で終える。"""


def printWarning(message):
    print("警告: " + message, file=sys.stderr)


# --------------------------------------------------------------------------
# 正規化
# --------------------------------------------------------------------------


def normalizeText(text):
    """比較・照合用のキーを生成する。

    全角/半角の違い、スペースの有無、評価記号の異体字を吸収する。
    出力に書き出す文字列にはこの結果を使わない。
    """
    converted = "".join(valueAliasTable.get(ch, ch) for ch in text)
    normalized = unicodedata.normalize("NFKC", converted)
    for space in (" ", "\u3000", "\t"):
        normalized = normalized.replace(space, "")
    return normalized.strip()


# --------------------------------------------------------------------------
# 見出し形式の解析
# --------------------------------------------------------------------------


class HeadingBlock(object):
    """レベル1の見出しと、それに属するレベル2の見出しのまとまり。"""

    def __init__(self, title, lineNumber):
        self.title = title
        self.lineNumber = lineNumber
        self.childList = []          # レベル2のテキスト
        self.childLineList = []      # 対応する行番号


def readTextFile(path):
    """ファイルを読み、inputEncodingList の順に解読を試みた文字列を返す。

    BOM 付き UTF-8 の BOM は除去される。どの文字コードでも解読できなければ SpecError。
    """
    try:
        with open(path, "rb") as inputFile:
            rawData = inputFile.read()
    except OSError as error:
        raise SpecError("ファイル「%s」を読み込めない。\n  %s" % (path, error))

    for encodingName in inputEncodingList:
        try:
            return rawData.decode(encodingName)
        except UnicodeDecodeError:
            continue
    raise SpecError(
        "ファイル「%s」の文字コードを判別できない。\n"
        "  UTF-8 としても Shift_JIS（CP932）としても読み込めなかった。\n"
        "  UTF-8 または Shift_JIS で保存し直す必要がある。" % path)


def parseHeadingFile(path):
    """見出し形式のファイルを読み、HeadingBlock のリストを返す。

    行頭に # のない行は無視する。ただし、行頭の空白を除くと # で始まる行は、
    見出しの書き誤りの可能性が高いため警告を出す（行自体は無視する）。
    """
    lineList = readTextFile(path).splitlines()

    blockList = []
    for lineNumber, rawLine in enumerate(lineList, start=1):
        matched = headingPattern.match(rawLine.rstrip())
        if matched is None:
            # 行頭に # のない行は無視する
            if rawLine.lstrip().startswith("#"):
                printWarning(
                    "%s の %d 行目: 行頭に空白があるため見出しとして扱わず無視した。"
                    "見出しにするには行頭の空白を削除する。" % (path, lineNumber))
            continue
        level = len(matched.group(1))
        text = matched.group(2).strip()
        if level == 1:
            blockList.append(HeadingBlock(text, lineNumber))
        elif level == 2:
            if not blockList:
                printWarning(
                    "%s の %d 行目: 対応する # のない ## を無視した。" % (path, lineNumber))
                continue
            blockList[-1].childList.append(text)
            blockList[-1].childLineList.append(lineNumber)
        else:
            printWarning(
                "%s の %d 行目: レベル%d の見出しは想定外のため無視した。"
                % (path, lineNumber, level))
    return blockList


# --------------------------------------------------------------------------
# tableE / tableP の読み取り
# --------------------------------------------------------------------------


class DataRow(object):
    """tableE のデータ行（＝1つの選択肢）。"""

    def __init__(self, choiceName, valueList, rowIndex):
        self.choiceName = choiceName
        self.valueList = valueList
        self.rowIndex = rowIndex


class TableA(object):
    def __init__(self, criterionNameList, dataRowList):
        self.criterionNameList = criterionNameList
        self.dataRowList = dataRowList
        # 正規化した評価項目名 -> 列番号
        self.columnIndexMap = {}
        for columnIndex, criterionName in enumerate(criterionNameList):
            self.columnIndexMap.setdefault(normalizeText(criterionName), columnIndex)
        # 正規化した評価値 -> (初出順, 原文)
        self.valueDisplayMap = {}
        for dataRow in dataRowList:
            for value in dataRow.valueList:
                valueKey = normalizeText(value)
                if valueKey not in self.valueDisplayMap:
                    self.valueDisplayMap[valueKey] = (len(self.valueDisplayMap), value)


def parseTableA(blockList, path):
    """ヘッダブロックとデータブロックを分解して TableA を返す。"""
    if len(blockList) == 0:
        raise SpecError("評価表 %s に見出し行が1つもない。" % path)
    if len(blockList) == 1:
        raise SpecError(
            "評価表 %s にデータ行がない。\n"
            "  最初の # ブロック「%s」はヘッダとして扱うため、\n"
            "  選択肢を表す # ブロックが少なくとも1つ必要である。"
            % (path, blockList[0].title))

    headerBlock = blockList[0]
    criterionNameList = list(headerBlock.childList)
    if len(criterionNameList) == 0:
        raise SpecError(
            "評価表 %s のヘッダ「%s」に評価項目（##）が1つもない。"
            % (path, headerBlock.title))

    seenKeySet = set()
    for criterionName in criterionNameList:
        criterionKey = normalizeText(criterionName)
        if criterionKey in seenKeySet:
            printWarning(
                "評価表 %s のヘッダに評価項目「%s」が重複している。最初の列を使用する。"
                % (path, criterionName))
        seenKeySet.add(criterionKey)

    columnCount = len(criterionNameList)
    dataRowList = []
    for rowIndex, block in enumerate(blockList[1:]):
        valueList = list(block.childList)
        if len(valueList) < columnCount:
            raise SpecError(
                "評価表 %s の %d 行目、選択肢「%s」の評価値が足りない。\n"
                "  必要な列数: %d（%s）\n"
                "  実際の列数: %d"
                % (path, block.lineNumber, block.title, columnCount,
                   ", ".join(criterionNameList), len(valueList)))
        if len(valueList) > columnCount:
            printWarning(
                "評価表 %s の選択肢「%s」の評価値が列数(%d)より多い(%d)。超過分を無視した。"
                % (path, block.title, columnCount, len(valueList)))
            valueList = valueList[:columnCount]
        dataRowList.append(DataRow(block.title, valueList, rowIndex))

    return TableA(criterionNameList, dataRowList)


def parseTableB(blockList, path):
    """順位の昇順に並べた評価項目名のリスト（優先度リスト）を返す。"""
    if len(blockList) == 0:
        raise SpecError("優先度表 %s に見出し行が1つもない。" % path)

    entryList = []
    for block in blockList[1:]:   # 最初のブロックはヘッダなので読み飛ばす
        rankText = normalizeText(block.title)
        try:
            rankNumber = int(rankText)
        except ValueError:
            raise SpecError(
                "優先度表 %s の %d 行目、順位「%s」を整数として解釈できない。"
                % (path, block.lineNumber, block.title))
        if len(block.childList) == 0:
            raise SpecError(
                "優先度表 %s の %d 行目、順位 %s に評価項目（##）が指定されていない。"
                % (path, block.lineNumber, block.title))
        if len(block.childList) > 1:
            printWarning(
                "優先度表 %s の順位 %s に評価項目が複数ある。最初の「%s」を使用する。"
                % (path, block.title, block.childList[0]))
        entryList.append((rankNumber, block.childList[0], block.lineNumber))

    entryList.sort(key=lambda entry: entry[0])   # 安定ソート。同順位は出現順を保つ
    return entryList


def buildPriorityList(entryList, tableE, tableEPath, tablePPath):
    """優先度表の評価項目を評価表の列に照合し、優先度リストを組み立てる。"""
    missingList = []
    priorityList = []
    usedKeySet = set()

    for rankNumber, criterionName, lineNumber in entryList:
        criterionKey = normalizeText(criterionName)
        if criterionKey not in tableE.columnIndexMap:
            missingList.append((rankNumber, criterionName, lineNumber))
            continue
        if criterionKey in usedKeySet:
            printWarning(
                "優先度表 %s で評価項目「%s」が重複して指定されている。順位 %d の指定を無視した。"
                % (tablePPath, criterionName, rankNumber))
            continue
        usedKeySet.add(criterionKey)
        # 出力には評価表側の原文を使う
        columnIndex = tableE.columnIndexMap[criterionKey]
        priorityList.append(tableE.criterionNameList[columnIndex])

    if missingList:
        detailLineList = []
        for rankNumber, criterionName, lineNumber in missingList:
            detailLineList.append(
                "  優先度表 %s の %d 行目、順位 %d で指定されている。"
                % (tablePPath, lineNumber, rankNumber))
        nameList = "、".join("「%s」" % item[1] for item in missingList)
        raise SpecError(
            "優先度表の評価項目%sが評価表に存在しない。\n"
            "%s\n"
            "  評価表 %s のヘッダに定義されている評価項目は次のとおり:\n"
            "    %s\n"
            "  （全角・半角およびスペースの違いは無視して照合している）"
            % (nameList, "\n".join(detailLineList), tableEPath,
               ", ".join(tableE.criterionNameList)))

    for criterionName in tableE.criterionNameList:
        if normalizeText(criterionName) not in usedKeySet:
            printWarning(
                "評価項目「%s」は優先度表 %s に指定がないため、分岐に使用しない。"
                % (criterionName, tablePPath))

    return priorityList


# --------------------------------------------------------------------------
# 木の構築
# --------------------------------------------------------------------------


def getCellValue(dataRow, criterionName, tableE):
    """データ行から、指定した評価項目の評価値（原文）を取り出す。"""
    columnIndex = tableE.columnIndexMap[normalizeText(criterionName)]
    return dataRow.valueList[columnIndex]


def groupRowsByValue(rowList, criterionName, tableE):
    """評価値ごとにデータ行をまとめる。

    戻り値は [(表示用の評価値, [データ行, ...]), ...] を評価値のランク順に並べたもの。
    """
    groupMap = {}
    for dataRow in rowList:
        rawValue = getCellValue(dataRow, criterionName, tableE)
        valueKey = normalizeText(rawValue)
        if valueKey not in groupMap:
            # 表示は tableE 内で最初に出現した原文を代表として採用する
            _, displayValue = tableE.valueDisplayMap.get(valueKey, (0, rawValue))
            groupMap[valueKey] = {"display": displayValue, "rowList": []}
        groupMap[valueKey]["rowList"].append(dataRow)

    unknownRankBase = len(valueRankTable)

    def sortKey(item):
        valueKey, group = item
        if valueKey in valueRankTable:
            return (valueRankTable[valueKey], 0)
        # 未知の評価値は既知の値すべての後ろに、tableE 内の初出順で並べる
        firstSeenIndex, _ = tableE.valueDisplayMap.get(valueKey, (0, ""))
        return (unknownRankBase, firstSeenIndex)

    sortedItemList = sorted(groupMap.items(), key=sortKey)
    return [(group["display"], group["rowList"]) for _, group in sortedItemList]


def buildNode(rowList, criteriaList, level, edgeValue, tableE, outputLines):
    """1ノードを出力し、必要なら子ノードを再帰的に構築する。"""
    linePrefix = "#" * level + " "
    if edgeValue is not None:
        linePrefix += "|" + edgeValue + "|"

    # (a) 選択肢が1つに絞れた -> 葉ノード（評価項目が残っていても葉にする）
    if len(rowList) == 1:
        outputLines.append(linePrefix + rowList[0].choiceName)
        return

    # (b) 評価項目を使い切った -> 葉ノード（複数の選択肢を列挙する）
    if len(criteriaList) == 0:
        orderedRowList = sorted(rowList, key=lambda dataRow: dataRow.rowIndex)
        joinedName = choiceSeparator.join(
            dataRow.choiceName for dataRow in orderedRowList)
        outputLines.append(linePrefix + joinedName)
        return

    # (c) 中間ノード
    currentCriterion = criteriaList[0]
    outputLines.append(linePrefix + shapePrefix + currentCriterion)

    for groupValue, groupRowList in groupRowsByValue(rowList, currentCriterion, tableE):
        buildNode(groupRowList, criteriaList[1:], level + 1, groupValue,
                  tableE, outputLines)


def generateDiagram(tableEPath, tablePPath):
    """入力ファイルを読み、出力テキストを返す。"""
    tableE = parseTableA(parseHeadingFile(tableEPath), tableEPath)
    entryList = parseTableB(parseHeadingFile(tablePPath), tablePPath)
    priorityList = buildPriorityList(entryList, tableE, tableEPath, tablePPath)

    # 1行目に入力ファイル名（ディレクトリを除いたもの）を書き、2行目を空行にする
    sourceLine = sourceLineFormat.format(
        tableEName=os.path.basename(tableEPath),
        tablePName=os.path.basename(tablePPath))
    outputLines = [sourceLine, ""]
    buildNode(tableE.dataRowList, priorityList, 1, None, tableE, outputLines)
    return "\n".join(outputLines) + "\n"


# --------------------------------------------------------------------------
# エントリポイント
# --------------------------------------------------------------------------


def main():
    argumentParser = argparse.ArgumentParser(
        description="評価表と優先度表からダイアグラム生成用の見出し形式を出力する。")
    argumentParser.add_argument("--tableE", dest="tableEPath", required=True,
                                help="評価用見出し形式のファイル")
    argumentParser.add_argument("--tableP", dest="tablePPath", required=True,
                                help="優先度用見出し形式のファイル")
    argumentParser.add_argument("-o", "--output", dest="outputPath", default=None,
                                help="出力先。省略時は標準出力")
    parsedArgument = argumentParser.parse_args()

    try:
        outputText = generateDiagram(parsedArgument.tableEPath,
                                     parsedArgument.tablePPath)
    except SpecError as error:
        print("エラー: " + str(error), file=sys.stderr)
        return 1

    if parsedArgument.outputPath is None:
        sys.stdout.write(outputText)
    else:
        try:
            with open(parsedArgument.outputPath, "w",
                      encoding="utf-8", newline="\n") as outputFile:
                outputFile.write(outputText)
        except OSError as error:
            print("エラー: ファイル「%s」に書き込めない。\n  %s"
                  % (parsedArgument.outputPath, error), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
