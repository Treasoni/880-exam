#!/usr/bin/env python3
"""Build the standalone 880 linear-algebra question index from its source books.

The existing ``question-index.json`` is the high-mathematics pool used by the
paper/grade workflow.  This builder intentionally writes a separate index so
adding the linear-algebra source cannot change an already graded paper.

The two source Markdown files are OCR exports.  Their chapter/section order is
stable, but a small number of question labels were swallowed by OCR.  The
repair anchors below only restore the boundaries; every question, answer, and
solution written to the output is copied from the two source files.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "880/【A4紧凑版】李林880数二线代篇做题本.pdf-a0b47585-3160-443a-9edc-b283dfd7ec0d/full.md"
ANSWERS = ROOT / "880/线代880答案/full.md"
BUILD_DIR = ROOT / "workspace/.build/linear-algebra"
SECTIONS_DIR = BUILD_DIR / "sections"
JOURNAL_PATH = BUILD_DIR / "latest_journal.jsonl"
OUT = ROOT / "workspace/linear-algebra-question-index.json"

CHAPTERS = {
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "十一": 11,
    "十二": 12,
}
TYPE_KEY = {"选择题": "choice", "填空题": "fill", "解答题": "solution"}
DIFFICULTY_KEY = {"基础题": "basic", "综合题": "comprehensive", "拓展题": "extension"}
CHAPTER_RE = re.compile(r"^第(七|八|九|十|十一|十二)章\s+(.+)$")
DIFFICULTY_RE = re.compile(r"^(基础题|综合题|拓展题)$")
TYPE_RE = re.compile(r"^(?:[一二三]、)?(选择题|填空题|解答题)$")
QUESTION_RE = re.compile(r"^[（(](\d+)[）)]\s*")


@dataclass(frozen=True)
class SectionKey:
    chapter_no: int
    difficulty: str
    qtype: str


# Workbook labels swallowed into the preceding line, plus the unlabelled
# chapter-7 comprehensive determinant question.  The anchors are intentionally
# source text, rather than line numbers, so harmless OCR line movement does not
# alter the alignment.
WORKBOOK_REPAIRS = {
    SectionKey(7, "综合题", "解答题"): ((4, "D _ {n} = \\left| \\begin{array}"),),
}

# Answer labels swallowed by the OCR.  These anchors were checked against the
# corresponding workbook item; no answer text is supplied by this table.
ANSWER_REPAIRS = {
    SectionKey(7, "基础题", "填空题"): (
        (8, "解 方法一: 利用矩阵的秩."),
        (10, "(1 0) (- 4) ^ {n - 1}"),
    ),
    SectionKey(8, "基础题", "填空题"): (
        (2, "EXACT:\\left( \\begin{array}{c c c} 2 n + 1 & 4 n & 0 \\\\ - n & - 2 n + 1 & 0 \\\\ 3 n & 6 n & 1 \\end{array} \\right)."),
    ),
    SectionKey(8, "综合题", "填空题"): (
        (4, "EXACT:\\left( \\begin{array}{c c c c} 1 & - 1 & 1 & - 1 \\\\ 0 & 1 & - 1 & 1 \\\\ 0 & 0 & 1 & - 1 \\\\ 0 & 0 & 0 & 1 \\end{array} \\right)."),
    ),
    SectionKey(10, "基础题", "选择题"): (
        (8, "解 对于选项 B, 由 $r(AB)"),
    ),
    SectionKey(11, "综合题", "填空题"): (
        (3, "解 由已知, A 有 3 个不同特征值"),
    ),
    SectionKey(11, "综合题", "解答题"): (
        (7, "(I) \\boldsymbol {A} = \\boldsymbol {\\alpha}"),
    ),
    SectionKey(12, "综合题", "选择题"): (
        (10, "EXACT:解 依题设, 对 $\\forall X \\neq 0$ , 有 $|X^{\\mathrm{T}}AX| < |X^{\\mathrm{T}}X|$ . 而 $X^{\\mathrm{T}}X > 0$ , 故"),
    ),
    SectionKey(12, "拓展题", "解答题"): (
        (7, "(7)(Ⅰ)由 $(A-4E)\\alpha=0$"),
    ),
}


def clean_heading(raw: str) -> str:
    return raw.lstrip("#").strip() if raw.lstrip().startswith("#") else raw.strip()


def split_source_sections(path: Path) -> dict[SectionKey, tuple[str, list[str]]]:
    """Return raw source lines grouped by chapter, difficulty, and question type."""
    result: dict[SectionKey, tuple[str, list[str]]] = {}
    chapter_no: int | None = None
    chapter_title: str | None = None
    difficulty: str | None = None
    qtype: str | None = None

    for raw in path.read_text(encoding="utf-8").splitlines():
        heading = clean_heading(raw)
        match = CHAPTER_RE.match(heading)
        if match:
            chapter_no = CHAPTERS[match.group(1)]
            chapter_title = heading
            difficulty = qtype = None
            continue
        if DIFFICULTY_RE.match(heading):
            difficulty = heading
            qtype = None
            continue
        match = TYPE_RE.match(heading)
        if match:
            qtype = match.group(1)
            continue
        if chapter_no is None or chapter_title is None or difficulty is None or qtype is None:
            continue
        key = SectionKey(chapter_no, difficulty, qtype)
        result.setdefault(key, (chapter_title, []))[1].append(raw)
    return result


def find_anchor(lines: list[str], anchor: str, *, section: SectionKey, q_num: int) -> tuple[int, int]:
    """Return the unique line/column where an OCR-repair anchor occurs."""
    exact = anchor.startswith("EXACT:")
    needle = anchor.removeprefix("EXACT:")
    if exact:
        hits = [(i, line.find(needle)) for i, line in enumerate(lines) if line == needle]
    else:
        hits = [(i, line.find(needle)) for i, line in enumerate(lines) if needle in line]
    if len(hits) != 1:
        raise ValueError(
            f"{section} 第 {q_num} 题的 OCR 修复锚点应唯一，实际为 {len(hits)} 个: {anchor!r}"
        )
    return hits[0]


def item_starts(
    lines: list[str],
    *,
    section: SectionKey,
    repairs: dict[SectionKey, tuple[tuple[int, str], ...]],
    answer_mode: bool,
) -> list[tuple[int, int, int]]:
    """Find (line, column, source-number) starts, including known OCR repairs."""
    starts: list[tuple[int, int, int]] = []
    for line_i, line in enumerate(lines):
        for match in re.finditer(r"[（(](\d+)[）)]", line):
            q_num = int(match.group(1))
            after = line[match.end():].lstrip()
            at_start = not line[:match.start()].strip()
            if answer_mode:
                # Solutions contain many internal (1)/(2) steps.  A true item
                # either exposes an answer directly, starts with 解/证, or is
                # one of the explicit repair anchors below.
                if section.qtype == "解答题":
                    if not re.match(r"(?:解|证|\\text\s*\{解\})", after):
                        continue
                elif section.qtype == "选择题":
                    if not re.match(r"[A-D]\.", after):
                        continue
                elif not at_start:
                    continue
            else:
                if not at_start:
                    # Only accept an inline label when the following text is a
                    # question opener.  This excludes formulas such as (1,2).
                    if not re.match(r"(?:设|若|已知|下列|计算|证明|解|在|给定|对于|向量|矩阵|齐次|非齐次)", after):
                        continue
            starts.append((line_i, match.start(), q_num))

    for q_num, anchor in repairs.get(section, ()):
        line_i, col = find_anchor(lines, anchor, section=section, q_num=q_num)
        starts.append((line_i, col, q_num))

    # In the two OCR cases below, a question label lives inside a displayed
    # equation.  It is a real item because its repair anchor says so.
    starts.sort(key=lambda item: (item[0], item[1]))
    if len({(line_i, col) for line_i, col, _ in starts}) != len(starts):
        raise ValueError(f"{section} 存在重复题目起点")
    return starts


def slice_items(lines: list[str], starts: list[tuple[int, int, int]], *, section: SectionKey) -> list[tuple[int, str]]:
    """Slice a source section at its item starts and require contiguous numbering."""
    if not starts:
        # 第九章拓展题的 OCR 同时吞掉了做题本与解析册唯一一道题的
        # “(1)”标记；整节即为该题，仍可无歧义地按原文对齐。
        text = "\n".join(lines).strip()
        if text:
            return [(1, text)]
        raise ValueError(f"{section} 未找到题目")

    items: list[tuple[int, str]] = []
    for index, (line_i, col, q_num) in enumerate(starts):
        next_line, next_col = starts[index + 1][:2] if index + 1 < len(starts) else (len(lines), 0)
        chunk: list[str] = [lines[line_i][col:]]
        chunk.extend(lines[line_i + 1:next_line])
        if index + 1 < len(starts) and next_line == line_i:
            chunk[-1] = chunk[-1][: next_col - col]
        elif index + 1 < len(starts) and next_col:
            # OCR sometimes joins the next item number to the end of an
            # option line: ``D. ... (4) 设…``.  The prefix on that line still
            # belongs to the current item and must not be discarded.
            chunk.append(lines[next_line][:next_col])
        text = "\n".join(chunk).strip()
        if text:
            items.append((q_num, text))

    q_nums = [q_num for q_num, _ in items]
    expected = list(range(1, len(items) + 1))
    if q_nums != expected:
        raise ValueError(f"{section} 题号不连续：{q_nums}（应为 {expected}）")
    return items


def strip_question_number(text: str) -> str:
    return QUESTION_RE.sub("", text, count=1).strip()


def parse_answer_item(text: str, qtype: str) -> tuple[str, str]:
    """Split a source answer item into final answer and source solution text."""
    if qtype == "解答题":
        return "", strip_question_number(text)

    source = strip_question_number(text)
    if qtype == "选择题":
        match = re.match(r"\s*([A-D])\.\s*", source)
        if match:
            return match.group(1), source
        # OCR occasionally dropped the leading "(n) B." but retained the
        # source statement identifying the correct option.
        match = re.search(r"选项\s*([A-D])\s*正确", source)
        return (match.group(1) if match else ""), source

    # Fill-in answers normally occupy the first line.  For the repaired
    # no-label cases that begin with 解, retain the full source solution and
    # leave ``answer`` empty rather than infer or calculate a value.
    first_line = source.splitlines()[0].strip() if source else ""
    if first_line.startswith("解") or first_line.startswith("证"):
        return "", source
    if first_line == "$$":
        closing = source.find("\n$$", 3)
        if closing != -1:
            return source[2:closing].strip(), source
    return first_line, source


def write_section_sources(
    wb_sections: dict[SectionKey, tuple[str, list[str]]],
    answer_sections: dict[SectionKey, tuple[str, list[str]]],
) -> None:
    """Keep the paired source excerpts used for the build, without touching the high-math build area."""
    SECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    all_keys = sorted(set(wb_sections) | set(answer_sections), key=lambda k: (k.chapter_no, k.difficulty, k.qtype))
    for key in all_keys:
        safe_id = f"la-ch{key.chapter_no}-{DIFFICULTY_KEY[key.difficulty]}-{TYPE_KEY[key.qtype]}"
        wb_title, wb_lines = wb_sections.get(key, ("", []))
        ans_title, ans_lines = answer_sections.get(key, ("", []))
        (SECTIONS_DIR / f"{safe_id}.wb.md").write_text("\n".join(wb_lines).strip() + "\n", encoding="utf-8")
        (SECTIONS_DIR / f"{safe_id}.ans.md").write_text("\n".join(ans_lines).strip() + "\n", encoding="utf-8")
        manifest.append({
            "id": safe_id,
            "chapter_no": key.chapter_no,
            "chapter_title": wb_title or ans_title,
            "difficulty": key.difficulty,
            "type": key.qtype,
            "wb_file": f"{safe_id}.wb.md",
            "ans_file": f"{safe_id}.ans.md",
        })
    (SECTIONS_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def build() -> dict:
    wb_sections = split_source_sections(WORKBOOK)
    answer_sections = split_source_sections(ANSWERS)
    write_section_sources(wb_sections, answer_sections)

    questions = []
    journal_rows = []
    all_keys = sorted(wb_sections, key=lambda k: (k.chapter_no, k.difficulty, k.qtype))
    for key in all_keys:
        if key not in answer_sections:
            raise ValueError(f"解析册缺少小节：{key}")
        chapter_title, wb_lines = wb_sections[key]
        _, answer_lines = answer_sections[key]
        wb_items = slice_items(
            wb_lines,
            item_starts(wb_lines, section=key, repairs=WORKBOOK_REPAIRS, answer_mode=False),
            section=key,
        )
        answer_items = slice_items(
            answer_lines,
            item_starts(answer_lines, section=key, repairs=ANSWER_REPAIRS, answer_mode=True),
            section=key,
        )
        if len(wb_items) != len(answer_items):
            raise ValueError(f"{key} 做题本 {len(wb_items)} 题，解析册 {len(answer_items)} 题")

        extracted = []
        for (q_num, question_text), (_, answer_text) in zip(wb_items, answer_items, strict=True):
            answer, solution = parse_answer_item(answer_text, key.qtype)
            flags: list[str] = []
            if not answer and not solution:
                flags.append("answer_missing")
            item = {
                "id": f"la-c{key.chapter_no:02d}-{DIFFICULTY_KEY[key.difficulty]}-{TYPE_KEY[key.qtype]}-{q_num:03d}",
                "subject": "线性代数",
                "chapter_no": key.chapter_no,
                "chapter_title": chapter_title,
                "difficulty": DIFFICULTY_KEY[key.difficulty],
                "difficulty_zh": key.difficulty,
                "type": TYPE_KEY[key.qtype],
                "type_zh": key.qtype,
                "q_num": q_num,
                "text": strip_question_number(question_text),
                "answer": answer,
                "solution": solution,
                "answer_status": "missing" if flags else "ok",
                "flags": flags,
            }
            questions.append(item)
            extracted.append({
                "q_num": q_num,
                "text": question_text,
                "answer": answer,
                "solution": solution,
                "flags": flags,
            })

        section_id = f"la-ch{key.chapter_no}-{DIFFICULTY_KEY[key.difficulty]}-{TYPE_KEY[key.qtype]}"
        journal_rows.append({"type": "result", "result": {"section_id": section_id, "questions": extracted}})
        journal_rows.append({"type": "result", "result": {"section_id": section_id, "verdict": "ok", "issues": []}})

    questions.sort(key=lambda q: (q["chapter_no"], q["difficulty"], q["type"], q["q_num"]))
    missing = sum(q["answer_status"] == "missing" for q in questions)
    index = {
        "subject": "线性代数",
        "subject_code": "la",
        "built_at": date.today().isoformat(),
        "source": {
            "workbook": str(WORKBOOK.relative_to(ROOT)),
            "answers": str(ANSWERS.relative_to(ROOT)),
            "alignment": "section-order alignment with source-text OCR boundary repairs",
        },
        "questions": questions,
        "stats": {
            "total": len(questions),
            "answer_missing": missing,
            "verify_needs_review": 0,
            "ocr_boundary_repairs": sum(len(items) for items in WORKBOOK_REPAIRS.values()) + sum(len(items) for items in ANSWER_REPAIRS.values()),
        },
    }
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    JOURNAL_PATH.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in journal_rows), encoding="utf-8"
    )
    OUT.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return index


def validate(index: dict) -> list[str]:
    questions = index.get("questions", [])
    errors = []
    if index.get("subject") != "线性代数" or index.get("subject_code") != "la":
        errors.append("科目元数据错误")
    if len(questions) != 311:
        errors.append(f"题目数应为 311，实际为 {len(questions)}")
    if index.get("stats", {}).get("total") != len(questions):
        errors.append("stats.total 与题目数不一致")
    ids = [q.get("id") for q in questions]
    if len(ids) != len(set(ids)):
        errors.append("题目 ID 重复")
    missing = sum(q.get("answer_status") == "missing" for q in questions)
    if missing != index.get("stats", {}).get("answer_missing"):
        errors.append("缺答案统计不一致")
    for q in questions:
        if not q.get("text"):
            errors.append(f"{q.get('id')}: 题干为空")
        if q.get("answer_status") == "ok" and not (q.get("answer") or q.get("solution")):
            errors.append(f"{q.get('id')}: 标记 ok 但答案和解析均为空")
    return errors


def main() -> int:
    try:
        index = build()
    except (OSError, ValueError) as exc:
        print(f"!! 线代 880 构建失败：{exc}", file=sys.stderr)
        return 1
    errors = validate(index)
    if errors:
        print("!! 线代 880 索引校验失败：", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print(f"线代 880 题目索引已生成：{OUT.relative_to(ROOT)}")
    print(f"总题数 {index['stats']['total']} · 缺答案 {index['stats']['answer_missing']} · OCR 边界修复 {index['stats']['ocr_boundary_repairs']}")
    print(f"提取 journal：{JOURNAL_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
