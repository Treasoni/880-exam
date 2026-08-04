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
  # Windows 请把 python3 换成 py -3
"""

import json
import re
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib880

ROOT = Path(__file__).resolve().parent.parent

# 跨平台：Windows 控制台/非 UTF-8 locale 下 print 中文不崩溃（同 lib880.ensure_utf8_stdio）
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
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


def check_source_alignment():
    """审计原始 Markdown 的可解析数量；OCR 造成的差异只作提示，不能据此覆盖 LLM 对齐结果。"""
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
    print("\n原始 Markdown 计数: ", "一致" if ok else "存在 OCR/标记差异（需以逐节提取日志复核）")
    return ok


def check_index(*, allow_pending_review=False):
    """校验当前可运行索引；返回 True 时才可作为稳定输入使用。"""
    try:
        schema = lib880.load_schema()
        index = lib880.load_index()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"!! 无法读取索引或配置: {exc}", file=sys.stderr)
        return False
    errors = lib880.validate_index(schema, index, strict_review=not allow_pending_review)
    if errors:
        print("\n=== 索引契约校验失败 ===", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        if not allow_pending_review and index.get("stats", {}).get("verify_needs_review", 0):
            print("  可用 --allow-pending-review 仅确认结构完整；不要把它当作人工复核完成。", file=sys.stderr)
        return False
    print("\n索引契约校验: 通过")
    return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="审计原始题库与当前 question-index.json")
    ap.add_argument("--check", action="store_true", help="严格校验当前索引；待人工复核项会使命令失败")
    ap.add_argument("--allow-pending-review", action="store_true",
                    help="只校验索引结构；保留待复核警告")
    args = ap.parse_args()
    check_source_alignment()
    if args.check:
        sys.exit(0 if check_index(allow_pending_review=args.allow_pending_review) else 1)
    print("\n提示：题目索引由 prepare_sections + extraction workflow + merge_extraction.py 生成。")
