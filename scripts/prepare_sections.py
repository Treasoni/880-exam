#!/usr/bin/env python3
"""
prepare_sections.py — 把做题本与解析册按小节切成原文对，供 LLM 逐节对齐提取。

输出到 workspace/.build/：
  sections/manifest.json         — 每节元信息（章节/难度/题型/行号/题号/原文文件）
  sections/{id}.wb.md            — 做题本该节原文
  sections/{id}.ans.md           — 解析册该节原文

id 形如 ch1-basic-choice。
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 跨平台：Windows 控制台/非 UTF-8 locale 下 print 中文不崩溃（同 lib880.ensure_utf8_stdio）
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
WORKBOOK = ROOT / "880/【A4紧凑版】李林880数二高数篇做题本/full.md"
ANSWER_15 = ROOT / "880/第一章到第五章解析/full.md"
ANSWER_6 = ROOT / "880/第六章解析/full.md"
BUILD = ROOT / "workspace/.build/sections"

CHAPTER_RE = re.compile(r"^第([一二三四五六])章\s+(.+)")
DIFFICULTY_RE = re.compile(r"^(基础题|综合题|拓展题)$")
TYPE_HEADING_RE = re.compile(r"^(?:[一二三四五六]、)?(选择题|填空题|解答题)$")
Q_RE = re.compile(r"^[（(](\d+)[)）]\s*(.*)$")
CHAPTER_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6}
TYPE_MAP = {"选择题": "choice", "填空题": "fill", "解答题": "solution"}
DIFF_MAP = {"基础题": "basic", "综合题": "comprehensive", "拓展题": "extension"}


def find_sections(path: Path):
    """返回 [ {id字段, chapter_no, chapter_title, difficulty, type, start, end, lines, q_nums} ]"""
    lines = path.read_text(encoding="utf-8").splitlines()
    chapter_no = chapter_title = difficulty = qtype = None
    sections = []
    open_sec = None

    def new_sec():
        return {"chapter_no": chapter_no, "chapter_title": chapter_title,
                "difficulty": difficulty, "type": qtype, "start": 0, "lines": []}

    def flush():
        nonlocal open_sec
        if open_sec is not None and open_sec["lines"]:
            open_sec["end"] = open_sec["start"] + len(open_sec["lines"]) - 1
            nums = []
            for ln in open_sec["lines"]:
                m = Q_RE.match(ln.strip())
                if m:
                    nums.append(int(m.group(1)))
            open_sec["q_nums"] = nums
            sections.append(open_sec)
        open_sec = None

    for idx, raw in enumerate(lines):
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
                difficulty = qtype = None
                continue
            m = DIFFICULTY_RE.match(body)
            if m:
                flush()
                difficulty = m.group(1)
                qtype = None
                continue
            m = TYPE_HEADING_RE.match(body)
            if m:
                flush()
                qtype = m.group(1)
                open_sec = new_sec()
                open_sec["start"] = idx
                continue
            continue
        # 非标题行：裸文本章节/题型标记（做题本与解析册的拓展题均可能出现）
        if DIFFICULTY_RE.match(line):
            flush()
            difficulty = line
            qtype = None
            continue
        if TYPE_HEADING_RE.match(line):
            flush()
            qtype = line
            open_sec = new_sec()
            open_sec["start"] = idx
            continue
        # 拓展题缺题型标记时按“解答题”处理（如解析册第五章拓展题）
        if qtype is None and difficulty == "拓展题" and Q_RE.match(line):
            qtype = "解答题"
            open_sec = new_sec()
            open_sec["start"] = idx
        if open_sec is not None and chapter_no is not None and difficulty is not None and qtype is not None:
            open_sec["lines"].append(raw)
    flush()
    return sections


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    wb = find_sections(WORKBOOK)
    ans = find_sections(ANSWER_15) + find_sections(ANSWER_6)

    by_key = {}
    for s in wb + ans:
        key = (s["chapter_no"], s["difficulty"], s["type"])
        by_key.setdefault(key, []).append(s)

    manifest = []
    for key, sections in sorted(by_key.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
        ch, diff, typ = key
        sid = f"ch{ch}-{DIFF_MAP[diff]}-{TYPE_MAP[typ]}"
        wb_s = next((s for s in sections if s in wb), None)
        ans_s = next((s for s in sections if s not in wb), None)
        if wb_s is None:
            print(f"!! {sid}: 做题本缺节（仅解析册有）")
        if ans_s is None:
            print(f"!! {sid}: 解析册缺节")
        wb_path = BUILD / f"{sid}.wb.md"
        ans_path = BUILD / f"{sid}.ans.md"
        if wb_s:
            wb_path.write_text("\n".join(wb_s["lines"]) + "\n", encoding="utf-8")
        if ans_s:
            ans_path.write_text("\n".join(ans_s["lines"]) + "\n", encoding="utf-8")
        manifest.append({
            "id": sid,
            "chapter_no": ch, "chapter_title": wb_s["chapter_title"] if wb_s else ans_s["chapter_title"],
            "difficulty": diff, "type": typ,
            "wb_q_nums": wb_s["q_nums"] if wb_s else [],
            "ans_q_nums": ans_s["q_nums"] if ans_s else [],
            "wb_file": wb_path.name if wb_s else None,
            "ans_file": ans_path.name if ans_s else None,
        })

    (BUILD / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n共 {len(manifest)} 节 → {BUILD}")
    total_wb = sum(len(m["wb_q_nums"]) for m in manifest)
    total_ans = sum(len(m["ans_q_nums"]) for m in manifest)
    print(f"做题本标记总数: {total_wb}   解析册标记总数: {total_ans}")
    print("\n=== 每节题号列表（做题本 vs 解析册） ===")
    for m in manifest:
        w = m["wb_q_nums"]
        a = m["ans_q_nums"]
        flag = "OK" if w == a else "DIFF"
        print(f"  {m['id']:<24} wb={len(w):>2} ans={len(a):>2}  {flag}   wb:{w}  ans:{a}")


if __name__ == "__main__":
    sys.exit(main())
