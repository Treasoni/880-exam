#!/usr/bin/env python3
"""grade.py — 判分（五态：对/错/不会/半会/粗心），更新判分记录并重生成错题本与进度。

用法（推荐，勾选式）：
  python3 scripts/grade.py --sheet workspace/papers/paper-01/判分卡-01.md [--redo]
  # 读取判分卡里的勾选（[x]），paper_id 从卡片 frontmatter 自动获取

用法（JSON，兜底）：
  python3 scripts/grade.py --paper paper-01 \
      --grading '{"choice":{"1":"不会","2":"对"},"fill":{"3":"半会"},"solution":{"1":"不会"}}'
  python3 scripts/grade.py --paper paper-01 --grading-file grade.json --redo
  # Windows 把 python3 换成 py -3；JSON 建议走 --grading-file，避免 cmd/PowerShell 引号问题

grading 中 key 为题型内题号（1 起），value 为中文或英文判分态。
--grading 可接受带外层单/双引号的字符串；也可用 --grading-file <UTF-8 文件> 读取 JSON。
可加 --redo：表示这是错题重练（若判为『对』则复习状态置为已掌握，否则保持未复习）。
判分后会回填卷子文件判分表、把 frontmatter status 更新为 graded，并刷新错题本与进度总览。
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib880

GRADE_ALIAS = {
    "对": "correct", "correct": "correct",
    "错": "wrong", "wrong": "wrong",
    "不会": "cannot", "cannot": "cannot",
    "半会": "half", "half": "half",
    "粗心": "careless", "careless": "careless",
}

SECTION_NO = {"choice": "一", "fill": "二", "solution": "三"}
SECTION_ORDER = {"一": "choice", "二": "fill", "三": "solution"}
TICK_RE = re.compile(r"^\[[xX✓✔☑✅]\]$|^[xX✓✔☑✅]$")


def _is_ticked(cell):
    return bool(TICK_RE.match(cell.strip()))


def _split_cells(line):
    """按顶层 | 拆分表格行，尊重反斜杠转义（\\| 是字面竖线，不作分隔符）。

    make_paper 的 _cell_escape 会把答案里的 | 转成 \\|，这里必须数反斜杠奇偶：
    偶数个反斜杠（含 0 个）后的 | 才是真正的列分隔符。
    """
    cells = []
    cur = []
    for i, ch in enumerate(line):
        if ch == "|":
            bs = 0
            j = i - 1
            while j >= 0 and line[j] == "\\":
                bs += 1
                j -= 1
            if bs % 2 == 0:
                cells.append("".join(cur).strip())
                cur = []
            else:
                cur.append(ch)
        else:
            cur.append(ch)
    cells.append("".join(cur).strip())
    return cells


def _table_cells(line):
    """去掉行首尾的表格定界 | 后按转义规则拆分单元格。"""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return _split_cells(s)


def parse_grading_card(path):
    """解析判分卡 markdown → (paper_id, grading)。

    grading 形如 {"choice": {"1": "对", "2": "错"}, ...}，与 --grading JSON 同构。
    每行只允许勾一个状态；零勾的行跳过（保持未判）；多勾直接报错。
    """
    text = Path(path).read_text(encoding="utf-8")

    paper_id = None
    fm = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if fm:
        for line in fm.group(1).splitlines():
            if line.startswith("paper_id:"):
                paper_id = line.split(":", 1)[1].strip()
                if len(paper_id) >= 2 and paper_id[0] in "\"'" and paper_id[-1] == paper_id[0]:
                    paper_id = paper_id[1:-1]  # 去 YAML 引号

    section = None
    col_to_grade = {}
    seen_header = False
    grading = {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("## "):
            mh = re.match(r"^## ([一二三])、", line)
            section = SECTION_ORDER.get(mh.group(1)) if mh else None
            col_to_grade = {}
            seen_header = False
            continue
        if not section or not line.startswith("|"):
            continue
        cells = _table_cells(line)
        if not cells:
            continue
        # 分隔行：全为 --- 或空
        if all(re.fullmatch(r"-{2,}", c or "-") for c in cells):
            continue
        # 数据行：第一格是题号
        if re.fullmatch(r"\d+", cells[0]):
            pos = int(cells[0])
            # 勾选 = [x]/勾号，或在对应列直接写该判分态（如「对」列写“对”）
            ticked = [col_to_grade[i] for i, c in enumerate(cells)
                      if i in col_to_grade and (_is_ticked(c) or c == col_to_grade[i])]
            if len(ticked) > 1:
                print(f"!! 判分卡第 {SECTION_NO.get(section, section)} 第 {pos} 题勾了多个状态："
                      f"{ticked}，每题只能勾一个", file=sys.stderr)
                sys.exit(2)
            if len(ticked) == 1:
                grading.setdefault(section, {})[str(pos)] = ticked[0]
            continue
        # 表头行：仅认本小节的第一张表（seen_header 防答案恰好是「对/错」的行被误判为表头）
        if not seen_header:
            grade_cols = {c for c in cells if c in GRADE_ALIAS and GRADE_ALIAS[c] != c}
            if grade_cols:
                col_to_grade = {i: c for i, c in enumerate(cells) if c in grade_cols}
                seen_header = True
    return paper_id, grading


def _backfill_grade_table(text, graded_rows):
    """把判分态回填到卷子判分表的第三列。graded_rows: [(section, pos, grade_zh)]。"""
    fill = {f"{SECTION_NO[sec]}{pos}": zh for sec, pos, zh in graded_rows}
    out = []
    for line in text.splitlines():
        if line.startswith("| ") and line.endswith(" |"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) == 3 and cells[0] in fill:
                cells[2] = fill[cells[0]]
                line = "| " + " | ".join(cells) + " |"
        out.append(line)
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", default=None, help="卷子 id；用 --sheet 时可不传（从卡片 frontmatter 读）")
    ap.add_argument("--sheet", default=None, help="从判分卡 markdown 读取勾选判分（推荐）")
    ap.add_argument("--grading", default=None, help="JSON：题型→{题号:判分}（可带外层引号）")
    ap.add_argument("--grading-file", default=None,
                    help="从 UTF-8 文件读取判分 JSON（避免 shell 引号问题）")
    ap.add_argument("--note", default="")
    ap.add_argument("--redo", action="store_true", help="错题重练模式")
    args = ap.parse_args()

    import json
    if not args.sheet and not args.grading and not args.grading_file:
        ap.error("必须提供 --sheet / --grading / --grading-file 之一")
    if args.sheet:
        card_paper, grading = parse_grading_card(args.sheet)
        if args.paper and args.paper != card_paper:
            print(f"!! 判分卡属于 {card_paper}，与 --paper {args.paper} 不一致", file=sys.stderr)
            sys.exit(2)
        args.paper = args.paper or card_paper
        if not args.paper:
            print(f"!! 判分卡 {args.sheet} 缺少 paper_id frontmatter", file=sys.stderr)
            sys.exit(2)
    elif args.grading or args.grading_file:
        if not args.paper:
            ap.error("JSON 判分需要 --paper")
        try:
            if args.grading_file:
                grading = json.loads(Path(args.grading_file).read_text(encoding="utf-8"))
            else:
                raw = args.grading.strip()
                if len(raw) >= 2 and raw[0] in "'\"" and raw[-1] == raw[0]:
                    raw = raw[1:-1]  # cmd.exe 会原样保留单引号，先去外层引号再解析
                grading = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"!! 判分 JSON 解析失败: {exc}", file=sys.stderr)
            sys.exit(2)

    schema = lib880.load_schema()
    index = lib880.load_index()
    lib880.build_index_map(index)
    attempts = lib880.load_attempts()
    papers = lib880.load_papers()

    paper = next((p for p in papers["papers"] if p["paper_id"] == args.paper), None)
    if not paper:
        print(f"!! 找不到卷子 {args.paper}", file=sys.stderr)
        sys.exit(2)

    qmap = {}  # (section, pos) -> qid
    for q in paper["questions"]:
        sec = q["section"]
        pos = int(q["paper_no"][1:])  # 一1 -> 1
        qmap[(sec, pos)] = q["qid"]

    today = lib880.today_str()
    grade_zh = {g["key"]: g["zh"] for g in schema["grades"]}
    processed = 0  # 判分卡里识别到的有效判分题数
    added = 0      # 实际新写入 attempts 的记录数（去重后）
    graded_rows = []  # (section, pos, grade_zh) 用于回填卷子判分表
    for sec, pos_grade in grading.items():
        if sec not in ("choice", "fill", "solution"):
            print(f"!! 未知题型 {sec}（应为 choice/fill/solution）", file=sys.stderr)
            sys.exit(2)
        for pos, g in pos_grade.items():
            grade_key = GRADE_ALIAS.get(str(g).strip())
            if not grade_key:
                print(f"!! 未知判分 {g}", file=sys.stderr)
                sys.exit(2)
            qid = qmap.get((sec, int(pos)))
            if not qid:
                print(f"!! 卷子 {args.paper} 无 {sec} 第 {pos} 题", file=sys.stderr)
                sys.exit(2)
            new_attempt = {
                "qid": qid,
                "paper_id": args.paper,
                "grade": grade_key,
                "when": today,
                "note": args.note,
            }
            # 幂等：同日同题同态判分不重复记录（判分卡重复跑不会叠加记录）
            dup = any(
                a.get("qid") == qid and a.get("grade") == grade_key and a.get("when") == today
                for a in attempts["attempts"]
            )
            if not dup:
                attempts["attempts"].append(new_attempt)
                added += 1
            # 复习状态联动（重复判分也刷新状态）
            if args.redo:
                prev = attempts["wrong_book_status"].get(qid, {}).get("state")
                new_state = "已掌握" if grade_key == "correct" else ("未复习" if prev != "已重做" else prev)
                attempts["wrong_book_status"][qid] = {"state": new_state, "updated": today}
            elif grade_key in set(schema["wrong_book"]["focus_grades"]):
                if qid not in attempts["wrong_book_status"]:
                    attempts["wrong_book_status"][qid] = {"state": "未复习", "updated": today}
            graded_rows.append((sec, int(pos), grade_zh[grade_key]))
            processed += 1

    if processed == 0:
        print("!! 没有有效的判分（判分卡未勾选，或勾选无法识别），未写入任何记录", file=sys.stderr)
        sys.exit(2)
    if added == 0:
        print("判分卡勾选与已有记录重复，无新增记录（复习状态/判分表已刷新）")

    lib880.save_attempts(attempts)
    paper["status"] = "graded"
    lib880.save_papers(papers)

    # 更新卷子文件：frontmatter status → graded、updated → 当日；判分表回填判分态
    try:
        n = int(args.paper.split("-")[-1])
    except ValueError:
        print(f"!! 无法从 {args.paper} 解析卷号", file=sys.stderr)
        sys.exit(2)
    paper_path = lib880.paper_dir(args.paper) / f"卷子-{n:02d}.md"
    if paper_path.exists():
        text = paper_path.read_text(encoding="utf-8")
        text = re.sub(r"^status: .*$", "status: graded", text, count=1, flags=re.MULTILINE)
        text = re.sub(r"^updated: .*$", f"updated: {today}", text, count=1, flags=re.MULTILINE)
        text = _backfill_grade_table(text, graded_rows)
        paper_path.write_text(text, encoding="utf-8")
    else:
        print(f"!! 警告：找不到卷子文件 {paper_path}，无法更新判分表与 status（判分记录已写入）",
              file=sys.stderr)

    # 重生成报告
    import subprocess
    py = sys.executable
    scripts = Path(__file__).resolve().parent
    subprocess.run([py, str(scripts / "wrong_book.py")], check=True)
    subprocess.run([py, str(scripts / "progress.py")], check=True)

    print(f"已记录 {added} 条判分 → 卷子 {args.paper} 标记为已判分")
    print(f"已重生成错题本与进度总览")


if __name__ == "__main__":
    main()
