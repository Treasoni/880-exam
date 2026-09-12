#!/usr/bin/env python3
"""lint_content.py — 校验生成的 Markdown 符合 .claude/rules/common/obsidian-content.md。

检查项：
1. YAML frontmatter 必填键（type/date|updated/tags）存在；
2. type 取值合法；
3. 站内 [[wikilink]] 指向的文件存在（在 workspace 范围内解析）；
4. 卷子/答案卷/判分卡/错题本/进度总览 的专属属性齐全；
5. LaTeX 公式定界符成对、未混入 Markdown 结构标记、不含控制字符，且未使用
   Obsidian 不渲染的 LaTeX 式定界符（行内 \\(...\\)、独立 \\[...\\]）。

用法：
  python3 scripts/lint_content.py            # 校验全部生成产物
  # Windows 请把 python3 换成 py -3（如 py -3 scripts/lint_content.py）
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib880

FM_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
WIKI_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
MARKDOWN_STRUCTURE_RE = re.compile(r"(?m)^\s*(?:#{1,6}\s|\*\*\d+\.\*\*)")
# 坏内容判据统一取自 lib880，与渲染层同源，避免两边各存一份正则而漂移
# （本次 \(...\) 漏检：渲染层与 lint 各存了一份只查独立式 \[...\] 的旧正则）。
CONTROL_CHAR_RE = lib880.CONTROL_CHAR_RE
LEGACY_DISPLAY_RE = lib880.LEGACY_DISPLAY_RE
LEGACY_INLINE_RE = lib880.LEGACY_INLINE_RE

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
WORKSPACE_FILES = set()
for p in (lib880.ROOT / "workspace").rglob("*.md"):
    WORKSPACE_FILES.add(p.stem)


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
        return base in WORKSPACE_FILES
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
    ``$$``，导致后续题目正文被吞进数学环境。
    """
    errors = []
    if CONTROL_CHAR_RE.search(text):
        errors.append("正文含控制字符（尤其检查 LaTeX 反斜杠转义是否生成了 \\x0c）")

    in_block = False
    block_start = None
    body = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if line.strip() != "$$":
            if in_block:
                body.append(line)
            continue

        if not in_block:
            in_block = True
            block_start = line_no
            body = []
            continue

        block_text = "\n".join(body)
        if MARKDOWN_STRUCTURE_RE.search(block_text):
            errors.append(
                f"第 {block_start}-{line_no} 行独立公式块混入 Markdown 结构标记，"
                "可能存在多余或错位的 $$"
            )
        in_block = False
        block_start = None
        body = []

    if in_block:
        errors.append(f"第 {block_start} 行开始的独立公式块缺少结束 $$")
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
    return rel, errors


def main():
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
    if not targets:
        print("没有可校验的产物（先拼卷/判分）。")
        return
    all_ok = True
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
