#!/usr/bin/env python3
"""progress.py — 生成进度总览（预览/需求5）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib880

GRADE_ICON = {
    "correct": "✅ 对", "wrong": "❌ 错", "cannot": "⚠️ 不会",
    "half": "🔶 半会", "careless": "🟡 粗心",
}
DIFF_ZH = {"basic": "基础", "comprehensive": "综合", "extension": "拓展"}
TYPE_ZH = {"choice": "选", "fill": "填", "solution": "解"}


def latest_grade(qid, attempts):
    last = lib880.latest_attempt(qid, attempts)
    return last["grade"] if last else None


def generate(subject=lib880.SUBJECT_HIGH_MATH):
    """Regenerate one subject's progress note and return its summary counts."""
    subject = lib880.normalize_subject(subject)
    schema = lib880.load_schema(subject)
    index = lib880.load_index(subject)
    lib880.build_index_map(index)
    attempts = lib880.load_attempts()
    papers = lib880.load_papers()

    # 抽到过但未判分 的题目集合
    drawn = {}
    subject_papers = [p for p in papers["papers"] if lib880.subject_from_paper(p) == subject]
    for p in subject_papers:
        for q in p["questions"]:
            drawn[q["qid"]] = True

    status = {}
    for q in index["questions"]:
        g = latest_grade(q["id"], attempts)
        if g:
            status[q["id"]] = ("graded", g)
        elif q["id"] in drawn:
            status[q["id"]] = ("pending", None)
        else:
            status[q["id"]] = ("undone", None)

    total = len(index["questions"])
    n_graded = sum(1 for s in status.values() if s[0] == "graded")
    n_pending = sum(1 for s in status.values() if s[0] == "pending")
    n_undone = total - n_graded - n_pending
    n_wrong = sum(1 for s in status.values() if s[0] == "graded" and s[1] != "correct")

    weakness = lib880.chapter_weakness(schema, index, attempts)

    lines = []
    lines.append("---")
    lines.append("type: 进度总览")
    lines.append(f"updated: {lib880.today_str()}")
    lines.append(f"tags: [{schema['subject']}, 880, 进度]")
    lines.append(f"total: {total}")
    lines.append(f"graded: {n_graded}")
    lines.append(f"pending: {n_pending}")
    lines.append(f"undone: {n_undone}")
    lines.append(f"wrong: {n_wrong}")
    lines.append("---")
    lines.append("")
    lines.append(f"# 880 {schema['subject']}进度总览")
    lines.append("")
    lines.append("## 汇总")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("| --- | --- |")
    lines.append(f"| 总题数 | {total} |")
    lines.append(f"| 已做并判分 | {n_graded} |")
    lines.append(f"| 做过未判（欠账） | {n_pending} |")
    lines.append(f"| 未做 | {n_undone} |")
    lines.append(f"| 判分中含非『对』 | {n_wrong} |")
    lines.append("")
    lines.append("## 章节弱点排行")
    lines.append("")
    if weakness:
        lines.append("| 排名 | 章节 | 弱点分 |")
        lines.append("| --- | --- | --- |")
        for i, (ch, w) in enumerate(sorted(weakness.items(), key=lambda kv: -kv[1]), start=1):
            title = index["questions"][0]["chapter_title"] if False else _ch_title(schema, index, ch)
            lines.append(f"| {i} | 第{_cn(ch)}章 {title} | {w:.2f} |")
    else:
        lines.append("（暂无判分记录，先做一张卷判分后再看弱点）")
    lines.append("")
    lines.append("## 章节进度")
    lines.append("")

    by_ch = {}
    for q in index["questions"]:
        by_ch.setdefault(q["chapter_no"], []).append(q)

    for ch in sorted(by_ch):
        qs = by_ch[ch]
        done = sum(1 for q in qs if status[q["id"]][0] == "graded")
        lines.append(f"### 第{_cn(ch)}章 {_ch_title(schema, index, ch)}（{done}/{len(qs)} 题已判）")
        lines.append("")
        lines.append("| # | 题 | 难度 | 状态 |")
        lines.append("| --- | --- | --- | --- |")
        for q in sorted(qs, key=lambda q: (q["type"], q["q_num"])):
            st, g = status[q["id"]]
            if st == "graded":
                icon = GRADE_ICON.get(g, g)
            elif st == "pending":
                icon = "📝 做过未判"
            else:
                icon = "⬜ 未做"
            lines.append(f"| {q['q_num']} | {TYPE_ZH[q['type']]} | {DIFF_ZH[q['difficulty']]} | {icon} |")
        lines.append("")

    lines.append("## 关联")
    lines.append("")
    lines.append(f"- 错题本：[[{lib880.wrong_book_path(subject).stem}]]")
    if subject_papers:
        links = "、".join(
            f"[[{lib880.paper_artifact_stems(subject, p['paper_id'])['paper']}]]"
            for p in subject_papers
        )
        lines.append(f"- 卷子：{links}")
    lines.append("")

    output_path = lib880.progress_path(subject)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path, {
        "total": total,
        "graded": n_graded,
        "pending": n_pending,
        "undone": n_undone,
        "wrong": n_wrong,
    }


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", default=lib880.SUBJECT_HIGH_MATH,
                    help="题库：high-math（默认）或 linear-algebra")
    args = ap.parse_args()
    try:
        subject = lib880.normalize_subject(args.subject)
    except ValueError as exc:
        ap.error(str(exc))
    output_path, summary = generate(subject)
    print(f"已更新进度总览：{output_path}")
    print(
        f"汇总：总{summary['total']} 已判{summary['graded']} "
        f"欠账{summary['pending']} 未做{summary['undone']} 非对{summary['wrong']}"
    )


def _cn(n):
    return lib880.chapter_number_zh(n)


def _ch_title(schema, index, ch):
    meta = next((c for c in schema["chapters"] if c["no"] == ch), None)
    if meta:
        return meta["title"]
    qs = [q for q in index["questions"] if q["chapter_no"] == ch]
    if qs:
        t = qs[0]["chapter_title"] or ""
        return t.lstrip(f"第{_cn(ch)}章").strip()
    return ""


if __name__ == "__main__":
    main()
