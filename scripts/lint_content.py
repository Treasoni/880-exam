#!/usr/bin/env python3
"""lint_content.py — 校验生成的 Markdown 符合 .claude/rules/common/obsidian-content.md。

检查项：
1. YAML frontmatter 必填键（type/date|updated/tags）存在；
2. type 取值合法；
3. 站内 [[wikilink]] 指向的文件存在（在 workspace 范围内解析）；
4. 卷子/答案卷/判分卡/错题本/进度总览 的专属属性齐全；
5. LaTeX 公式定界符成对、未混入 Markdown 结构标记、不含控制字符、无未解码的
   字面量 \\n，且未使用 Obsidian 不渲染的 LaTeX 式定界符（行内 \\(...\\)、
   独立 \\[...\\]）；
6. 事实源满足第 5 项——产物只是事实源的投影，源头坏了重建后必然流回产物，
   因此源头必须先绿。覆盖三个事实源：两个 880 索引（每题的 text/answer/
   solution 字段）与真题事实源 zhenti-problems.json（每题的 stem/answer/
   solution 字段，注意题干键名与 880 索引不同）；
7. 答案卷的题块集合与 papers.json 记录的 `paper_no` 一一对应（缺块 / 多块 /
   题号错位都能抓出）。判据锚定事实源期望，而不是「两版切块有无差异」——切块
   本身出错时后者会伪装成「无改动」。

用法：
  python3 scripts/lint_content.py            # 校验事实源 + 全部生成产物
  # Windows 请把 python3 换成 py -3（如 py -3 scripts/lint_content.py）
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib880

FM_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
WIKI_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
# 坏内容判据统一取自 lib880，与渲染层同源，避免两边各存一份正则而漂移
# （本次 \(...\) 漏检：渲染层与 lint 各存了一份只查独立式 \[...\] 的旧正则）。
CONTROL_CHAR_RE = lib880.CONTROL_CHAR_RE
LEGACY_DISPLAY_RE = lib880.LEGACY_DISPLAY_RE
LEGACY_INLINE_RE = lib880.LEGACY_INLINE_RE
LITERAL_NEWLINE_RE = lib880.LITERAL_NEWLINE_RE

VALID_TYPES = {"卷子", "答案卷", "判分卡", "错题本", "进度总览", "文档", "记录"}
REQUIRED = ["type", "tags"]  # date|updated 二选一
PER_TYPE = {
    "卷子": ["paper_id", "paper_no", "date", "subject", "duration_minutes", "total_score", "status"],
    "答案卷": ["paper_id", "date", "subject"],
    "判分卡": ["paper_id", "date", "subject"],
    "错题本": ["updated", "total", "focus_count", "mastered_count"],
    "进度总览": ["updated", "total", "graded", "pending", "undone", "wrong"],
}

# wikilink 解析根（各产物都在 workspace 下，按文件名匹配）
# 收全部文件而非只收 .md：错题本会以裸名嵌入真题原图（`![[zt-2021-数二-解答3.png]]`），
# 只收 .md 的 stem 会把图片嵌入误判成死链。Obsidian 也按「不含扩展名的文件名」解析任意
# 文件类型，所以 stem 与完整名两种写法都要认。
WORKSPACE_FILES = set()
for p in (lib880.ROOT / "workspace").rglob("*"):
    if not p.is_file():
        continue
    WORKSPACE_FILES.add(p.stem)  # [[卷子-01]]、[[zt-2021-数二-解答3.png]]
    WORKSPACE_FILES.add(p.name)  # 显式带扩展名时按完整名匹配


def _wikilink_resolves(target):
    """wikilink 目标能否解析到真实笔记文件。

    - 带 `#锚点` 时先剥离锚点（Obsidian 锚点匹配不参与文件解析）；
    - 路径型目标（含 `/`）按 vault 根相对解析，补 `.md` 后 `exists()` 判定——
      `Path.exists()` 会跟随 `external-notes/` 这类 symlink，跨库链接因此可解析；
    - 裸名目标（如 `[[卷子-01]]`）按 workspace 下文件 stem 匹配。
    """
    base = target.split("#", 1)[0].strip()
    if not base:
        return False
    if "/" not in base:
        return base in WORKSPACE_FILES or Path(base).stem in WORKSPACE_FILES
    p = lib880.ROOT / base
    if p.exists():
        return True
    return Path(str(p) + ".md").exists()


def parse_fm(text):
    m = FM_RE.match(text)
    if not m:
        return None
    kv = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        kv[k.strip()] = v.strip()
    return kv


def lint_math(text):
    """检查 Obsidian 独立公式块的基本结构。

    仅把单独占行的 ``$$`` 视为独立公式定界符，避免误判行内公式。
    额外拒绝公式块中出现 Markdown 标题/题号：这通常意味着多写了一个
    ``$$``，导致后续题目正文被吞进数学环境。结构判据取自 lib880，与渲染层
    同源（``display_math_errors``）。
    """
    errors = []
    if CONTROL_CHAR_RE.search(text):
        errors.append("正文含控制字符（尤其检查 LaTeX 反斜杠转义是否生成了 \\x0c）")
    if LITERAL_NEWLINE_RE.search(text):
        errors.append(
            "正文含字面量 \\n（反斜杠 + n 两字符）；换行未解码，会把整段解析"
            "挤成一行，请回查该字段在上游事实源中的换行是否已解码"
        )
    errors.extend(lib880.display_math_errors(text))
    if LEGACY_DISPLAY_RE.search(text):
        errors.append("使用了 \\[...\\] 独立公式定界符；Obsidian 产物统一使用 $$...$$")
    inline_hits = [
        i for i, line in enumerate(text.splitlines(), start=1)
        if LEGACY_INLINE_RE.search(line)
    ]
    if inline_hits:
        shown = "、".join(str(i) for i in inline_hits[:5])
        more = f" 等 {len(inline_hits)} 行" if len(inline_hits) > 5 else ""
        errors.append(
            f"使用了 \\(...\\) 行内公式定界符（第 {shown}{more}）；"
            "Obsidian 只渲染 $...$，请改用 $...$"
        )
    return errors


SOURCE_FIELDS = ("text", "answer", "solution")


def lint_source(subject):
    """校验事实源索引里每道题的 text/answer/solution 字段。

    产物只是事实源的投影：索引里任一字段带坏内容，重建后都会原样流进卷子/
    答案卷/错题本。此前 lint 只校验产物，坏数据可以一直躺在事实源里不被发现
    （2026-09-13 那次字面 \\n 与错位 $$ 就是这样漏过去的），所以这里对每道题的
    三个字段跑与产物同一个 lint_math，报「题号 + 字段」，让源头缺陷在重建前
    就被拦住。返回 (相对路径, errors 或 None——None 表示尚未入库)。
    """
    path = lib880.subject_paths(subject)["index"]
    rel = path.relative_to(lib880.ROOT)
    if not path.exists():
        return rel, None
    doc = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    for q in doc.get("questions", []):
        qid = q.get("id", "?")
        for field in SOURCE_FIELDS:
            for e in lint_math(q.get(field) or ""):
                errors.append(f"{qid}.{field}: {e}")
    return rel, errors


def lint_solution_overrides():
    """校验解析覆盖层（``workspace/records/solution-overrides.json``）。

    覆盖层与索引一样是产物上游：它替换解析册原文流进答案卷与错题本，所以用
    同一个 ``lint_math`` 判据校验，坏公式在重建前就被拦住。文件不存在返回 None。
    """
    path = lib880.SOLUTION_OVERRIDES_PATH
    rel = path.relative_to(lib880.ROOT)
    if not path.exists():
        return rel, None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return rel, [f"JSON 解析失败: {exc}"]
    errors = []
    for qid, text in lib880.load_solution_overrides().items():
        for e in lint_math(text):
            errors.append(f"{qid}.solution: {e}")
    if not doc.get("solutions"):
        errors.append("solutions 为空；没有覆盖项时请删除该文件")
    return rel, errors


def lint_zhenti_source():
    """校验真题事实源（``workspace/records/zhenti-problems.json``）。

    与两个 880 索引同理：真题错题本只是它的事实源投影，源头的坏公式/字面 `\\n`/
    错位 `$$` 重建后必然流回产物，所以源头必须先绿。文件不存在返回 None。

    字段表用 ``lib880.ZHENTI_SOURCE_FIELDS``（``stem``/``answer``/``solution``），
    **不能**沿用 880 索引的 ``SOURCE_FIELDS``（``text``/...）：真题记录的题干键是
    ``stem``，拿 ``text`` 去取只会得到 None，整张表校验静默空转。末尾的覆盖面护栏
    专门盯这类漂移——某字段在所有记录里都不存在，说明字段表与实际 schema 已经脱节。
    """
    path = lib880.ZHENTI_PROBLEMS_PATH
    rel = path.relative_to(lib880.ROOT)
    if not path.exists():
        return rel, None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return rel, [f"JSON 解析失败: {exc}"]
    problems = doc.get("problems") or {}
    errors = []
    for pid, p in problems.items():
        for field in lib880.ZHENTI_SOURCE_FIELDS:
            for e in lint_math(p.get(field) or ""):
                errors.append(f"{pid}.{field}: {e}")
    # 防空转：字段表与 schema 脱节时，上面对不存在的键取 None 会「全绿」，检查
    # 看着通过实则一条没查。某字段在所有记录里都不出现即判为脱节。
    if problems:
        for field in lib880.ZHENTI_SOURCE_FIELDS:
            if not any(field in p for p in problems.values()):
                errors.append(
                    f"字段 {field!r} 在全部 {len(problems)} 条记录里都不存在——"
                    "事实源 schema 与 ZHENTI_SOURCE_FIELDS 已脱节，校验未生效，"
                    "请核对字段名后同步 lib880.ZHENTI_SOURCE_FIELDS"
                )
    return rel, errors


def lint_file(path: Path):
    rel = path.relative_to(lib880.ROOT)
    text = path.read_text(encoding="utf-8")
    errors = []
    fm = parse_fm(text)
    if fm is None:
        return rel, ["缺少 YAML frontmatter"]
    if "type" not in fm or fm["type"] not in VALID_TYPES:
        errors.append(f"type 缺失或非法: {fm.get('type')!r}")
    if "tags" not in fm:
        errors.append("缺少 tags")
    if "date" not in fm and "updated" not in fm:
        errors.append("缺少 date 或 updated")
    for k in PER_TYPE.get(fm.get("type"), []):
        if k not in fm:
            errors.append(f"缺少专属属性 {k}")
    # wikilink 校验
    for target in WIKI_RE.findall(text):
        if not _wikilink_resolves(target):
            errors.append(f"wikilink 指向不存在的文件: [[{target}]]")
    errors.extend(lint_math(text))
    # 答案卷结构：题块集合须与 papers.json 期望一一对应
    if fm.get("type") == "答案卷" and fm.get("paper_id"):
        errors.extend(lib880.answer_sheet_key_errors(fm["paper_id"], text))
    return rel, errors


def main():
    all_ok = True
    # 1) 事实源：先于产物校验——产物只是它的投影，源头不绿产物必坏
    for subject in (lib880.SUBJECT_HIGH_MATH, lib880.SUBJECT_LINEAR_ALGEBRA):
        rel, errors = lint_source(subject)
        if errors is None:
            print(f"- {rel}（未入库，跳过）")
            continue
        if errors:
            all_ok = False
            print(f"✗ {rel}")
            for e in errors[:20]:
                print(f"    - {e}")
            if len(errors) > 20:
                print(f"    … 共 {len(errors)} 处")
        else:
            print(f"✓ {rel}")
    rel, errors = lint_solution_overrides()
    if errors is None:
        print(f"- {rel}（未启用，跳过）")
    elif errors:
        all_ok = False
        print(f"✗ {rel}")
        for e in errors[:20]:
            print(f"    - {e}")
    else:
        print(f"✓ {rel}")
    rel, errors = lint_zhenti_source()
    if errors is None:
        print(f"- {rel}（未启用，跳过）")
    elif errors:
        all_ok = False
        print(f"✗ {rel}")
        for e in errors[:20]:
            print(f"    - {e}")
    else:
        print(f"✓ {rel}")
    # 2) 产物
    targets = []
    if lib880.PAPERS_DIR.exists():
        targets += sorted(lib880.PAPERS_DIR.rglob("*.md"))
    for subject in (lib880.SUBJECT_HIGH_MATH, lib880.SUBJECT_LINEAR_ALGEBRA):
        wrong_book = lib880.wrong_book_path(subject)
        progress = lib880.progress_path(subject)
        if wrong_book.exists():
            targets.append(wrong_book)
        if progress.exists():
            targets.append(progress)
    if lib880.ZHENTI_WRONG_BOOK_PATH.exists():
        targets.append(lib880.ZHENTI_WRONG_BOOK_PATH)
    for path in targets:
        rel, errors = lint_file(path)
        if errors:
            all_ok = False
            print(f"✗ {rel}")
            for e in errors:
                print(f"    - {e}")
        else:
            print(f"✓ {rel}")
    print("=== 结果:", "全部通过" if all_ok else "存在问题", "===")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
