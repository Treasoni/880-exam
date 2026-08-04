#!/usr/bin/env python3
"""
build-question-index.py — 解析做题本 + 解析册，生成题目索引。

输入（只读）：
  880/【A4紧凑版】李林880数二高数篇做题本/full.md    （题目，含全部 6 章）
  880/第一章到第五章解析/full.md                    （答案，第 1~5 章）
  880/第六章解析/full.md                            （答案，第 6 章）

输出：
  workspace/question-index.json  — 每题：唯一ID/科目/章/难度/题型/序号/题干/答案/解析

用法：
  python3 scripts/build-question-index.py --check   # 只输出对齐校验报告
  python3 scripts/build-question-index.py           # 生成索引
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "880/【A4紧凑版】李林880数二高数篇做题本/full.md"
ANSWER_15 = ROOT / "880/第一章到第五章解析/full.md"
ANSWER_6 = ROOT / "880/第六章解析/full.md"
OUT = ROOT / "workspace/question-index.json"

SUBJECT = "高数"

CHAPTER_RE = re.compile(r"^第([一二三四五六])章\s+(.+)")
DIFFICULTY_RE = re.compile(r"^(基础题|综合题|拓展题)$")
TYPE_RE = re.compile(r"^(?:[一二三四五六]、)?(选择题|填空题|解答题)$")
Q_RE = re.compile(r"^[（(](\d+)[)）]\s*(.*)$")

CHAPTER_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6}
TYPE_MAP = {"选择题": "choice", "填空题": "fill", "解答题": "solution"}
DIFF_MAP = {"基础题": "basic", "综合题": "comprehensive", "拓展题": "extension"}


def parse_questions(path: Path):
    """把一份 full.md 解析成题目条目列表（语义化键，不用位置索引）。"""
    lines = path.read_text(encoding="utf-8").splitlines()

    chapter_no, chapter_title, difficulty, qtype = None, None, None, None
    cur = None
    entries = []

    def flush():
        nonlocal cur
        if cur is not None and cur["text"]:
            entries.append(cur)
        cur = None

    def new_question(num):
        nonlocal cur
        return {
            "chapter_no": chapter_no,
            "chapter_title": chapter_title,
            "difficulty": difficulty,
            "type": qtype,
            "q_num": num,
            "text": [],
        }

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            body = line.lstrip("#").strip()
            m = CHAPTER_RE.match(body)
            if m:
                flush()
                chapter_no = CHAPTER_NUM[m.group(1)]
                chapter_title = body
                difficulty, qtype, cur = None, None, None
                continue
            m = DIFFICULTY_RE.match(body)
            if m:
                flush()
                difficulty = m.group(1)
                qtype, cur = None, None
                continue
            m = TYPE_RE.match(body)
            if m:
                flush()
                qtype = m.group(1)
                cur = None
                continue
            continue
        if difficulty is None or qtype is None:
            continue
        m = Q_RE.match(line)
        if m:
            num = int(m.group(1))
            if cur is not None and cur["q_num"] == num:
                cur["text"].append(line)
            else:
                flush()
                cur = new_question(num)
                cur["text"].append(line)
        else:
            if cur is not None:
                cur["text"].append(line)
    flush()
    return entries


def summarize(entries):
    stat = {}
    for e in entries:
        key = (e["chapter_no"], e["difficulty"], e["type"])
        stat[key] = stat.get(key, 0) + 1
    return stat


def check():
    wb = parse_questions(WORKBOOK)
    a = parse_questions(ANSWER_15) + parse_questions(ANSWER_6)

    wb_stat = summarize(wb)
    a_stat = summarize(a)
    all_keys = sorted(set(wb_stat) | set(a_stat), key=lambda k: (k[0], k[1], k[2]))

    print(f"做题本总题数: {len(wb)}   解析册总题数: {len(a)}")
    print(f"\n=== 逐节题数对比 (章|难度|题型 → 做题本 vs 解析册) ===")
    ok = True
    for k in all_keys:
        w = wb_stat.get(k, 0)
        x = a_stat.get(k, 0)
        if w != x:
            ok = False
            flag = "解析缺节/少题" if x < w else "!! 解析多出"
        else:
            flag = "OK"
        print(f"  第{k[0]}章 | {k[1]} | {k[2]} → {w:>3} vs {x:<3}  {flag}")
    print("\n总对齐: ", "通过" if ok else "存在不一致")


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
        sys.exit(0)
    check()
    print("\n(尚未实现索引输出，先跑 --check)")
