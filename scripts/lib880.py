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
ATTEMPTS_PATH = ROOT / "workspace/records/attempts.json"
PAPERS_PATH = ROOT / "workspace/records/papers.json"
PAPERS_DIR = ROOT / "workspace/papers"
WRONG_BOOK_PATH = ROOT / "workspace/wrong-book/错题本.md"
PROGRESS_PATH = ROOT / "workspace/preview/进度总览.md"


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


# ---------------------------------------------------------------- data loads
def load_schema():
    return load_yaml(SCHEMA_PATH)


def load_index():
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


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


def today_str():
    return date.today().isoformat()


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
    scores = {}
    for ch in sorted(ch_accum):
        if ch_count[ch] <= 0:
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
        last = max(q_attempts, key=lambda a: a["when"])
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
