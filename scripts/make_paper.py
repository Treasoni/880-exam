#!/usr/bin/env python3
"""make_paper.py — 按真题模式拼卷（配额浮动 + 难度配比 + 加权随机）。

用法：
  python3 scripts/make_paper.py                     # 自动取下一卷号
  python3 scripts/make_paper.py --n 3 --seed 42     # 指定卷号与随机种子
  python3 scripts/make_paper.py --ignore-extension  # 不使用拓展题
  python3 scripts/make_paper.py --no-weakness       # 忽略弱点浮动
  # Windows 请把 python3 换成 py -3（如 py -3 scripts/make_paper.py）
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
        and q.get("answer_status") == "ok"
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
        d = max(candidates, key=lambda d: (mix.get(d, 0),
                                            len(cell_pool(index, chapter_no, type_key, d)) - alloc[d]))
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
            # 题目原文（与卷子保持一致），再给答案与解析
            lines.append(f"**{idx}.** {q.get('text', '').strip()}")
            lines.append("")
            lines.append("**答案：** " + (f"**{q['answer']}**" if q.get("answer") else "（见解析）"))
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


def _cell_escape(s):
    """表格单元格转义：把 | 换成 \\|，把换行折叠成空格，避免破坏 Markdown 表格。"""
    return str(s).replace("|", "\\|").replace("\n", " ").strip()


def render_grading_card(schema, paper_id, sections_plan):
    """生成判分卡：每题一行（题号/答案/对/错/不会/半会/粗心），用户勾选后由 grade.py --sheet 读取。"""
    num = paper_id.split("-")[-1]
    grade_cols = [g["zh"] for g in schema["grades"]]  # 对/错/不会/半会/粗心
    lines = []
    lines.append("---")
    lines.append("type: 判分卡")
    lines.append(f"paper_id: {paper_id}")
    lines.append(f"date: {lib880.today_str()}")
    lines.append(f"updated: {lib880.today_str()}")
    lines.append(f"subject: {schema['subject']}")
    lines.append(f"tags: [{schema['subject']}, 880, 判分卡]")
    lines.append("---")
    lines.append("")
    lines.append(f"# 判分卡 · 卷子-{num}")
    lines.append("")
    lines.append("> [!info] 判分说明")
    lines.append("> 对照答案核对，在对应状态列写 `x`（对/错/不会/半会/粗心）。没做的题留空即可。")
    lines.append("")
    for type_key in ("choice", "fill", "solution"):
        lines.append(f"## {TYPE_ORDER[type_key]}、{TYPE_ZH[type_key]}")
        lines.append("")
        lines.append("| # | 答案 | " + " | ".join(grade_cols) + " |")
        lines.append("| --- | --- | " + " | ".join(["---"] * len(grade_cols)) + " |")
        for idx, q in enumerate(sections_plan[type_key], start=1):
            if type_key == "solution":
                ans = "（见答案卷）"
            elif q.get("answer_status") == "missing" or not q.get("answer"):
                ans = "（解析册未找到）"
            else:
                ans = q["answer"]
            cells = " | ".join("[ ]" for _ in grade_cols)
            lines.append(f"| {idx} | {_cell_escape(ans)} | {cells} |")
        lines.append("")
    lines.append("## 关联")
    lines.append("")
    lines.append(f"- 卷子：[[卷子-{num}]]")
    lines.append(f"- 答案：[[卷子-{num}-答案]]")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--ignore-extension", action="store_true")
    ap.add_argument("--no-weakness", action="store_true")
    ap.add_argument("--replace-ungraded", action="store_true",
                    help="仅替换尚无判分记录的同编号卷子；防止意外覆盖学习记录")
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

    existing_papers = [p for p in papers["papers"] if p["paper_id"] == paper_id]
    paper_dir = lib880.paper_dir(paper_id)
    if existing_papers or paper_dir.exists():
        has_attempts = any(a.get("paper_id") == paper_id for a in attempts["attempts"])
        if not args.replace_ungraded:
            ap.error(f"卷子 {paper_id} 已存在；请换一个 --n。仅未判分卷子可用 --replace-ungraded 重生成")
        if len(existing_papers) != 1 or has_attempts:
            ap.error(f"卷子 {paper_id} 已有判分记录或记录异常，拒绝覆盖以保护学习数据")

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

    # 在落盘前严格校验：题库不足绝不能生成一张残缺的卷子。
    expected_total = sum(spec["count"] for spec in schema["paper"]["sections"].values())
    total = sum(len(v) for v in sections_plan.values())
    shortages = [
        f"{TYPE_ZH[t]} {len(sections_plan.get(t, []))}/{spec['count']}"
        for t, spec in schema["paper"]["sections"].items()
        if len(sections_plan.get(t, [])) != spec["count"]
    ]
    if total != expected_total or shortages:
        ap.error("题库可用题目不足，未生成卷子：" + "；".join(shortages))

    # 写文件（每卷一个子文件夹：卷子/答案/判分卡）
    paper_dir.mkdir(parents=True, exist_ok=True)
    paper_path = paper_dir / f"卷子-{n:02d}.md"
    answer_path = paper_dir / f"卷子-{n:02d}-答案.md"
    card_path = paper_dir / f"判分卡-{n:02d}.md"
    paper_path.write_text(render_paper(schema, paper_id, sections_plan, index["by_id"]),
                          encoding="utf-8")
    answer_path.write_text(render_answers(schema, paper_id, sections_plan), encoding="utf-8")
    card_path.write_text(render_grading_card(schema, paper_id, sections_plan), encoding="utf-8")

    # 记录
    paper_record = {
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
    }
    if existing_papers:
        papers["papers"] = [p for p in papers["papers"] if p["paper_id"] != paper_id]
    papers["papers"].append(paper_record)
    lib880.save_papers(papers)

    print(f"已生成卷子：{paper_path}")
    print(f"已生成答案：{answer_path}")
    print(f"已生成判分卡：{card_path}")
    print(f"卷子规格：选择 {len(sections_plan['choice'])} · 填空 {len(sections_plan['fill'])} · 解答 {len(sections_plan['solution'])}")
    if weakness:
        wl = sorted(weakness.items(), key=lambda kv: -kv[1])
        print("弱点分：", ", ".join(f"第{k}章={v:.2f}" for k, v in wl))


if __name__ == "__main__":
    main()
