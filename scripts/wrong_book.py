#!/usr/bin/env python3
"""wrong_book.py — 生成错题本（按章节），并可更新复习状态。

用法：
  python3 scripts/wrong_book.py                     # 重新生成错题本
  python3 scripts/wrong_book.py --mark qid=已掌握   # 更新某题复习状态后重新生成
  python3 scripts/wrong_book.py --list-states       # 列出全部错题及状态
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib880

GRADE_ZH = {g["key"]: g["zh"] for g in lib880.load_schema()["grades"]}
DIFF_ZH = {"basic": "基础", "comprehensive": "综合", "extension": "拓展"}
TYPE_ZH = {"choice": "选择题", "fill": "填空题", "solution": "解答题"}
CN = "零一二三四五六七八九"


def latest_grade(qid, attempts):
    hits = [a for a in attempts["attempts"] if a["qid"] == qid]
    if not hits:
        return None
    return hits[-1]  # 按插入顺序，最后一条即最近一次判分


def build_wrong_list(schema, index, attempts):
    focus = set(schema["wrong_book"]["focus_grades"])
    light = set(schema["wrong_book"]["light_grades"])
    wrong = []
    for q in index["questions"]:
        last = latest_grade(q["id"], attempts)
        if last is None or last["grade"] == "correct":
            continue
        entry = {
            "q": q,
            "grade": last["grade"],
            "grade_zh": GRADE_ZH.get(last["grade"], last["grade"]),
            "when": last["when"],
            "paper_id": last.get("paper_id"),
            "state": attempts["wrong_book_status"].get(q["id"], {}).get("state", "未复习"),
            "priority": "重点" if last["grade"] in focus else ("轻" if last["grade"] in light else ""),
        }
        wrong.append(entry)
    wrong.sort(key=lambda e: (e["q"]["chapter_no"], e["q"]["type"], e["q"]["q_num"]))
    return wrong


def render(schema, index, attempts, wrong):
    total = len(wrong)
    n_focus = sum(1 for e in wrong if e["priority"] == "重点")
    n_mastered = sum(1 for e in wrong if e["state"] == "已掌握")
    lines = []
    lines.append("---")
    lines.append("type: 错题本")
    lines.append(f"updated: {lib880.today_str()}")
    lines.append("tags: [高数, 880, 错题本]")
    lines.append(f"total: {total}")
    lines.append(f"focus_count: {n_focus}")
    lines.append(f"mastered_count: {n_mastered}")
    lines.append("---")
    lines.append("")
    lines.append("# 880 错题本")
    lines.append("")
    lines.append("> 判分中『不会』『半会』为重点，『错』『粗心』为轻标记。复习状态：未复习 → 已重做 → 已掌握。")
    lines.append("")
    lines.append(f"共 {total} 道错题（重点 {n_focus} · 已掌握 {n_mastered}）")
    lines.append("")

    by_ch = {}
    for e in wrong:
        by_ch.setdefault(e["q"]["chapter_no"], []).append(e)

    if not by_ch:
        lines.append("（暂无错题，继续加油 ✅）")
        lines.append("")

    for ch in sorted(by_ch):
        es = by_ch[ch]
        title = next((c["title"] for c in schema["chapters"] if c["no"] == ch), "")
        lines.append(f"## 第{CN[ch]}章 {title}（{len(es)} 题）")
        lines.append("")
        lines.append("| # | 题型 | 难度 | 判分 | 优先级 | 复习状态 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for e in es:
            q = e["q"]
            lines.append(f"| {q['q_num']} | {TYPE_ZH[q['type']]} | {DIFF_ZH[q['difficulty']]} | {e['grade_zh']} | {e['priority']} | {e['state']} |")
        lines.append("")
        lines.append("### 题目与解析")
        lines.append("")
        for e in es:
            q = e["q"]
            lines.append(f"#### 第{CN[ch]}章 {TYPE_ZH[q['type']]} 第 {q['q_num']} 题 · 判分：{e['grade_zh']} · {e['priority']} · {e['state']}")
            lines.append("")
            lines.append(f"**题干：** {q['text']}")
            lines.append("")
            if q.get("answer"):
                lines.append(f"**答案：** {q['answer']}")
                lines.append("")
            if q.get("solution"):
                lines.append("**解析：**")
                lines.append("")
                lines.append(q["solution"].strip())
                lines.append("")
            if e.get("paper_id"):
                lines.append(f"*来源卷子：[[卷子-{e['paper_id'].split('-')[-1]}]]*")
            if e["when"]:
                lines.append(f"*最近判分：{e['when']}*")
            lines.append("")
    lines.append("## 关联")
    lines.append("")
    lines.append("- 进度：[[进度总览]]")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mark", action="append", default=[], help="qid=状态")
    ap.add_argument("--list-states", action="store_true")
    args = ap.parse_args()

    schema = lib880.load_schema()
    index = lib880.load_index()
    lib880.build_index_map(index)
    attempts = lib880.load_attempts()

    valid_states = set(schema["wrong_book"]["review_states"])
    for spec in args.mark:
        if "=" not in spec:
            print(f"!! 无效 --mark: {spec}（应为 qid=状态）", file=sys.stderr)
            sys.exit(2)
        qid, state = spec.split("=", 1)
        if state not in valid_states:
            print(f"!! 无效状态 {state}（可选 {valid_states}）", file=sys.stderr)
            sys.exit(2)
        if qid not in index["by_id"]:
            print(f"!! 未知题号 {qid}", file=sys.stderr)
            sys.exit(2)
        attempts["wrong_book_status"][qid] = {
            "state": state, "updated": lib880.today_str(),
        }
        lib880.save_attempts(attempts)
        print(f"已更新 {qid} → {state}")

    wrong = build_wrong_list(schema, index, attempts)
    if args.list_states:
        for e in wrong:
            print(f"{e['q']['id']}  {e['grade_zh']:<4} {e['priority']:<3} {e['state']}")
        return

    lib880.WRONG_BOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    lib880.WRONG_BOOK_PATH.write_text(
        render(schema, index, attempts, wrong), encoding="utf-8")
    print(f"已更新错题本：{lib880.WRONG_BOOK_PATH}（{len(wrong)} 道错题）")


if __name__ == "__main__":
    main()
