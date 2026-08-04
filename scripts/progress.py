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


def main():
    schema = lib880.load_schema()
    index = lib880.load_index()
    lib880.build_index_map(index)
    attempts = lib880.load_attempts()
    papers = lib880.load_papers()

    # 抽到过但未判分 的题目集合
    drawn = {}
    for p in papers["papers"]:
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
    lines.append("tags: [高数, 880, 进度]")
    lines.append(f"total: {total}")
    lines.append(f"graded: {n_graded}")
    lines.append(f"pending: {n_pending}")
    lines.append(f"undone: {n_undone}")
    lines.append(f"wrong: {n_wrong}")
    lines.append("---")
    lines.append("")
    lines.append("# 880 进度总览")
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
    lines.append("- 错题本：[[错题本]]")
    if papers["papers"]:
        links = "、".join(f"[[卷子-{p['paper_id'].split('-')[-1]}]]" for p in papers["papers"])
        lines.append(f"- 卷子：{links}")
    lines.append("")

    lib880.PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    lib880.PROGRESS_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"已更新进度总览：{lib880.PROGRESS_PATH}")
    print(f"汇总：总{total} 已判{n_graded} 欠账{n_pending} 未做{n_undone} 非对{n_wrong}")


def _cn(n):
    return "零一二三四五六七八九"[n]


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
