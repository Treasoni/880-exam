#!/usr/bin/env python3
"""wrong_book.py — 生成错题本（按章节），并可更新复习状态。

用法：
  python3 scripts/wrong_book.py                     # 重新生成错题本
  python3 scripts/wrong_book.py --mark qid=已掌握   # 更新某题复习状态后重新生成
  python3 scripts/wrong_book.py --list-states       # 列出全部错题及状态
  python3 scripts/wrong_book.py --check --all       # 检查盘面产物是否已陈旧（不写文件）
  # Windows 请把 python3 换成 py -3（如 py -3 scripts/wrong_book.py）
"""

import argparse
import difflib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib880

GRADE_ZH = {g["key"]: g["zh"] for g in lib880.load_schema()["grades"]}
DIFF_ZH = {"basic": "基础", "comprehensive": "综合", "extension": "拓展"}
TYPE_ZH = {"choice": "选择题", "fill": "填空题", "solution": "解答题"}
CN = {n: lib880.chapter_number_zh(n) for n in range(1, 100)}

HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*)$")


def validate_solution_text(text, qid):
    """在写入错题本前拒绝会破坏 Obsidian 渲染的解析文本。

    判据统一取自 lib880（CONTROL_CHAR_RE / normalize_math_delimiters /
    display_math_errors），不再在本文件另存一份正则——行内 ``\\(...\\)`` 漏检就是
    因为这里和 lint_content.py 各存了一份只查独立式的旧正则。独立式 ``\\[...\\]``
    与转义的反斜杠括号由 ``normalize_math_delimiters`` 统一拒绝（此处不再重复判一遍，
    避免同一问题报两次）。

    字形换行与行内定界符由渲染层归一（``prepare_solution_text``）；归一前先解码
    字面量 ``\\n``，否则整段解析只算一行、公式块根本无法成对识别。归一失败、
    定界符残留、或独立公式块结构错误（``$$`` 多写/错位/丢失）一律拒绝写入。
    """
    decoded = lib880.decode_literal_newlines(text)
    errors = []
    if lib880.CONTROL_CHAR_RE.search(decoded):
        errors.append("含控制字符（检查 LaTeX 反斜杠是否被 Python 字符串转义）")
    try:
        normalized = lib880.normalize_math_delimiters(decoded)
    except ValueError as exc:
        errors.append(str(exc))
    else:
        if lib880.LEGACY_INLINE_RE.search(normalized):
            errors.append("归一后仍残留 \\(...\\) 行内定界符；请改用 $...$")
        errors.extend(lib880.display_math_errors(normalized))
    if errors:
        raise ValueError(f"题目 {qid} 的解析无法渲染：" + "；".join(errors))


def demote_solution_headings(text, item_level):
    """把解析文本内部的 Markdown 标题降到条目标题之下，保证嵌套排版。

    条目标题为 item_level 级（待复习条目 = 4，已掌握归档条目 = 5）。
    解析中最浅的标题被降到 item_level+1 级，更深的标题保持相对层级，
    最深不超过 6 级（Obsidian 支持的最大标题深度）。
    不含标题的解析原样返回。
    """
    levels = []
    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m:
            levels.append(len(m.group(1)))
    if not levels:
        return text
    base = min(levels)
    out = []
    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m:
            lvl = len(m.group(1))
            new_lvl = min(6, item_level + 1 + (lvl - base))
            out.append("#" * new_lvl + " " + m.group(2).strip())
        else:
            out.append(line)
    return "\n".join(out)


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
           solution_overrides=None, subject=lib880.SUBJECT_HIGH_MATH):
    ext_links = ext_links or {}
    analysis = analysis or {"items": {}}
    overrides = lib880.load_solution_overrides() if solution_overrides is None else solution_overrides
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
            solution = lib880.effective_solution(q, overrides)
            if solution:
                lines.append("**解析：**")
                lines.append("")
                lines.append(demote_solution_headings(
                    lib880.prepare_solution_text(solution), 4))
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
                solution = lib880.effective_solution(q, overrides)
                if solution:
                    lines.append("**解析：**")
                    lines.append("")
                    lines.append(demote_solution_headings(
                        lib880.prepare_solution_text(solution), 5))
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


def build(subject=lib880.SUBJECT_HIGH_MATH):
    """按当前事实源渲染错题本文本但不写盘（generate 与 --check 共用）。"""
    subject = lib880.normalize_subject(subject)
    schema = lib880.load_schema(subject)
    index = lib880.load_index(subject)
    lib880.build_index_map(index)
    attempts = lib880.load_attempts()

    # 先校验事实源（含解析覆盖层），再生成产物，避免把坏公式写进错题本后才发现。
    overrides = lib880.load_solution_overrides()
    for q in index["questions"]:
        solution = lib880.effective_solution(q, overrides)
        if solution:
            validate_solution_text(solution, q["id"])

    active, mastered = build_wrong_lists(schema, index, attempts)
    text = render(schema, index, attempts, active, mastered,
                  lib880.load_external_links(), lib880.load_analysis(), overrides, subject)
    return lib880.wrong_book_path(subject), text, active, mastered


def generate(subject=lib880.SUBJECT_HIGH_MATH):
    """Regenerate one subject's wrong-book note and return its summary."""
    output_path, text, active, mastered = build(subject)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    return output_path, active, mastered


# 渲染里随当天变化的行，比对产物新旧时忽略
_VOLATILE_PREFIXES = ("updated:",)


def _stable_view(text):
    return "\n".join(
        line for line in text.splitlines()
        if not line.startswith(_VOLATILE_PREFIXES)
    )


def check(subject=lib880.SUBJECT_HIGH_MATH, context=2):
    """比对盘面上的错题本与按当前事实源渲染的结果，返回 (path, stale, diff 行)。

    产物不会自动跟随事实源更新：索引修好、生成器收紧后，盘面上的旧文件仍可能
    是坏的（2026-09-13 用户看到的坏渲染正是这种陈旧产物）。这里渲染一份内存副本
    与磁盘内容比对，`updated:` 这类当天变化的行不参与比较。
    """
    path, text, _, _ = build(subject)
    if not path.exists():
        return path, True, ["（产物不存在，尚未生成）"]
    on_disk = path.read_text(encoding="utf-8")
    if _stable_view(on_disk) == _stable_view(text):
        return path, False, []
    diff = list(difflib.unified_diff(
        _stable_view(on_disk).splitlines(),
        _stable_view(text).splitlines(),
        fromfile=f"{path.name}（盘面）", tofile=f"{path.name}（按事实源渲染）",
        lineterm="", n=context))
    return path, True, diff


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", default=lib880.SUBJECT_HIGH_MATH,
                    help="题库：high-math（默认）或 linear-algebra")
    ap.add_argument("--mark", action="append", default=[], help="qid=状态")
    ap.add_argument("--list-states", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="只比对盘面产物与事实源是否一致，不写文件；陈旧则退出码 1")
    ap.add_argument("--all", action="store_true", help="配合 --check：两个科目都查")
    args = ap.parse_args()

    try:
        subject = lib880.normalize_subject(args.subject)
    except ValueError as exc:
        ap.error(str(exc))

    if args.check:
        subjects = ([lib880.SUBJECT_HIGH_MATH, lib880.SUBJECT_LINEAR_ALGEBRA]
                    if args.all else [subject])
        stale = 0
        for subj in subjects:
            path, is_stale, diff = check(subj)
            rel = path.relative_to(lib880.ROOT)
            if is_stale:
                stale += 1
                print(f"✗ {rel} 与事实源不一致（产物陈旧）")
                for line in diff[:40]:
                    print("    " + line)
                if len(diff) > 40:
                    print(f"    … 共 {len(diff)} 行 diff")
            else:
                print(f"✓ {rel} 与事实源一致")
        if stale:
            print("按事实源重刷：python3 scripts/wrong_book.py --subject <high-math|linear-algebra>")
            sys.exit(1)
        return

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

    output_path, active, mastered = generate(subject)
    print(f"已更新错题本：{output_path}（待复习 {len(active)} 道 · 已掌握归档 {len(mastered)} 道）")


if __name__ == "__main__":
    main()
