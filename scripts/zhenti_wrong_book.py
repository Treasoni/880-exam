#!/usr/bin/env python3
"""zhenti_wrong_book.py — 生成考研数学真题错题本（按外部笔记体系），并维护真题库。

真题系统独立于 880：独立事实源、独立产物、独立复习状态，不进 880 进度总览，
也不影响 880 的拼卷配额与弱点分。

用法：
  python3 scripts/zhenti_wrong_book.py                      # 重新生成真题错题本
  python3 scripts/zhenti_wrong_book.py --modules            # 列出推导出的模块清单
  python3 scripts/zhenti_wrong_book.py --list               # 列出全部真题及状态
  python3 scripts/zhenti_wrong_book.py --record zt-2021-数二-解答3=不会
  python3 scripts/zhenti_wrong_book.py --mark zt-2021-数二-解答3=已掌握
  python3 scripts/zhenti_wrong_book.py --redo zt-2021-数二-解答3   # 重练：只给题干
  python3 scripts/zhenti_wrong_book.py --check              # 盘面产物是否陈旧（不写文件）
  # Windows 请把 python3 换成 py -3（如 py -3 scripts/zhenti_wrong_book.py）
"""

import argparse
import difflib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib880
from wrong_book import demote_solution_headings

PROBLEMS_PATH = lib880.ZHENTI_PROBLEMS_PATH
OUTPUT_PATH = lib880.ZHENTI_WRONG_BOOK_PATH

# 模块清单的推导根：外部笔记体系里「含 错题本.md 的目录」才是错题归档处
MODULE_ROOTS = (
    ("高数", lib880.ROOT / "external-notes/考研数学"),
    ("线代", lib880.ROOT / "external-notes/线性代数"),
)

COVERAGE_STATES = ("未做", "做过", "已复盘")


def derive_modules():
    """从外部笔记目录推导模块清单——不硬编码。

    判据是「该目录是不是一个错题归档处」：目录下存在 `错题本.md`。
    外部体系增删模块时清单自动跟上；`0-基础知识`（纯速查表）、`assets`
    这类无错题本的目录天然出局，不会被误当成模块。
    """
    modules = {}
    for subject, root in MODULE_ROOTS:
        found = []
        if root.is_dir():
            for d in sorted(root.iterdir()):
                if d.is_dir() and (d / "错题本.md").exists():
                    found.append(d.name)
        modules[subject] = found
    return modules


def module_index():
    """返回 {模块名: (科目, 外部目录相对路径)}，供归档与链接候选使用。"""
    out = {}
    for subject, root in MODULE_ROOTS:
        if not root.is_dir():
            continue
        for name in derive_modules()[subject]:
            out[name] = (subject, root.relative_to(lib880.ROOT) / name)
    return out


def load_problems():
    if not PROBLEMS_PATH.exists():
        return {"version": 1, "problems": {}, "coverage": {}}
    doc = json.loads(PROBLEMS_PATH.read_text(encoding="utf-8"))
    doc.setdefault("problems", {})
    doc.setdefault("coverage", {})
    return doc


def save_problems(doc):
    """写事实源。硬护栏：只允许写 workspace/ 下，绝不触碰只读的外部笔记库。"""
    rel = PROBLEMS_PATH.relative_to(lib880.ROOT)
    if not str(rel).startswith("workspace/"):
        raise SystemExit(f"拒绝写入 workspace/ 之外的路径：{rel}")
    PROBLEMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROBLEMS_PATH.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def problem_key(p):
    """真题坐标唯一键：zt-{年}-{卷种}-{题号}。"""
    return p["id"]


def attempts_of(p):
    return p.get("attempts") or []


def latest_grade_key(p):
    a = attempts_of(p)
    return a[-1].get("grade") if a else None


def tally(p):
    """返回 (错次数, 对次数)——错=非「对」的判分，对=「对」。"""
    a = attempts_of(p)
    return (sum(1 for x in a if x.get("grade") != "correct"),
            sum(1 for x in a if x.get("grade") == "correct"))


def validate_text(text, zt_id, field):
    """写入前拒绝会破坏 Obsidian 渲染的文本（判据同源 lib880，不另存正则）。"""
    if not text:
        return
    decoded = lib880.decode_literal_newlines(text)
    errors = []
    if lib880.CONTROL_CHAR_RE.search(decoded):
        errors.append("含控制字符（检查 LaTeX 反斜杠是否被转义）")
    try:
        normalized = lib880.normalize_math_delimiters(decoded)
    except ValueError as exc:
        errors.append(str(exc))
    else:
        if lib880.LEGACY_INLINE_RE.search(normalized):
            errors.append("归一后仍残留 \\(...\\) 行内定界符；请改用 $...$")
        errors.extend(lib880.display_math_errors(normalized))
    if errors:
        raise ValueError(f"{zt_id}.{field} 无法渲染：" + "；".join(errors))


def render(schema, doc, modules):
    grade_zh = {g["key"]: g["zh"] for g in schema["grades"]}
    cause_labels = list(schema["analysis"]["cause_labels"])
    problems = doc["problems"]
    items = []
    for pid, p in problems.items():
        key = latest_grade_key(p)
        n_wrong, n_right = tally(p)
        state = p.get("review_state") or "未复习"
        items.append({
            "id": pid, "p": p, "module": p.get("module") or "（未归档）",
            "grade": key, "grade_zh": grade_zh.get(key, "—") if key else "—",
            "tally": f"错{n_wrong} 对{n_right}" if (n_wrong or n_right) else "—",
            "state": state,
            "year": p.get("year") or 0, "paper": p.get("paper") or "",
        })
    active = [e for e in items if e["grade"] != "correct" or e["state"] != "已掌握"]
    mastered = [e for e in items if e["grade"] == "correct" and e["state"] == "已掌握"]
    n_focus = sum(1 for e in active if e["grade"] in
                  set(schema["wrong_book"]["focus_grades"]))

    L = []
    L.append("---")
    L.append("type: 错题本")
    L.append(f"updated: {lib880.today_str()}")
    mod_list = "、".join(modules["高数"] + modules["线代"])
    L.append(f"tags: [考研数学, 真题, 错题本]")
    L.append(f"total: {len(items)}")
    L.append(f"focus_count: {n_focus}")
    L.append(f"mastered_count: {len(mastered)}")
    L.append("---")
    L.append("")
    L.append("# 考研数学真题错题本")
    L.append("")
    L.append("> [!info] 说明")
    L.append("> 本册只收**真题**（数一/数二/数三），独立于 880 习题系统：不进 880 进度总览，不影响拼卷配额。")
    L.append("> 模块归属对齐你的外部笔记体系；`external-notes/` 为只读引用，本册只链接不写入。")
    L.append("")
    L.append(f"共 {len(items)} 道真题记录（待复习 {len(active)} · 重点 {n_focus} · 已掌握 {len(mastered)}）")
    L.append("")
    L.append(f"模块体系（推导自外部笔记 {len(modules['高数'])} 高数 + {len(modules['线代'])} 线代）：{mod_list}")
    L.append("")

    if not items:
        L.append("（暂无真题错题，继续加油 ✅）")
        L.append("")

    # —— 一、按模块（章节为主）——
    L.append("## 一、模块错题")
    L.append("")
    by_mod = {}
    for e in active:
        by_mod.setdefault(e["module"], []).append(e)
    for mod in modules["高数"] + modules["线代"]:
        es = by_mod.get(mod)
        if not es:
            continue
        L.append(f"### {mod}（{len(es)} 题）")
        L.append("")
        L.append("| 年份 | 卷种 | 题号 | 判分 | 错/对 | 复习状态 |")
        L.append("| --- | --- | --- | --- | --- | --- |")
        for e in sorted(es, key=lambda x: (x["year"], x["paper"], str(x["p"].get("no")))):
            L.append(f"| {e['year']} | {e['paper']} | {e['p'].get('no','')} | "
                     f"{e['grade_zh']} | {e['tally']} | {e['state']} |")
        L.append("")
        for e in sorted(es, key=lambda x: (x["year"], x["paper"], str(x["p"].get("no")))):
            p = e["p"]
            L.append(f"#### {p.get('year')} {p.get('paper')} {p.get('no')} · "
                     f"判分：{e['grade_zh']} · {e['tally']} · {e['state']}")
            L.append("")
            if p.get("stem"):
                L.append(f"**题干：** {lib880.prepare_solution_text(p['stem'])}")
                L.append("")
            if p.get("stem_image"):
                L.append(f"![[{Path(p['stem_image']).name}]]")
                L.append("")
            if p.get("answer"):
                L.append(f"**答案：** {lib880.markdown_math_answer(p['answer'])}")
                L.append("")
            else:
                L.append("**答案：**（待补）")
                L.append("")
            if p.get("solution"):
                L.append("**解析：**")
                L.append("")
                L.append(demote_solution_headings(
                    lib880.prepare_solution_text(p["solution"]), 4))
                L.append("")
            if p.get("solution_image"):
                L.append(f"![[{Path(p['solution_image']).name}]]")
                L.append("")
            cause = p.get("cause") or {}
            if cause.get("label"):
                if cause["label"] not in cause_labels:
                    raise ValueError(
                        f"{e['id']}.cause.label 非法：{cause['label']}（可选 {cause_labels}）")
                L.append("> [!info] 错因分析")
                L.append(f"> **错因：** {cause['label']}")
                if cause.get("step"):
                    L.append(f"> **出错环节：** {cause['step']}")
                if cause.get("advice"):
                    L.append(f"> **建议：** {cause['advice']}")
                L.append("")
            links = p.get("links") or []
            parts = []
            for link in links:
                if link.get("path") and link.get("anchor"):
                    label = link.get("label") or link["anchor"]
                    parts.append(f"[[{link['path']}#{link['anchor']}|{label}]]")
            if parts:
                L.append("*相关笔记：" + " · ".join(parts) + "*")
                L.append("")
            if attempts_of(p):
                hist = " · ".join(
                    f"{a.get('date','?')} {grade_zh.get(a.get('grade'), a.get('grade'))}"
                    for a in attempts_of(p))
                L.append(f"*历史：{hist}*")
                L.append("")

    # —— 二、年份索引 ——
    L.append("## 二、年份索引")
    L.append("")
    if items:
        L.append("| 年份 | 卷种 | 题号 | 模块 | 判分 | 错/对 | 复习状态 |")
        L.append("| --- | --- | --- | --- | --- | --- | --- |")
        for e in sorted(items, key=lambda x: (x["year"], x["paper"], str(x["p"].get("no")))):
            L.append(f"| {e['year']} | {e['paper']} | {e['p'].get('no','')} | {e['module']} | "
                     f"{e['grade_zh']} | {e['tally']} | {e['state']} |")
    else:
        L.append("（暂无记录）")
    L.append("")

    # —— 三、年份覆盖表 ——
    L.append("## 三、年份覆盖表")
    L.append("")
    cov = {}
    for key, v in (doc.get("coverage") or {}).items():
        cov[key] = {"status": v.get("status", "未做"), "note": v.get("note", "")}
    # 派生状态按「年份-卷种」**整卷聚合**：本卷任一条有作答即算「做过」。
    # 不能用逐条 setdefault——那等于拿本卷第一条记录定整卷状态，首条恰好没作答
    # 就把整卷误锁成「未做」（2010-数二 8 题里 6 题有 attempts，却显示「未做」）。
    # 事实源里手写的 coverage 覆盖仍然优先。
    for key in {f"{e['year']}-{e['paper']}" for e in items}:
        if key in cov:
            continue
        done = any(attempts_of(e["p"]) for e in items
                   if f"{e['year']}-{e['paper']}" == key)
        cov[key] = {"status": "做过" if done else "未做", "note": ""}
    if cov:
        L.append("| 年份-卷种 | 状态 | 本册题数 | 备注 |")
        L.append("| --- | --- | --- | --- |")
        for key in sorted(cov, reverse=True):
            n = sum(1 for e in items if f"{e['year']}-{e['paper']}" == key)
            L.append(f"| {key} | {cov[key]['status']} | {n} | {cov[key]['note']} |")
    else:
        L.append("（尚无覆盖记录）")
    L.append("")

    # —— 已掌握归档 ——
    if mastered:
        L.append(f"## 四、已掌握归档（{len(mastered)} 题）")
        L.append("")
        L.append("> [!success] 抽查用")
        L.append("> 以下真题已重练做对，保留解析与错因分析供后续抽查。")
        L.append("")
        for e in sorted(mastered, key=lambda x: (x["year"], x["paper"])):
            L.append(f"### {e['year']} {e['paper']} {e['p'].get('no','')} · {e['module']}")
            L.append("")
            if e["p"].get("stem"):
                L.append(f"**题干：** {lib880.prepare_solution_text(e['p']['stem'])}")
                L.append("")
            if e["p"].get("answer"):
                L.append(f"**答案：** {lib880.markdown_math_answer(e['p']['answer'])}")
                L.append("")
            L.append("")

    L.append("## 关联")
    L.append("")
    L.append("- 880 错题本：[[错题本]]")
    L.append("")
    return "\n".join(L)


def build():
    """按当前事实源渲染真题错题本文本但不写盘（generate 与 --check 共用）。"""
    schema = lib880.load_schema(lib880.SUBJECT_HIGH_MATH)
    doc = load_problems()
    modules = derive_modules()
    mods = module_index()
    known = set(mods)
    for pid, p in doc["problems"].items():
        for field in lib880.ZHENTI_SOURCE_FIELDS:
            validate_text(p.get(field), pid, field)
        m = p.get("module")
        if m and m not in known:
            raise ValueError(f"{pid}.module 不在推导出的模块清单里：{m}（可选 {sorted(known)}）")
    return OUTPUT_PATH, render(schema, doc, modules)


_VOLATILE_PREFIXES = ("updated:",)


def _stable_view(text):
    return "\n".join(l for l in text.splitlines() if not l.startswith(_VOLATILE_PREFIXES))


def generate():
    path, text = build()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def check(context=2):
    path, text = build()
    if not path.exists():
        return path, True, ["（产物不存在，尚未生成）"]
    on_disk = path.read_text(encoding="utf-8")
    if _stable_view(on_disk) == _stable_view(text):
        return path, False, []
    diff = list(difflib.unified_diff(
        _stable_view(on_disk).splitlines(), _stable_view(text).splitlines(),
        fromfile=f"{path.name}（盘面）", tofile=f"{path.name}（按事实源渲染）",
        lineterm="", n=context))
    return path, True, diff


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modules", action="store_true", help="列出推导出的模块清单")
    ap.add_argument("--list", action="store_true", help="列出全部真题及状态")
    ap.add_argument("--record", action="append", default=[], help="zt-id=五态")
    ap.add_argument("--mark", action="append", default=[], help="zt-id=复习状态")
    ap.add_argument("--redo", metavar="ZT_ID", help="重练模式：只给题干，隐去答案与解析")
    ap.add_argument("--check", action="store_true", help="只比对盘面产物，不写文件")
    args = ap.parse_args()

    schema = lib880.load_schema(lib880.SUBJECT_HIGH_MATH)
    grade_zh = {g["key"]: g["zh"] for g in schema["grades"]}
    zh_grade = {v: k for k, v in grade_zh.items()}

    if args.modules:
        mods = derive_modules()
        for subject in ("高数", "线代"):
            print(f"{subject}（{len(mods[subject])}）")
            for m in mods[subject]:
                print(f"  - {m}")
        return

    if args.check:
        path, is_stale, diff = check()
        rel = path.relative_to(lib880.ROOT)
        if is_stale:
            print(f"✗ {rel} 与事实源不一致（产物陈旧）")
            for line in diff[:40]:
                print("    " + line)
            sys.exit(1)
        print(f"✓ {rel} 与事实源一致")
        return

    doc = load_problems()
    problems = doc["problems"]

    if args.redo:
        p = problems.get(args.redo)
        if not p:
            print(f"!! 未知真题 {args.redo}", file=sys.stderr)
            sys.exit(2)
        print(f"# {p.get('year')} {p.get('paper')} {p.get('no')}（重练模式：答案与解析已隐去）")
        print()
        print(p.get("stem") or "（题干待补）")
        if p.get("stem_image"):
            print()
            print(f"![[{Path(p['stem_image']).name}]]")
        print()
        print("做完后回报结果，用 --record 记录："
              f"python3 scripts/zhenti_wrong_book.py --record {args.redo}=<对|错|不会|半会|粗心>")
        return

    valid_states = set(schema["wrong_book"]["review_states"])
    changed = False
    for spec in args.record:
        if "=" not in spec:
            print(f"!! 无效 --record: {spec}（应为 zt-id=判分）", file=sys.stderr)
            sys.exit(2)
        pid, zh = spec.split("=", 1)
        if zh not in zh_grade:
            print(f"!! 无效判分 {zh}（可选 {sorted(zh_grade)}）", file=sys.stderr)
            sys.exit(2)
        if pid not in problems:
            print(f"!! 未知真题 {pid}", file=sys.stderr)
            sys.exit(2)
        problems[pid].setdefault("attempts", []).append(
            {"date": lib880.today_str(), "grade": zh_grade[zh]})
        changed = True
        print(f"已记录 {pid} → {zh}")

    for spec in args.mark:
        if "=" not in spec:
            print(f"!! 无效 --mark: {spec}（应为 zt-id=状态）", file=sys.stderr)
            sys.exit(2)
        pid, state = spec.split("=", 1)
        if state not in valid_states:
            print(f"!! 无效状态 {state}（可选 {valid_states}）", file=sys.stderr)
            sys.exit(2)
        if pid not in problems:
            print(f"!! 未知真题 {pid}", file=sys.stderr)
            sys.exit(2)
        problems[pid]["review_state"] = state
        problems[pid]["review_updated"] = lib880.today_str()
        changed = True
        print(f"已更新 {pid} → {state}")

    if changed:
        save_problems(doc)
        # 记录结果后顺带推进复习状态：做对 → 已重做（不自动置「已掌握」，由用户确认）
        for spec in args.record:
            pid = spec.split("=", 1)[0]
            p = problems[pid]
            if latest_grade_key(p) == "correct" and (p.get("review_state") or "未复习") == "未复习":
                p["review_state"] = "已重做"
                p["review_updated"] = lib880.today_str()
        save_problems(doc)

    if args.list:
        for pid, p in sorted(problems.items(),
                             key=lambda kv: (kv[1].get("year", 0), kv[1].get("paper", ""))):
            n_wrong, n_right = tally(p)
            print(f"{pid}  {p.get('module','—'):<12} "
                  f"{grade_zh.get(latest_grade_key(p), '—'):<4} 错{n_wrong} 对{n_right}  "
                  f"{p.get('review_state') or '未复习'}")
        return

    path = generate()
    items = len(problems)
    print(f"已更新真题错题本：{path.relative_to(lib880.ROOT)}（共 {items} 道真题）")


if __name__ == "__main__":
    main()