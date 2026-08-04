#!/usr/bin/env python3
"""make_paper.py — 按真题模式拼卷（配额浮动 + 难度配比 + 加权随机）。

用法：
  python3 scripts/make_paper.py                     # 自动取下一卷号
  python3 scripts/make_paper.py --n 3 --seed 42     # 指定卷号与随机种子
  python3 scripts/make_paper.py --ignore-extension  # 不使用拓展题
  python3 scripts/make_paper.py --no-weakness       # 忽略弱点浮动
"""

import argparse
import random
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib880

TYPE_ZH = {"choice": "选择题", "fill": "填空题", "solution": "解答题"}
DIFF_ZH = {"basic": "基础题", "comprehensive": "综合题", "extension": "拓展题"}
TYPE_ORDER = {"choice": "一", "fill": "二", "solution": "三"}
CN = "零一二三四五六七八九"


def allocate(weights, target):
    """按权重最大余数法分配 target 份，保证总和精确。"""
    if target <= 0:
        return {k: 0 for k in weights}
    keys = list(weights)
    total_w = sum(weights.values()) or 1.0
    alloc = {k: int(w * target / total_w) for k, w in weights.items()}
    rem = target - sum(alloc.values())
    frac = {k: w * target / total_w - int(w * target / total_w) for k, w in weights.items()}
    for k in sorted(keys, key=lambda k: -frac[k])[:rem]:
        alloc[k] += 1
    return alloc


def effective_quota(schema, weakness):
    """补弱配额浮动：返回 {chapter_no: {type: count}}，合计保持 10/6/6。

    弱点高于均值的章节上浮、低于的让题，最大偏差幅度=cap（默认 2 题）。
    """
    base = schema["paper"]["quota"]
    strength = schema["sampling"]["quota_float_strength"]
    cap = schema["sampling"]["quota_float_cap"]
    chapters = list(base)
    out = {ch: dict(base[ch]) for ch in chapters}
    if not weakness:
        return out
    wmean = sum(weakness.get(ch, 0.0) for ch in chapters) / len(chapters)
    raw_dev = {ch: strength * (weakness.get(ch, 0.0) - wmean) for ch in chapters}
    m = max(abs(v) for v in raw_dev.values()) or 0.0
    dev = {ch: raw_dev[ch] * (cap / m) if m else 0.0 for ch in chapters}

    for type_key, spec in schema["paper"]["sections"].items():
        target = spec["count"]
        frac = {ch: base[ch].get(type_key, 0) + dev[ch] for ch in chapters}
        lo = {ch: max(0, base[ch].get(type_key, 0) - cap) for ch in chapters}
        hi = {ch: base[ch].get(type_key, 0) + cap for ch in chapters}
        alloc = _round_to_target(frac, target, lo, hi)
        for ch in chapters:
            out[ch][type_key] = alloc[ch]
    return out


def _round_to_target(frac, target, lo, hi):
    """把各章节配额取整到总和=target，并满足 lo≤x≤hi。"""
    alloc = {ch: int(frac[ch]) for ch in frac}
    for ch in frac:
        alloc[ch] = min(max(alloc[ch], lo[ch]), hi[ch])
    diff = target - sum(alloc.values())
    if diff > 0:
        order = sorted(frac, key=lambda ch: frac[ch] - int(frac[ch]), reverse=True)
        for ch in order:
            if diff == 0:
                break
            if alloc[ch] < hi[ch]:
                alloc[ch] += 1
                diff -= 1
    elif diff < 0:
        order = sorted(frac, key=lambda ch: frac[ch] - int(frac[ch]))
        for ch in order:
            if diff == 0:
                break
            if alloc[ch] > lo[ch]:
                alloc[ch] -= 1
                diff += 1
    # 兜底（cap 冲突时保总量优先）
    for ch in frac:
        if diff == 0:
            break
        if diff > 0 and alloc[ch] < hi[ch]:
            alloc[ch] += 1
            diff -= 1
        elif diff < 0 and alloc[ch] > lo[ch]:
            alloc[ch] -= 1
            diff += 1
    return alloc


def cell_pool(index, chapter_no, type_key, difficulty):
    return [
        q for q in index["questions"]
        if q["chapter_no"] == chapter_no and q["type"] == type_key
        and q["difficulty"] == difficulty
    ]


def allocate_difficulties(schema, index, chapter_no, type_key, k, ignore_extension):
    mix = dict(schema["difficulty_mix"])
    if ignore_extension or not schema.get("extension_enabled", True):
        mix.pop("extension", None)
    avail = [
        d for d in mix
        if cell_pool(index, chapter_no, type_key, d)
    ]
    if not avail or k <= 0:
        return {}
    weights = {d: mix.get(d, 0) for d in avail}
    if sum(weights.values()) <= 0:
        weights = {d: 1 for d in avail}
    alloc = allocate(weights, k)
    # 池不足时收缩到池大小，空位转给还有余量的难度
    for d in avail:
        if alloc[d] > len(cell_pool(index, chapter_no, type_key, d)):
            alloc[d] = len(cell_pool(index, chapter_no, type_key, d))
    leftover = k - sum(alloc.values())
    for _ in range(leftover):
        candidates = [
            d for d in avail
            if alloc[d] < len(cell_pool(index, chapter_no, type_key, d))
        ]
        if not candidates:
            break
        d = max(candidates, key=lambda d: alloc[d] and mix.get(d, 0))
        alloc[d] += 1
    return {d: v for d, v in alloc.items() if v > 0}


def sample_weighted(pool, k, schema, attempts, avoid=None):
    avoid = avoid or set()
    now = date.today()
    w = []
    for q in pool:
        wq = lib880.question_weight(schema, q, attempts, now)
        if q["id"] in avoid:
            wq *= 0.05  # 上一张卷出现过的题几乎不抽
        w.append(wq)
    chosen = []
    for _ in range(k):
        total = sum(w)
        if total <= 0:
            break
        r = random.uniform(0, total)
        acc = 0.0
        for idx, wi in enumerate(w):
            acc += wi
            if r <= acc:
                chosen.append(pool[idx])
                w[idx] = 0.0
                break
    return chosen


def pick_cell(schema, index, attempts, chapter_no, type_key, k, ignore_extension, avoid):
    picked = []
    per_diff = allocate_difficulties(schema, index, chapter_no, type_key, k, ignore_extension)
    for diff, dk in per_diff.items():
        pool = cell_pool(index, chapter_no, type_key, diff)
        picked += sample_weighted(pool, dk, schema, attempts, avoid)
    return picked


def render_paper(schema, paper_id, sections_plan, questions_by_id):
    num = paper_id.split("-")[-1]
    lines = []
    lines.append("---")
    lines.append("type: 卷子")
    lines.append(f"paper_id: {paper_id}")
    lines.append(f"paper_no: \"{num}\"")
    lines.append(f"date: {lib880.today_str()}")
    lines.append(f"updated: {lib880.today_str()}")
    lines.append(f"subject: {schema['subject']}")
    lines.append(f"duration_minutes: {schema['paper']['duration_minutes']}")
    lines.append(f"total_score: {schema['paper']['total_score']}")
    lines.append("status: created")
    lines.append(f"tags: [{schema['subject']}, 880, 卷子]")
    lines.append(f"aliases: [第 {int(num)} 套]")
    lines.append("---")
    lines.append("")
    lines.append(f"# 880 高数模拟卷 · 第 {int(num)} 套")
    lines.append("")
    lines.append("> [!info] 卷头")
    lines.append(f"> 满分 {schema['paper']['total_score']} 分 · 限时 {schema['paper']['duration_minutes']} 分钟")
    lines.append("> 一、选择题 10 题×5 分 · 二、填空题 6 题×5 分 · 三、解答题 6 题共 70 分")
    lines.append("")

    for type_key in ("choice", "fill", "solution"):
        spec = schema["paper"]["sections"][type_key]
        if type_key == "solution":
            lines.append(f"## 三、解答题（共 70 分）")
        else:
            lines.append(f"## {TYPE_ORDER[type_key]}、{TYPE_ZH[type_key]}（每小题 {spec['per_score']} 分）")
        lines.append("")
        for idx, q in enumerate(sections_plan[type_key], start=1):
            lines.append(f"**{idx}.** {q['text']}")
            lines.append("")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 答题卡")
    lines.append("")
    # 选择
    n_choice = len(sections_plan["choice"])
    lines.append("**一、选择题**")
    lines.append("")
    lines.append("| 题号 | " + " | ".join(str(i) for i in range(1, n_choice + 1)) + " |")
    lines.append("| --- | " + " | ".join(["---"] * n_choice) + " |")
    lines.append("| 答案 | " + " | ".join([" "] * n_choice) + " |")
    lines.append("")
    n_fill = len(sections_plan["fill"])
    lines.append("**二、填空题**")
    lines.append("")
    lines.append("| 题号 | " + " | ".join(str(i) for i in range(1, n_fill + 1)) + " |")
    lines.append("| --- | " + " | ".join(["---"] * n_fill) + " |")
    lines.append("| 答案 | " + " | ".join([" "] * n_fill) + " |")
    lines.append("")
    lines.append("**三、解答题**（写下题号即可）")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 判分表（对/错/不会/半会/粗心）")
    lines.append("")
    lines.append("| 题号 | 题型 | 判分 |")
    lines.append("| --- | --- | --- |")
    for type_key in ("choice", "fill", "solution"):
        for idx, q in enumerate(sections_plan[type_key], start=1):
            lines.append(f"| {TYPE_ORDER[type_key]}{idx} | {TYPE_ZH[type_key]} |  |")
    lines.append("")
    lines.append("## 关联")
    lines.append("")
    lines.append(f"- 答案：[[卷子-{num}-答案]]")
    lines.append("- 错题本：[[错题本]]")
    lines.append("- 进度：[[进度总览]]")
    lines.append("")
    return "\n".join(lines)


def render_answers(schema, paper_id, sections_plan):
    num = paper_id.split("-")[-1]
    lines = []
    lines.append("---")
    lines.append("type: 答案卷")
    lines.append(f"paper_id: {paper_id}")
    lines.append(f"date: {lib880.today_str()}")
    lines.append(f"updated: {lib880.today_str()}")
    lines.append(f"subject: {schema['subject']}")
    lines.append(f"tags: [{schema['subject']}, 880, 答案]")
    lines.append("---")
    lines.append("")
    lines.append(f"# 卷子-{num} 答案与解析")
    lines.append("")
    lines.append(f"> [!info] 卷头")
    lines.append(f"> 答案与解析摘自李林880解析册（按做题本↔解析册内容对齐）。")
    lines.append(f"> 对应卷子：[[卷子-{num}]]")
    lines.append("")
    for type_key in ("choice", "fill", "solution"):
        if type_key == "solution":
            lines.append("## 三、解答题")
        else:
            lines.append(f"## {TYPE_ORDER[type_key]}、{TYPE_ZH[type_key]}")
        lines.append("")
        for idx, q in enumerate(sections_plan[type_key], start=1):
            lines.append(f"**{idx}.** " + (f"答案：**{q['answer']}**" if q.get("answer") else "（见解析）"))
            lines.append("")
            if q.get("solution"):
                lines.append(q["solution"].strip())
                lines.append("")
            if q.get("answer_status") == "missing":
                lines.append("> ⚠️ 解析册中未找到该题答案。")
                lines.append("")
        lines.append("")
    lines.append("## 关联")
    lines.append("")
    lines.append(f"- 对应卷子：[[卷子-{num}]]")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--ignore-extension", action="store_true")
    ap.add_argument("--no-weakness", action="store_true")
    args = ap.parse_args()

    schema = lib880.load_schema()
    index = lib880.load_index()
    lib880.build_index_map(index)
    attempts = lib880.load_attempts()
    papers = lib880.load_papers()

    if args.seed is not None:
        random.seed(args.seed)

    n = args.n
    if n is None:
        existing = [
            int(p["paper_id"].split("-")[-1])
            for p in papers["papers"] if p["paper_id"].startswith("paper-")
        ]
        n = (max(existing) + 1) if existing else 1
    paper_id = f"paper-{n:02d}"

    weakness = {} if args.no_weakness else lib880.chapter_weakness(schema, index, attempts)
    quota = effective_quota(schema, weakness)

    # 上一张卷的题目，用于避免立即重复
    avoid = set()
    if papers["papers"]:
        avoid = {q["qid"] for q in papers["papers"][-1]["questions"]}

    sections_plan = {}
    all_picked = []
    for type_key, spec in schema["paper"]["sections"].items():
        picked = []
        for chapter_no in sorted(quota):
            k = quota[chapter_no].get(type_key, 0)
            if k <= 0:
                continue
            picked += pick_cell(schema, index, attempts, chapter_no, type_key, k,
                                args.ignore_extension, avoid)
        random.shuffle(picked)
        picked = picked[: spec["count"]]
        sections_plan[type_key] = picked
        all_picked += picked

    # 校验合计
    total = sum(len(v) for v in sections_plan.values())
    if total != 22:
        print(f"!! 卷子题目数异常: {total}（预期 22）", file=sys.stderr)

    # 写文件
    lib880.PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    paper_path = lib880.PAPERS_DIR / f"卷子-{n:02d}.md"
    answer_path = lib880.PAPERS_DIR / f"卷子-{n:02d}-答案.md"
    paper_path.write_text(render_paper(schema, paper_id, sections_plan, index["by_id"]),
                          encoding="utf-8")
    answer_path.write_text(render_answers(schema, paper_id, sections_plan), encoding="utf-8")

    # 记录
    papers["papers"].append({
        "paper_id": paper_id,
        "date": lib880.today_str(),
        "duration_minutes": schema["paper"]["duration_minutes"],
        "quota_used": quota,
        "questions": [
            {"qid": q["id"], "section": type_key,
             "paper_no": f"{TYPE_ORDER[type_key]}{i}"}
            for type_key, qs in sections_plan.items()
            for i, q in enumerate(qs, start=1)
        ],
        "status": "created",
        "weakness_scores": weakness,
    })
    lib880.save_papers(papers)

    print(f"已生成卷子：{paper_path}")
    print(f"已生成答案：{answer_path}")
    print(f"卷子规格：选择 {len(sections_plan['choice'])} · 填空 {len(sections_plan['fill'])} · 解答 {len(sections_plan['solution'])}")
    if weakness:
        wl = sorted(weakness.items(), key=lambda kv: -kv[1])
        print("弱点分：", ", ".join(f"第{k}章={v:.2f}" for k, v in wl))


if __name__ == "__main__":
    main()
