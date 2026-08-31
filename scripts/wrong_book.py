#!/usr/bin/env python3
"""wrong_book.py — 生成错题本（按章节），并可更新复习状态。

用法：
  python3 scripts/wrong_book.py                     # 重新生成错题本
  python3 scripts/wrong_book.py --mark qid=已掌握   # 更新某题复习状态后重新生成
  python3 scripts/wrong_book.py --list-states       # 列出全部错题及状态
  # Windows 请把 python3 换成 py -3（如 py -3 scripts/wrong_book.py）
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib880

GRADE_ZH = {g["key"]: g["zh"] for g in lib880.load_schema()["grades"]}
DIFF_ZH = {"basic": "基础", "comprehensive": "综合", "extension": "拓展"}
TYPE_ZH = {"choice": "选择题", "fill": "填空题", "solution": "解答题"}
CN = {n: lib880.chapter_number_zh(n) for n in range(1, 100)}


def latest_grade(qid, attempts):
    return lib880.latest_attempt(qid, attempts)


def build_wrong_lists(schema, index, attempts):
    """返回（待复习题，已掌握归档）。

    已掌握题的最近判分虽然为「对」，但只要此前出现过非「对」的判分，
    仍保留为错题复习记录，避免重练正确后丢失错因与解析。
    """
    focus = set(schema["wrong_book"]["focus_grades"])
    light = set(schema["wrong_book"]["light_grades"])
    active = []
    mastered = []
    for q in index["questions"]:
        last = latest_grade(q["id"], attempts)
        if last is None:
            continue
        state = attempts["wrong_book_status"].get(q["id"], {}).get("state", "未复习")
        had_noncorrect_attempt = any(
            a.get("qid") == q["id"] and a.get("grade") != "correct"
            for a in attempts["attempts"]
        )
        if last["grade"] == "correct" and not (state == "已掌握" and had_noncorrect_attempt):
            continue
        entry = {
            "q": q,
            "grade": last["grade"],
            "grade_zh": GRADE_ZH.get(last["grade"], last["grade"]),
            "when": last["when"],
            "paper_id": last.get("paper_id"),
            "state": state,
            "priority": "重点" if last["grade"] in focus else ("轻" if last["grade"] in light else ""),
        }
        if state == "已掌握" and last["grade"] == "correct":
            mastered.append(entry)
        else:
            active.append(entry)
    sort_key = lambda e: (e["q"]["chapter_no"], e["q"]["type"], e["q"]["q_num"])
    active.sort(key=sort_key)
    mastered.sort(key=sort_key)
    return active, mastered


def render(schema, index, attempts, active, mastered, ext_links=None, analysis=None,
           subject=lib880.SUBJECT_HIGH_MATH):
    ext_links = ext_links or {}
    analysis = analysis or {"items": {}}
    total = len(active) + len(mastered)
    n_focus = sum(1 for e in active if e["priority"] == "重点")
    n_mastered = len(mastered)
    lines = []
    lines.append("---")
    lines.append("type: 错题本")
    lines.append(f"updated: {lib880.today_str()}")
    lines.append(f"tags: [{schema['subject']}, 880, 错题本]")
    lines.append(f"total: {total}")
    lines.append(f"focus_count: {n_focus}")
    lines.append(f"mastered_count: {n_mastered}")
    lines.append("---")
    lines.append("")
    lines.append(f"# 880 {schema['subject']}错题本")
    lines.append("")
    lines.append("> 判分中『不会』『半会』为重点，『错』『粗心』为轻标记。复习状态：未复习 → 已重做 → 已掌握；已掌握题保留在文末归档。")
    lines.append("")
    lines.append(f"共 {total} 道错题记录（待复习 {len(active)} · 重点 {n_focus} · 已掌握 {n_mastered}）")
    lines.append("")

    by_ch = {}
    for e in active:
        by_ch.setdefault(e["q"]["chapter_no"], []).append(e)

    if not active and not mastered:
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
                lines.append(f"**答案：** {lib880.markdown_math_answer(q['answer'])}")
                lines.append("")
            if q.get("solution"):
                lines.append("**解析：**")
                lines.append("")
                lines.append(q["solution"].strip())
                lines.append("")
            if e.get("paper_id"):
                stem = lib880.paper_artifact_stems(subject, e["paper_id"])["paper"]
                lines.append(f"*来源卷子：[[{stem}]]*")
            if e["when"]:
                lines.append(f"*最近判分：{e['when']}*")
            raw_links = ext_links.get(q["id"])
            if isinstance(raw_links, dict):  # 兼容旧的单条结构
                raw_links = [raw_links]
            if raw_links:
                parts = []
                for link in raw_links:
                    if link.get("path") and link.get("anchor"):
                        label = link.get("label") or link["anchor"]
                        parts.append(f"[[{link['path']}#{link['anchor']}|{label}]]")
                if parts:
                    lines.append("*相关笔记：" + " · ".join(parts) + "*")
            an = analysis.get("items", {}).get(q["id"])
            if an:
                lines.append("")
                lines.append("> [!info] 错因分析")
                if an.get("cause"):
                    lines.append(f"> **错因：** {an['cause']}")
                if an.get("step"):
                    lines.append(f"> **出错环节：** {an['step']}")
                if an.get("advice"):
                    lines.append(f"> **建议：** {an['advice']}")
            lines.append("")

    if mastered:
        lines.append(f"## 已掌握归档（{len(mastered)} 题）")
        lines.append("")
        lines.append("> [!success] 间隔复习")
        lines.append("> 以下题目已在重练中做对，保留解析与错因分析，供后续抽查。")
        lines.append("")
        mastered_by_ch = {}
        for e in mastered:
            mastered_by_ch.setdefault(e["q"]["chapter_no"], []).append(e)
        for ch in sorted(mastered_by_ch):
            es = mastered_by_ch[ch]
            title = next((c["title"] for c in schema["chapters"] if c["no"] == ch), "")
            lines.append(f"### 第{CN[ch]}章 {title}（{len(es)} 题）")
            lines.append("")
            lines.append("| # | 题型 | 难度 | 最近判分 | 复习状态 |")
            lines.append("| --- | --- | --- | --- | --- |")
            for e in es:
                q = e["q"]
                lines.append(f"| {q['q_num']} | {TYPE_ZH[q['type']]} | {DIFF_ZH[q['difficulty']]} | {e['grade_zh']} | {e['state']} |")
            lines.append("")
            lines.append("#### 题目与解析")
            lines.append("")
            for e in es:
                q = e["q"]
                lines.append(f"##### 第{CN[ch]}章 {TYPE_ZH[q['type']]} 第 {q['q_num']} 题 · 最近判分：{e['grade_zh']} · {e['state']}")
                lines.append("")
                lines.append(f"**题干：** {q['text']}")
                lines.append("")
                if q.get("answer"):
                    lines.append(f"**答案：** {lib880.markdown_math_answer(q['answer'])}")
                    lines.append("")
                if q.get("solution"):
                    lines.append("**解析：**")
                    lines.append("")
                    lines.append(q["solution"].strip())
                    lines.append("")
                if e.get("paper_id"):
                    stem = lib880.paper_artifact_stems(subject, e["paper_id"])["paper"]
                    lines.append(f"*来源卷子：[[{stem}]]*")
                if e["when"]:
                    lines.append(f"*最近判分：{e['when']}*")
                raw_links = ext_links.get(q["id"])
                if isinstance(raw_links, dict):
                    raw_links = [raw_links]
                if raw_links:
                    parts = []
                    for link in raw_links:
                        if link.get("path") and link.get("anchor"):
                            label = link.get("label") or link["anchor"]
                            parts.append(f"[[{link['path']}#{link['anchor']}|{label}]]")
                    if parts:
                        lines.append("*相关笔记：" + " · ".join(parts) + "*")
                an = analysis.get("items", {}).get(q["id"])
                if an:
                    lines.append("")
                    lines.append("> [!info] 错因分析")
                    if an.get("cause"):
                        lines.append(f"> **错因：** {an['cause']}")
                    if an.get("step"):
                        lines.append(f"> **出错环节：** {an['step']}")
                    if an.get("advice"):
                        lines.append(f"> **建议：** {an['advice']}")
                lines.append("")
    lines.append("## 关联")
    lines.append("")
    lines.append(f"- 进度：[[{lib880.progress_path(subject).stem}]]")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", default=lib880.SUBJECT_HIGH_MATH,
                    help="题库：high-math（默认）或 linear-algebra")
    ap.add_argument("--mark", action="append", default=[], help="qid=状态")
    ap.add_argument("--list-states", action="store_true")
    args = ap.parse_args()

    try:
        subject = lib880.normalize_subject(args.subject)
    except ValueError as exc:
        ap.error(str(exc))
    schema = lib880.load_schema(subject)
    index = lib880.load_index(subject)
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

    active, mastered = build_wrong_lists(schema, index, attempts)
    if args.list_states:
        for e in active + mastered:
            print(f"{e['q']['id']}  {e['grade_zh']:<4} {e['priority']:<3} {e['state']}")
        return

    output_path = lib880.wrong_book_path(subject)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render(schema, index, attempts, active, mastered, lib880.load_external_links(), lib880.load_analysis(), subject),
        encoding="utf-8")
    print(f"已更新错题本：{output_path}（待复习 {len(active)} 道 · 已掌握归档 {len(mastered)} 道）")


if __name__ == "__main__":
    main()
