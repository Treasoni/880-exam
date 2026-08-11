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
EXTERNAL_LINKS_PATH = ROOT / "workspace/records/external-links.json"
ANALYSIS_PATH = ROOT / "workspace/records/analysis.json"


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
