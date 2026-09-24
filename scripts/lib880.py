#!/usr/bin/env python3
"""lib880.py — 880 习题系统的共享库：配置加载、数据读写、弱点/权重计算。"""

import json
import math
import re
import sys
from datetime import datetime, date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "workspace/schema.yaml"
INDEX_PATH = ROOT / "workspace/question-index.json"
LINEAR_ALGEBRA_SCHEMA_PATH = ROOT / "workspace/linear-algebra-schema.yaml"
LINEAR_ALGEBRA_INDEX_PATH = ROOT / "workspace/linear-algebra-question-index.json"
ATTEMPTS_PATH = ROOT / "workspace/records/attempts.json"
PAPERS_PATH = ROOT / "workspace/records/papers.json"
PAPERS_DIR = ROOT / "workspace/papers"
WRONG_BOOK_PATH = ROOT / "workspace/wrong-book/错题本.md"
PROGRESS_PATH = ROOT / "workspace/preview/进度总览.md"
LINEAR_ALGEBRA_WRONG_BOOK_PATH = ROOT / "workspace/wrong-book/线代错题本.md"
LINEAR_ALGEBRA_PROGRESS_PATH = ROOT / "workspace/preview/线代进度总览.md"
EXTERNAL_LINKS_PATH = ROOT / "workspace/records/external-links.json"
ANALYSIS_PATH = ROOT / "workspace/records/analysis.json"
SOLUTION_OVERRIDES_PATH = ROOT / "workspace/records/solution-overrides.json"
# 真题系统（zhenti-exam）：独立事实源与独立产物，不进 880 进度/配额
ZHENTI_PROBLEMS_PATH = ROOT / "workspace/records/zhenti-problems.json"
ZHENTI_WRONG_BOOK_PATH = ROOT / "workspace/wrong-book/真题错题本.md"
# 真题记录的正文型字段。注意题干键是 ``stem`` 而非 880 索引用的 ``text``——两套
# 事实源字段名不同，校验端必须各自用对的表，否则会去校验一个不存在的键：取出来是
# None，全表零错误，检查静默空转。此处单一出处，渲染层与 lint 都引用它。
ZHENTI_SOURCE_FIELDS = ("stem", "answer", "solution")


# ``high-math`` is the historical/default workflow.  Keep its identifiers and
# paths unchanged so adding the linear-algebra pool never moves or overwrites
# an existing paper.  The aliases accept both CLI-friendly and Chinese input.
SUBJECT_HIGH_MATH = "high-math"
SUBJECT_LINEAR_ALGEBRA = "linear-algebra"
_SUBJECT_ALIASES = {
    SUBJECT_HIGH_MATH: SUBJECT_HIGH_MATH,
    "high_math": SUBJECT_HIGH_MATH,
    "calculus": SUBJECT_HIGH_MATH,
    "gs": SUBJECT_HIGH_MATH,
    "高数": SUBJECT_HIGH_MATH,
    "高等数学": SUBJECT_HIGH_MATH,
    SUBJECT_LINEAR_ALGEBRA: SUBJECT_LINEAR_ALGEBRA,
    "linear_algebra": SUBJECT_LINEAR_ALGEBRA,
    "la": SUBJECT_LINEAR_ALGEBRA,
    "线代": SUBJECT_LINEAR_ALGEBRA,
    "线性代数": SUBJECT_LINEAR_ALGEBRA,
}


# 渲染层与 lint 共用的「坏内容」判据：单一出处，避免三份正则各自漂移
# （本次 \(...\) 漏检正是因为 wrong_book.py 与 lint_content.py 各存一份只查
# 独立式的旧正则）。CONTROL_CHAR_RE 挡 \x0c 这类把 LaTeX 反斜杠转义坏的控制字符。
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Obsidian 只渲染 $...$（行内）与 $$...$$（独立）。LaTeX 式定界符 \(...\)
# （行内）与 \[...\]（独立）会以原文裸露，必须在写入产物前归一或拒绝。
# 两个正则都用 (?<!\\) 跳过 \\\( / \\\[ 这类转义形式（后者含 LaTeX 换行 \\）。
LEGACY_INLINE_RE = re.compile(r"(?<!\\)\\[()]")
LEGACY_DISPLAY_RE = re.compile(r"(?<!\\)\\[\[\]]")
_ESCAPED_BACKSLASH_PAREN_RE = re.compile(r"\\\\[()]")

# 结构化提取（merge_extraction）用两个字符 ``\n`` 表示换行；残留到索引时渲染层会
# 把整段解析挤成一行字面量 ``\n``，``$$`` 也就无法成对识别。
#
# 既不能全局替换（会把 ``\neq`` 改坏），也不能只按「``\n`` 后面是不是字母」判断：
# 旧判据 ``(?![A-Za-z])`` 会漏掉 ``\nf (x)`` / ``\nS _ {1}`` / ``\nA (x)`` 这类
# ``\n`` 后紧跟公式变量的换行残留——它们同样把整段解析挤成一行，正是本次错题本
# 渲染故障的根因（13/20 道题的解析因此仍缺一个 ``$$`` 配对）。
#
# 判据改为「枚举真正以 n 开头的 LaTeX 命令」。但正则里的 ``\\n`` 已经吃掉了反斜杠
# 和 n，否定前瞻看到的是命令名的**剩余部分**：``\neq`` 剩 ``eq``、``\nabla`` 剩
# ``abla``、``\ne`` 剩 ``e``。所以下面列全名，再由 LATEX_N_COMMAND_TAILS 统一去掉
# 开头那个 n 构成前瞻分支；若把全名直接塞进前瞻，每个分支都会落空，``\neq`` 反而
# 会被解码成换行（上一版就是这样把 374 处 ``\neq`` 改成换行的）。
# 尾部的 ``(?![A-Za-z])`` 要求按整条命令匹配：``\nearrow`` 不被 ``e`` 分支抢走，
# ``\notin`` 不被 ``ot`` 分支抢走。
#
# 本库语料实测（两个索引的 text/answer/solution，405 处 ``\n``+字母）：真命令 383 处
# （``eq`` 374、``e`` 6、``earrow`` 2、``Rightarrow`` 1），换行残留 22 处
# （``f`` 8、``S`` 6、``F`` 3、``A`` 2、``I``/``L``/``V`` 各 1）。
# 单字母命令（``\ne``/``\ni``/``\nu``）与「换行 + 变量 e/i/u」本就同形，文本本身
# 无法区分；语料中逐条核对均为真命令，故按「保命令」处理——宁可漏解一个换行，
# 也不把数学公式改坏。
LATEX_N_COMMANDS = (
    # 关系/否定符号（amssymb）
    "nLeftrightarrow", "nleftrightarrow",
    "nRightarrow", "nrightarrow", "nLeftarrow", "nleftarrow",
    "ntrianglelefteq", "ntrianglerighteq", "ntriangleleft", "ntriangleright",
    "nshortparallel", "nshortmid", "nparallel", "nmid", "nlsim",
    "nsubseteqq", "nsupseteqq", "nsubseteq", "nsupseteq", "nsubset", "nsupset",
    "nleqslant", "ngeqslant", "nleqq", "ngeqq", "nleq", "ngeq",
    "nlessgtr", "ngtrless", "nless", "ngtr",
    "npreccurlyeq", "nprecneqq", "nprecneq", "nprecsim", "npreceq", "nprec",
    "nsucccurlyeq", "nsuccneqq", "nsuccneq", "nsuccsim", "nsucceq", "nsucc",
    "nvdash", "nvDash", "nVdash", "nVDash",
    "notin", "notni", "nexists",
    "nsimeq", "nsime", "nsim", "ncong", "nasymp", "napprox", "nequiv",
    "nwarrow", "nearrow",
    # 普通符号
    "nabla", "natural",
    "neq", "ne", "neg", "not", "ni", "nu",
    # 排版 / 空白 / 长度
    "negthickspace", "negmedspace", "negthinspace",
    "nobreakspace", "nolinebreak", "nonumber", "nobreak", "noindent",
    "newenvironment", "newcommand", "newtheorem", "newcounter", "newlength",
    "newsavebox", "newline", "newpage", "newif",
)

LATEX_N_COMMAND_TAILS = tuple(
    sorted({c[1:] for c in LATEX_N_COMMANDS}, key=len, reverse=True))
LITERAL_NEWLINE_RE = re.compile(
    r"\\n(?!(?:" + "|".join(LATEX_N_COMMAND_TAILS) + r")(?![A-Za-z]))")

# 独立公式块（单独占行的 $$）内部不应出现 Markdown 标题或题号；出现通常意味着
# 多写、错位或丢失了一个 $$，把后续正文吞进了数学环境。
DISPLAY_MATH_STRUCTURE_RE = re.compile(r"(?m)^\s*(?:#{1,6}\s|\*\*\d+\.\*\*)")

# Markdown 标题行；供 demote_solution_headings 把解析内部标题降到嵌套层之下
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*)$")

# 判分卡勾选标记：任务清单 `- [x] 对`（阅读视图点击即写 x），历史表格里也用过 [x]。
# 判据只此一份——grade.py 读勾选、make_paper.py 判断「卡上是否已有用户输入」都引用它，
# 免得一处放宽标记、另一处仍把已勾选的卡当成空白卡重建掉。
TICK_MARKS = "xX✓✔☑✅"
CHECK_RE = re.compile(r"^-\s+\[([" + TICK_MARKS + r" ])\]\s*(\S+)\s*$")
TICK_RE = re.compile(r"^\[[" + TICK_MARKS + r"]\]$|^[" + TICK_MARKS + r"]$")


def card_ticked_lines(text):
    """返回判分卡文本里已勾选的行（`- [x] 对` 这类，未勾的 `- [ ]` 不算）。"""
    return [line for line in text.splitlines()
            if (m := CHECK_RE.match(line)) and m.group(1) != " "]


def normalize_math_delimiters(text):
    """把 LaTeX 式行内定界符 ``\\(...\\)`` 归一为 Obsidian 的 ``$...$``。

    源文本不改，本函数在渲染层调用（与 ``demote_solution_headings`` 同一策略：
    复用文本进产物时由渲染层适配，事实源保持原貌）。

    无法安全自动转换时抛 ``ValueError`` 而不是盲替，避免替出更坏的渲染：

    - 独立式 ``\\[...\\]`` 不归本函数管，沿用既有「拒绝、改用 ``$$...$$``」策略；
    - 转义形式 ``\\\\`` 后紧跟括号语义不明（可能本就不是定界符），交人工判断；
    - 归一后若新增相邻 ``$$``（如 ``\\)$`` → ``$$``）或某行 ``$`` 个数变成奇数，
      说明替换会破坏定界符配对，一并拒绝。
    """
    text = str(text or "")
    if LEGACY_DISPLAY_RE.search(text):
        raise ValueError(
            "含 \\[...\\] 独立公式定界符；请改用 $$...$$（见 obsidian-content.md）")
    if _ESCAPED_BACKSLASH_PAREN_RE.search(text):
        raise ValueError(
            "含 \\\\( 或 \\\\) 转义形式，无法安全自动归一；请人工确认后再写入")
    if not LEGACY_INLINE_RE.search(text):
        return text
    converted = LEGACY_INLINE_RE.sub("$", text)
    if converted.count("$$") > text.count("$$"):
        raise ValueError(
            "归一行内定界符会产生相邻 $$，无法安全自动转换；请人工修正")
    for line_no, line in enumerate(converted.splitlines(), start=1):
        if line.count("$") % 2:
            raise ValueError(
                f"归一行内定界符后第 {line_no} 行 $ 定界符不配对；请人工修正")
    return converted


def decode_literal_newlines(value):
    """把字面量 ``\\n``（反斜杠 + n 两个字符）解码为真实换行。

    结构化提取的输出用 ``\\n`` 表示换行；这一步本该在合并（merge_extraction）时
    完成，索引里若残留，渲染层会把整段解析挤成一行字面量 ``\\n``。

    只解码不属于 LaTeX 命令的 ``\\n``（``LITERAL_NEWLINE_RE`` 按 ``LATEX_N_COMMANDS``
    枚举真命令、取其去首字母的「命令剩余部分」做否定前瞻），以免把
    ``\\neq`` / ``\\nabla`` / ``\\notin`` 改坏；禁止用全局 ``\\\\n`` 替换。
    ``\\n`` 后跟公式变量（``\\nf (x)``、``\\nS _ {1}``）也算换行残留，必须解码，
    否则整段解析仍被挤成一行、``$$`` 无法配对。
    """
    return LITERAL_NEWLINE_RE.sub("\n", str(value or ""))


# 答案卷结构：章节标题 `## 一、选择题`，题干以 `**N.** ` 起头
ANSWER_SECTION_RE = re.compile(r"^## *([一二三])、")
ANSWER_QUESTION_RE = re.compile(r"^\*\*(\d+)\.\*\*[ \t]")


def split_answer_sheet(text):
    """把答案卷切成 ``{题号: 块文本}``，题号形如 ``一1``（章节序号 + 题号）。

    切块是一切答案卷核验的基础：**块没切对时，「各块两版文本相同」是假绿**——
    错分组或只切出一两块，比较结果会是「无差异」，看起来像「文件没被改动」。
    所以调用方拿到结果后必须先跟期望题号集合比对（见
    ``answer_sheet_key_errors``），不能只报「有无差异」。
    """
    blocks, section, key, buf = {}, None, None, []

    def flush():
        if key is not None:
            blocks[key] = "\n".join(buf)

    for line in str(text or "").split("\n"):
        m = ANSWER_SECTION_RE.match(line)
        if m:
            flush()
            section, key, buf = m.group(1), None, []
            continue
        m = ANSWER_QUESTION_RE.match(line)
        if m and section:
            flush()
            key, buf = f"{section}{m.group(1)}", []
            continue
        if key is not None:
            buf.append(line)
    flush()
    return blocks


def answer_sheet_key_errors(paper_id, text):
    """核验答案卷的题块集合与 ``papers.json`` 记录一一对应，返回错误说明列表。

    期望集合取事实源记录的 ``paper_no``（如 ``一1``）——这是「本卷应该有哪些题」
    的权威来源，缺块、多块、题号错位都能抓出来。判据必须锚定这个集合，而不是
    「两版切块之间有无差异」：后者在切块本身出错时会伪装成「无改动」。
    记录里查不到该卷时返回空列表（跳过，不误报）。
    """
    rec = next((p for p in load_papers().get("papers", [])
                if p.get("paper_id") == paper_id), None)
    if rec is None:
        return []
    expected = {q["paper_no"] for q in rec.get("questions", []) if q.get("paper_no")}
    got = set(split_answer_sheet(text))
    errors = []
    missing = sorted(expected - got)
    extra = sorted(got - expected)
    if missing:
        errors.append("答案卷缺少题块: " + "、".join(missing))
    if extra:
        errors.append("答案卷题块多出或题号错位: " + "、".join(extra))
    return errors


def display_math_errors(text):
    """返回独立公式块（``$$``）的结构错误列表；渲染前置校验与 lint 共用同一判据。

    仅把单独占行的 ``$$`` 视为独立公式定界符，避免误判行内公式。逐对扫描：
    块内混入 Markdown 结构标记、或扫描结束时仍有未闭合的块，都说明 ``$$``
    多写、错位或丢失（后一种会把后续题目正文吞进数学环境）。
    """
    errors = []
    in_block = False
    block_start = None
    body = []
    for line_no, line in enumerate(str(text or "").splitlines(), start=1):
        if line.strip() != "$$":
            if in_block:
                body.append(line)
            continue
        if not in_block:
            in_block = True
            block_start = line_no
            body = []
            continue
        if DISPLAY_MATH_STRUCTURE_RE.search("\n".join(body)):
            errors.append(
                f"第 {block_start}-{line_no} 行独立公式块混入 Markdown 结构标记，"
                "可能存在多余或错位的 $$")
        in_block = False
        block_start = None
        body = []
    if in_block:
        errors.append(f"第 {block_start} 行开始的独立公式块缺少结束 $$")
    return errors


def prepare_solution_text(value):
    """渲染层统一的解析文本准备：解码字面量 ``\\n`` → 归一定界符 → 去首尾空白。

    在写入产物前调用（``wrong_book.py`` / ``make_paper.py``），让事实源里的提取
    残留（字面量 ``\\n``）与 LaTeX 式定界符都在同一处被吸收。
    """
    return normalize_math_delimiters(decode_literal_newlines(value)).strip()


def demote_solution_headings(text, item_level):
    """把解析文本内部的 Markdown 标题降到条目标题之下，保证嵌套排版。

    两个渲染层共用这一份实现（原先只在 ``wrong_book.py``，答案卷改版后
    ``make_paper.py`` 也要用）：

    - 错题本条目：待复习条目 ``item_level=4``、已掌握归档条目 ``item_level=5``；
    - 答案卷题目：题级标题 ``### 第 N 题``，故 ``item_level=3``，解析板块落到 ``####``。

    解析中最浅的标题被降到 item_level+1 级，更深的标题保持相对层级，
    最深不超过 6 级（Obsidian 支持的最大标题深度）。不含标题的解析原样返回。
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


def markdown_math_answer(value):
    """为未带数学定界符的公式答案补上行内 LaTeX 定界符。

    题库中的答案既有纯文本（如 ``A``、``0``），也有裸 LaTeX（如
    ``\\frac{1}{2}``）。只包装明显的公式，避免把普通答案强制渲染成数学体。
    已带 ``$`` 的答案保持原样，因为其中可能混有公式和说明文字。
    答案同样先过 ``normalize_math_delimiters``，避免答案里的 ``\\(...\\)``
    裸露进判分卡与错题本。
    """
    text = normalize_math_delimiters(value).strip()
    if not text or "$" in text:
        return text
    if re.search(r"\\[A-Za-z]+|[{}_^]", text):
        return f"${text}$"
    return text


def ensure_utf8_stdio():
    """把 stdout/stderr 强制为 UTF-8，避免 Windows 旧控制台或非 UTF-8 locale 下 print 中文报 UnicodeEncodeError。

    Windows 自带控制台与部分 Linux locale（如 LC_ALL=C）默认编码不是 UTF-8；
    脚本统一用 UTF-8 写文件，但 print 的输出流若不重配会在编码失败时直接抛异常。
    hasattr 守卫兼容 Python < 3.7；errors="replace" 保证任何情况下都不崩溃。
    """
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


ensure_utf8_stdio()


# ---------------------------------------------------------------- YAML subset
def _parse_block(lines, indent=0):
    """解析从指定缩进开始的一个块，返回 (值, 消耗行数)。支持 dict / list / 标量 / 行内结构。"""
    result = {}
    list_items = []
    mode = None
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        cur_indent = len(raw) - len(raw.lstrip(" "))
        if cur_indent < indent:
            break
        if cur_indent > indent:
            raise ValueError(f"非法缩进: {raw!r}")
        is_list_item = stripped.startswith("- ")
        if mode is None:
            mode = "list" if is_list_item else "dict"
        if is_list_item != (mode == "list"):
            break  # 同层混用，结束当前块
        if mode == "list":
            rest = stripped[2:].strip()
            if not rest:
                raise ValueError(f"空列表项: {raw!r}")
            list_items.append(_inline(rest))
            i += 1
            continue
        # dict 项
        if ":" not in stripped:
            raise ValueError(f"无法解析行: {raw!r}")
        key, _, v = stripped.partition(":")
        key = key.strip()
        v = v.strip()
        if v == "" or v.startswith("#"):
            sub, consumed = _parse_block(lines[i + 1:], cur_indent + 2)
            result[_int_key(key)] = sub
            i += 1 + consumed
        else:
            result[_int_key(key)] = _inline(v)
            i += 1
    if mode == "list":
        return list_items, i
    return result, i


def _int_key(k):
    return int(k) if re.fullmatch(r"-?\d+", k) else k


def _strip_comment(v):
    """去掉顶层（括号外）的 ' #' 注释。"""
    depth, in_q = 0, None
    for i, ch in enumerate(v):
        if in_q:
            if ch == in_q:
                in_q = None
            continue
        if ch in "\"'":
            in_q = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "#" and depth == 0:
            if i > 0 and v[i - 1] in " \t":
                return v[:i].strip()
    return v.strip()


def _inline(v):
    """解析行内值：{...} / [...] / 数字 / bool / null / 字符串。"""
    v = _strip_comment(v)
    if v.startswith("{") and v.endswith("}"):
        inner = v[1:-1]
        d = {}
        for part in _split_top(inner):
            if ":" not in part:
                raise ValueError(f"内联字典无冒号: {part!r}")
            k, vv = part.split(":", 1)
            d[k.strip()] = _inline(vv.strip())
        return d
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [_inline(x.strip()) for x in _split_top(inner)]
    if v in ("true", "True"):
        return True
    if v in ("false", "False"):
        return False
    if v in ("null", "None", "~"):
        return None
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if re.fullmatch(r"-?\d+\.\d+", v):
        return float(v)
    if v.startswith('"') and v.endswith('"'):
        return v[1:-1]
    if v.startswith("'") and v.endswith("'"):
        return v[1:-1]
    if "#" in v:
        v = v.split("#", 1)[0].strip()
    return v


def _split_top(s):
    """按顶层逗号拆分（忽略括号内）。"""
    parts, depth, cur = [], 0, []
    for ch in s:
        if ch in "({[":
            depth += 1
            cur.append(ch)
        elif ch in ")}]":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur).strip())
    return parts


def load_yaml(path):
    text = Path(path).read_text(encoding="utf-8")
    lines = text.splitlines()
    data, _ = _parse_block(lines, 0)
    return data


# ---------------------------------------------------------------- subjects / data loads
def normalize_subject(subject=None):
    """Return the stable subject key for a CLI/record value.

    The default remains high mathematics for backwards compatibility.  Callers
    should surface ``ValueError`` through their argument parser rather than
    silently falling back to a different question pool.
    """
    raw = str(subject or SUBJECT_HIGH_MATH).strip().lower()
    try:
        return _SUBJECT_ALIASES[raw]
    except KeyError as exc:
        raise ValueError(
            "未知科目 " + repr(subject) + "（可选：high-math / linear-algebra）"
        ) from exc


def subject_paths(subject=None):
    """Return the schema/index/output paths and naming policy for one subject."""
    key = normalize_subject(subject)
    if key == SUBJECT_LINEAR_ALGEBRA:
        return {
            "key": key,
            "schema": LINEAR_ALGEBRA_SCHEMA_PATH,
            "index": LINEAR_ALGEBRA_INDEX_PATH,
            "wrong_book": LINEAR_ALGEBRA_WRONG_BOOK_PATH,
            "progress": LINEAR_ALGEBRA_PROGRESS_PATH,
            "paper_id_prefix": "la-paper",
            "paper_stem_prefix": "线代卷子",
            "card_stem_prefix": "线代判分卡",
        }
    return {
        "key": key,
        "schema": SCHEMA_PATH,
        "index": INDEX_PATH,
        "wrong_book": WRONG_BOOK_PATH,
        "progress": PROGRESS_PATH,
        "paper_id_prefix": "paper",
        "paper_stem_prefix": "卷子",
        "card_stem_prefix": "判分卡",
    }


def load_schema(subject=None):
    return load_yaml(subject_paths(subject)["schema"])


def load_index(subject=None):
    return json.loads(subject_paths(subject)["index"].read_text(encoding="utf-8"))


def paper_id(subject, n):
    """Return a subject-scoped paper id, e.g. ``paper-01`` or ``la-paper-01``."""
    return f"{subject_paths(subject)['paper_id_prefix']}-{int(n):02d}"


def paper_number(paper_id_):
    """Extract the numeric suffix from a paper id without relying on its prefix."""
    try:
        return int(str(paper_id_).rsplit("-", 1)[1])
    except (IndexError, ValueError) as exc:
        raise ValueError(f"无法从 {paper_id_!r} 解析卷号") from exc


def chapter_number_zh(number):
    """Render a positive chapter number in Chinese (the 880 pools currently use 1–12)."""
    n = int(number)
    digits = "零一二三四五六七八九"
    if 0 <= n < 10:
        return digits[n]
    if 10 <= n < 20:
        return "十" if n == 10 else "十" + digits[n - 10]
    if 20 <= n < 100:
        tens, ones = divmod(n, 10)
        return digits[tens] + "十" + (digits[ones] if ones else "")
    return str(n)


def paper_artifact_stems(subject, paper_id_):
    """Return Obsidian file stems for a paper, answer sheet, and grading card."""
    policy = subject_paths(subject)
    n = paper_number(paper_id_)
    paper_stem = f"{policy['paper_stem_prefix']}-{n:02d}"
    return {
        "paper": paper_stem,
        "answers": f"{paper_stem}-答案",
        "card": f"{policy['card_stem_prefix']}-{n:02d}",
    }


def paper_artifact_paths(subject, paper_id_):
    """Return paths for all Markdown artefacts owned by a paper."""
    stems = paper_artifact_stems(subject, paper_id_)
    folder = paper_dir(paper_id_)
    return {key: folder / f"{stem}.md" for key, stem in stems.items()}


def wrong_book_path(subject=None):
    return subject_paths(subject)["wrong_book"]


def progress_path(subject=None):
    return subject_paths(subject)["progress"]


def subject_from_paper(paper):
    """Resolve a record's subject, including records created before this field existed."""
    for field in ("subject_key", "subject_code", "subject"):
        value = paper.get(field)
        if value:
            try:
                return normalize_subject(value)
            except ValueError:
                pass
    # Old records are high-math papers.  The qid fallback also makes a manually
    # restored pre-field linear-algebra record recoverable.
    qids = [q.get("qid", "") for q in paper.get("questions", [])]
    if qids and all(str(qid_).startswith("la-") for qid_ in qids):
        return SUBJECT_LINEAR_ALGEBRA
    return SUBJECT_HIGH_MATH


def load_attempts():
    if not ATTEMPTS_PATH.exists():
        return {"attempts": [], "wrong_book_status": {}}
    return json.loads(ATTEMPTS_PATH.read_text(encoding="utf-8"))


def save_attempts(data):
    ATTEMPTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ATTEMPTS_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_papers():
    if not PAPERS_PATH.exists():
        return {"papers": []}
    return json.loads(PAPERS_PATH.read_text(encoding="utf-8"))


def save_papers(data):
    PAPERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PAPERS_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_external_links():
    """读取外部错题本关联映射 {qid: {path, anchor, label, ...}}。

    文件不存在返回空 dict（功能未启用）；JSON 损坏时告警但不阻断主流程。
    """
    if not EXTERNAL_LINKS_PATH.exists():
        return {}
    try:
        return json.loads(EXTERNAL_LINKS_PATH.read_text(encoding="utf-8")).get("links", {})
    except ValueError as exc:
        print(f"!! external-links.json 解析失败，本次跳过外部关联: {exc}", file=sys.stderr)
        return {}


def load_analysis():
    """读取过程分析 {items: {qid: {paper_id, cause, step, advice, date}}}。

    文件不存在返回空结构（功能未启用）；JSON 损坏时告警但不阻断主流程。
    """
    if not ANALYSIS_PATH.exists():
        return {"items": {}}
    try:
        return json.loads(ANALYSIS_PATH.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(f"!! analysis.json 解析失败，按空处理: {exc}", file=sys.stderr)
        return {"items": {}}


def save_analysis(data):
    ANALYSIS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ANALYSIS_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_solution_overrides():
    """读取题目级解析覆盖 {qid: 自定义解析文本}。

    索引里的 ``solution`` 是解析册原文的忠实副本（见 ``build_linear_algebra_index.py``），
    重建索引会从源文件重新拷贝，所以自定义讲解不能写回索引，只能走覆盖层：
    渲染时优先取覆盖层，回退到解析册原文。任何产物里出现该题解析的地方都生效
    （答案卷、错题本），且重建后不丢。

    文件不存在返回空 dict（功能未启用）；JSON 损坏时告警但不阻断主流程。
    """
    if not SOLUTION_OVERRIDES_PATH.exists():
        return {}
    try:
        data = json.loads(SOLUTION_OVERRIDES_PATH.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(f"!! solution-overrides.json 解析失败，本次跳过解析覆盖: {exc}", file=sys.stderr)
        return {}
    overrides = {}
    for qid, item in (data.get("solutions") or {}).items():
        text = (item or {}).get("solution") if isinstance(item, dict) else item
        if text:
            overrides[qid] = text
    return overrides


def effective_solution(q, overrides=None):
    """题目的最终解析：优先取覆盖层，回退到索引内的解析册原文。"""
    if overrides is None:
        overrides = load_solution_overrides()
    return overrides.get(q.get("id")) or q.get("solution")


def grade_score_ratio(schema, grade_key):
    """判分态 → 得分比例（对 1.0 / 错 0 / 不会 0 / 半会 0.5 / 粗心 0.5）。"""
    for g in schema["grades"]:
        if g["key"] == grade_key:
            return float(g.get("score_ratio", 0.0))
    return 0.0


def question_full_score(schema, section, idx):
    """第 idx 题（1 起）满分：选择/填空 per_score，解答题取 score_seq。"""
    spec = schema["paper"]["sections"][section]
    if section == "solution":
        seq = spec.get("score_seq") or [12] * spec["count"]
        return seq[idx - 1] if idx - 1 < len(seq) else seq[-1]
    return spec.get("per_score", 5)


def compute_paper_scores(schema, paper, attempts, index):
    """判分后算分：返回该卷每题的满分/得分、题型汇总、章节得分率。

    index 需已 build_index_map（by_id 含 chapter_no）。
    """
    by_section = {s: {"earned": 0.0, "full": 0.0, "count": 0}
                  for s in schema["paper"]["sections"]}
    by_chapter = {}
    q_rows = []
    for q in paper["questions"]:
        qid = q["qid"]
        section = q["section"]
        paper_no = q["paper_no"]
        idx = int(paper_no[1:])
        full = question_full_score(schema, section, idx)
        last = latest_attempt(qid, attempts)
        grade_key = last["grade"] if last else None
        ratio = grade_score_ratio(schema, grade_key) if grade_key else 0.0
        earned = round(full * ratio, 2)
        q_rows.append({
            "qid": qid, "paper_no": paper_no, "section": section,
            "pos": idx, "full_score": full, "earned": earned,
            "grade": grade_key,
        })
        by_section[section]["earned"] += earned
        by_section[section]["full"] += full
        by_section[section]["count"] += 1
        meta = index["by_id"].get(qid)
        if meta:
            ch = meta["chapter_no"]
            c = by_chapter.setdefault(ch, {"earned": 0.0, "full": 0.0})
            c["earned"] += earned
            c["full"] += full
    return {
        "total_earned": round(sum(s["earned"] for s in by_section.values()), 2),
        "total_full": round(sum(s["full"] for s in by_section.values()), 2),
        "sections": by_section,
        "chapters": by_chapter,
        "questions": q_rows,
    }


def today_str():
    return date.today().isoformat()


def now_timestamp():
    """返回可排序的本地时区时间戳，供判分记录确定先后顺序。"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def attempt_sort_key(attempt):
    """兼容旧记录的稳定判分排序键。"""
    raw = attempt.get("recorded_at") or f"{attempt.get('when', '')}T00:00:00"
    try:
        return datetime.fromisoformat(raw).timestamp()
    except (TypeError, ValueError):
        return float("-inf")


def latest_attempt(qid_, attempts):
    """返回一道题按记录时间最新的判分；同一时间按写入顺序决胜。"""
    hits = [a for a in attempts["attempts"] if a.get("qid") == qid_]
    if not hits:
        return None
    return max(enumerate(hits), key=lambda item: (attempt_sort_key(item[1]), item[0]))[1]


def paper_dir(paper_id):
    """每张卷的文件目录：workspace/papers/<paper_id>/（卷子/答案/判分卡都放这里）。"""
    return PAPERS_DIR / paper_id


def qid(chapter_no, difficulty, type_key, qnum):
    return (f"gs-c{int(chapter_no):02d}-{difficulty}-{type_key}-{int(qnum):03d}")


# ---------------------------------------------------------------- 弱点与权重
def _decay_factor(days_ago, half_life_days):
    if half_life_days <= 0:
        return 1.0
    return math.exp(-math.log(2) * days_ago / half_life_days)


def grade_weight_of(schema, grade_key):
    for g in schema["grades"]:
        if g["key"] == grade_key:
            return g["weight"]
    return 0.5


def chapter_weakness(schema, index, attempts, now=None):
    """返回 {chapter_no: 弱点分}。弱点分 = 该章最近判分的加权错误率（时间衰减）。"""
    now = now or date.today()
    grade_weight = {g["key"]: g["weight"] for g in schema["grades"]}
    ch_accum = {}
    ch_count = {}
    ch_attempts = {}
    for a in attempts["attempts"]:
        q = index["by_id"].get(a["qid"])
        if not q:
            continue
        ch = q["chapter_no"]
        try:
            w = date.fromisoformat(a["when"])
        except Exception:
            continue
        days = max(0.0, (now - w).days)
        decay = _decay_factor(days, schema["weakness"]["decay_half_life_days"])
        gw = grade_weight.get(a["grade"], 0.5)
        ch_accum[ch] = ch_accum.get(ch, 0.0) + gw * decay
        ch_count[ch] = ch_count.get(ch, 0) + decay
        ch_attempts[ch] = ch_attempts.get(ch, 0) + 1
    scores = {}
    min_attempts = schema["weakness"].get("min_attempts", 1)
    for ch in sorted(ch_accum):
        if ch_count[ch] <= 0 or ch_attempts[ch] < min_attempts:
            continue
        scores[ch] = ch_accum[ch] / ch_count[ch]
    return scores


def question_weight(schema, q, attempts, now=None):
    """单题抽题权重：base × 尝试衰减 × 最近衰减 × 判分提升（带衰减）。"""
    now = now or date.today()
    base = schema["sampling"]["base_weight"]
    qid_ = q["id"]
    q_attempts = [a for a in attempts["attempts"] if a["qid"] == qid_]
    w = base
    if q_attempts:
        w *= schema["sampling"]["attempt_decay"] ** len(q_attempts)
        last = latest_attempt(qid_, attempts)
        try:
            days = max(0.0, (now - date.fromisoformat(last["when"])).days)
        except Exception:
            days = 0.0
        w *= _decay_factor(days, schema["sampling"]["recency_half_life_days"])
        boost = schema["sampling"]["grade_boost"].get(last["grade"], 1.0)
        boost *= _decay_factor(days, schema["sampling"]["boost_half_life_days"])
        w *= boost
    return w


def build_index_map(index):
    """把 index 的 questions 建成 by_id 字典，挂到 index 上。"""
    index.setdefault("by_id", {})
    for q in index["questions"]:
        index["by_id"][q["id"]] = q
    return index


def validate_index(schema, index, *, strict_review=True):
    """校验题目索引的运行时契约，返回所有错误文本而非在首个错误处退出。"""
    errors = []
    questions = index.get("questions")
    if not isinstance(questions, list) or not questions:
        return ["questions 必须是非空列表"]

    chapter_ids = {c["no"] for c in schema["chapters"]}
    type_ids = set(schema["paper"]["sections"])
    difficulty_ids = set(schema["difficulty_mix"])
    required = {
        "id", "chapter_no", "difficulty", "type", "q_num", "text",
        "answer", "solution", "answer_status",
    }
    seen = set()
    for n, q in enumerate(questions, start=1):
        missing = required - set(q)
        if missing:
            errors.append(f"第 {n} 题缺字段: {', '.join(sorted(missing))}")
            continue
        qid_ = q["id"]
        if not qid_ or qid_ in seen:
            errors.append(f"第 {n} 题 ID 为空或重复: {qid_!r}")
        seen.add(qid_)
        if q["chapter_no"] not in chapter_ids:
            errors.append(f"{qid_}: 未知章节 {q['chapter_no']!r}")
        if q["type"] not in type_ids:
            errors.append(f"{qid_}: 未知题型 {q['type']!r}")
        if q["difficulty"] not in difficulty_ids:
            errors.append(f"{qid_}: 未知难度 {q['difficulty']!r}")
        if not isinstance(q["q_num"], int) or q["q_num"] < 1:
            errors.append(f"{qid_}: q_num 必须为正整数")
        if not str(q["text"] or "").strip():
            errors.append(f"{qid_}: 题干为空")
        if q["answer_status"] not in {"ok", "missing"}:
            errors.append(f"{qid_}: 非法 answer_status {q['answer_status']!r}")
        if q["answer_status"] == "ok" and not (
            str(q["answer"] or "").strip() or str(q["solution"] or "").strip()
        ):
            errors.append(f"{qid_}: 标记为 ok 但答案和解析均为空")

    stats = index.get("stats", {})
    if stats.get("total") != len(questions):
        errors.append(f"stats.total={stats.get('total')!r}，实际题数={len(questions)}")
    pending = stats.get("verify_needs_review", 0)
    if strict_review and pending:
        errors.append(f"仍有 {pending} 个小节待人工复核")
    return errors
