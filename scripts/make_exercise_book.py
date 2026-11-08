#!/usr/bin/env python3
"""make_exercise_book.py — 生成数二知识点习题集（题目卷 + 答案卷）。

数据口径：
- 题目池：880 错题本、真题错题本、external-notes 下的错题本；
- 掌握度：只看 880 与真题的判分记录（attempts.json + zhenti-problems.json），
  external-notes 只作为选题池，不参与薄弱判定；
- 选题计划：workspace/records/exercise-book-plan.json（人工策展的 57 个知识点、
  题量目标与题目角色）。

用法：
  python3 scripts/make_exercise_book.py
  python3 scripts/make_exercise_book.py --check   # 只校验，不写文件
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import lib880  # noqa: E402

PLAN_PATH = ROOT / "workspace/records/exercise-book-plan.json"
HIGH_MATH_INDEX = ROOT / "workspace/question-index.json"
LINEAR_ALGEBRA_INDEX = ROOT / "workspace/linear-algebra-question-index.json"
ATTEMPTS_PATH = ROOT / "workspace/records/attempts.json"
ZHENTI_PATH = ROOT / "workspace/records/zhenti-problems.json"
ANALYSIS_PATH = ROOT / "workspace/records/analysis.json"
OUT_DIR = ROOT / "workspace/习题集"
BOOK_PATH = OUT_DIR / "数二知识点习题集.md"
ANSWER_PATH = OUT_DIR / "数二知识点习题集-答案.md"

EXTERNAL_ROOTS = [
    ROOT / "external-notes/考研数学",
    ROOT / "external-notes/线性代数",
]
EXTERNAL_MODULES = {
    "高数-函数极限与连续",
    "高数-数列极限",
    "高数-一元微分学",
    "高数-一元函数积分学",
    "高数-多元函数微分学",
    "二重积分",
    "微分方程",
    "第一章：行列式",
    "第二章：矩阵",
    "第三章：线性方程组",
    "第四章：向量与方程组",
    "第五章：矩阵相似理论",
    "第六章：二次型",
}

MASTERY_TARGET = {"薄弱": 5, "一般": 3, "已掌握": 2, "未测": 3}
LEVEL_ORDER = ["薄弱", "一般", "已掌握", "未测"]
LEVEL_BADGE = {"薄弱": "🔴 薄弱", "一般": "🟡 一般", "已掌握": "🟢 已掌握", "未测": "⚪ 未测"}
LEVEL_CALLOUT = {"薄弱": "warning", "一般": "tip", "已掌握": "success", "未测": "question"}

ROLE_NOTE = {
    "active_focus": "当前仍错，且最近一次判为“不会/半会”，最能暴露这一知识点的真实短板。",
    "active_light": "当前仍错，但最近一次判为“粗心/错”，用来检查步骤与计算规范。",
    "mastered": "已做对过，用来复现方法；做对一次不等于永久掌握。",
    "zhenti": "真题原题，代表这一考点在综合卷里的命题方式。",
    "external": "880/真题里这个角度的题不够，用外部错题补方法覆盖面。",
    "new": "880 同章新题，用来补齐题量并检验方法迁移；没有历史判分，做完按首次成绩记录。",
}
TRAP_PREFIX = {
    "active_focus": "你上次错在这类题上：",
    "active_light": "重做时注意：",
    "mastered": "重做时注意：",
    "zhenti": "真题常见陷阱：",
    "external": "原错题本提醒：",
    "new": "新题注意：",
}

FIELD_STOP = re.compile(
    r"^\s*(?:\*\*)?(分析|考点剖析|常规误区|方法论总结|难度|答案|正确答案|参考答案|"
    r"答案速览|解析|解|思路|核心|题型|注|变式|我的|错解|正确|易错|关键|总结|点评|"
    r"难点|考点)(?:\*\*)?\s*[：:]"
)


# --------------------------------------------------------------------------- 基础
def load_json(path, default=None):
    if not path.exists():
        if default is not None:
            return default
        raise SystemExit(f"缺少数据文件：{path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def inline(value):
    return lib880.prepare_inline_text(str(value or ""))


def block(value):
    return lib880.prepare_solution_text(str(value or ""))


_OPTION_PAREN_RE = re.compile(r"(?<![\w$])[（(]\s*([A-D])\s*[)）]")
_OPTION_DOT_RE = re.compile(r"(?<![\w$])([A-D])\s*[.．、]")


def _protected_spans(line):
    """返回行内公式与行内代码占据的区间，供选项切分跳过。"""
    spans = []
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == "`":
            j = line.find("`", i + 1)
            if j == -1:
                break
            spans.append((i, j + 1))
            i = j + 1
            continue
        if ch == "$" and (i == 0 or line[i - 1] != "\\"):
            delim = "$$" if line.startswith("$$", i) else "$"
            j = i + len(delim)
            while j < n:
                if line[j] == "$" and line[j - 1] != "\\":
                    if delim == "$$" and line.startswith("$$", j):
                        j += 2
                        break
                    if delim == "$":
                        j += 1
                        break
                j += 1
            spans.append((i, min(j, n)))
            i = max(j, i + len(delim))
            continue
        i += 1
    return spans


def _option_markers(line):
    spans = _protected_spans(line)

    def inside(pos):
        return any(a <= pos < b for a, b in spans)

    for pattern in (_OPTION_PAREN_RE, _OPTION_DOT_RE):
        markers = []
        for match in pattern.finditer(line):
            if inside(match.start()) or inside(match.start() + 1):
                continue
            markers.append((match.start(), match.group(1)))
        if len(markers) < 2:
            continue
        # 只接受 A→B→C→D 的连续序列；断链处不切，避免把正文里的字母当选项。
        runs = []
        run = [markers[0]]
        for prev, cur in zip(markers, markers[1:]):
            if ord(cur[1]) == ord(prev[1]) + 1:
                run.append(cur)
            else:
                if len(run) >= 2:
                    runs.append(run)
                run = [cur]
        if len(run) >= 2:
            runs.append(run)
        positions = sorted({pos for run in runs for pos, _ in run})
        if len(positions) >= 2:
            return positions
    return []


def format_stem(value):
    """把挤在同一行的选择题选项拆成独立行，便于阅读与核对。"""
    out = []
    for line in str(value or "").split("\n"):
        positions = _option_markers(line)
        if not positions:
            out.append(line)
            continue
        cuts = [0] + positions + [len(line)]
        prefix = line[: positions[0]].strip()
        if prefix:
            out.append(prefix)
        for start, end in zip(cuts[1:-1], cuts[2:]):
            piece = line[start:end].strip()
            if piece:
                out.append(piece)
    return "\n".join(out)


def dequote(lines):
    out = []
    for line in lines:
        if line.startswith("> "):
            out.append(line[2:])
        elif line.strip() == ">":
            out.append("")
        elif line.startswith(">"):
            out.append(line[1:])
        else:
            out.append(line)
    return out


# --------------------------------------------------------------------- 外部错题本
def extract_external_block(block_lines):
    """从一个 `## 错题NN：...` 块里抽取题干与完整解析。

    外部错题本的排版并不统一：题干可能在 `> [!example]` 里，解析可能是
    多个 callout、也可能是 `### ✅ 标准解答过程` 这样的普通小节。旧版只抓
    callout，遇到「先易错点、后标准解答」的块会漏掉正文；这里改成从题干
    结束处一直收到块尾，再剔除题源图、相关知识点与关联区。
    """
    head = block_lines[0]
    match = re.match(r"^##\s+((?:错题|好题)\s*(\d+)\s*[：:]\s*(.*))$", head)
    if not match:
        return None
    num = int(match.group(2))
    title = match.group(3).strip()
    heading = match.group(1).strip()
    body = block_lines[1:]

    start = None
    for i, line in enumerate(body):
        if re.match(r"^\s*>?\s*\*\*题目[^*\n]{0,24}\*\*[^：:\n]{0,24}[：:]", line):
            start = i
            break
    if start is None:
        for i, line in enumerate(body):
            if re.match(r"^\s*>?\s*#{2,4}\s*题目", line):
                start = i
                break
    if start is None:
        return {
            "num": num,
            "title": title,
            "heading": heading,
            "stem": "",
            "solution": "",
            "has_stem": False,
        }

    first = body[start]
    first_clean = re.sub(
        r"^\s*>?\s*\*\*题目[^*\n]{0,24}\*\*[^：:\n]{0,24}[：:]\s*", "", first
    )
    stem_lines = [first_clean] if first_clean.strip() else []
    in_callout = body[start].lstrip().startswith(">")
    i = start + 1
    while i < len(body):
        line = body[i]
        if in_callout and not line.lstrip().startswith(">"):
            break
        deq = line[2:] if line.startswith("> ") else (line[1:] if line.startswith(">") else line)
        stripped = deq.strip()
        if stripped == "---" or stripped.startswith("---"):
            break
        if FIELD_STOP.match(stripped):
            break
        if re.match(r"^#{2,4}\s", stripped):
            break
        if re.match(r"^>?\s*\[!", line):
            break
        stem_lines.append(deq)
        i += 1
    while stem_lines and not stem_lines[-1].strip():
        stem_lines.pop()
    while stem_lines and not stem_lines[0].strip():
        stem_lines.pop(0)
    stem = "\n".join(stem_lines).strip()
    stem = re.sub(r"^\s*#{2,4}\s*(?:题目|例题|问题|真题)\s*\n+", "", stem)
    stem = re.sub(r"^\s*(?:\*\*)?【[^】]{0,24}】(?:\*\*)?\s*", "", stem)
    stem = re.sub(r"^\s*\*\*\d+(?:\.\d+)?\*\*\s*", "", stem)
    stem = re.sub(r"^\s*\d+(?:\.\d+)?\s+", "", stem)
    stem = stem.strip()

    remainder = body[i:]
    cut = len(remainder)
    for j, line in enumerate(remainder):
        stripped = line.lstrip("> ").strip()
        if re.match(
            r"^#{2,6}\s*(?:🔗\s*)?(?:相关知识点|关联|拓展|变式|题目来源|题源)", stripped
        ):
            cut = j
            break
        if re.match(r"^\s*>?\s*\*\*关联", stripped):
            cut = j
            break
    remainder = remainder[:cut]

    # 去掉题源截图等与解题无关的 callout；其余 callout 保留，交给渲染层。
    kept = []
    j = 0
    while j < len(remainder):
        line = remainder[j]
        callout = re.match(r"^\s*>\s*\[!(\w+)\][-+]?\s*(.*)$", line)
        if callout:
            title2 = callout.group(2).strip()
            chunk = [line]
            k = j + 1
            while k < len(remainder) and remainder[k].lstrip().startswith(">"):
                chunk.append(remainder[k])
                k += 1
            if re.search(r"示意图|题源|截图|手写|原图|图片", title2):
                j = k
                continue
            kept.extend(chunk)
            j = k
            continue
        kept.append(line)
        j += 1
    solution = "\n".join(dequote(kept)).strip()
    solution = re.sub(r"^\s*(?:---\s*)+", "", solution).strip()
    solution = re.sub(r"\n{3,}", "\n\n", solution).strip()
    return {
        "num": num,
        "title": title,
        "heading": heading,
        "stem": stem,
        "solution": solution,
        "has_stem": bool(stem),
    }


def load_external_blocks():
    blocks = {}
    for root in EXTERNAL_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.glob("*/错题本.md")):
            module = path.parent.name
            if module not in EXTERNAL_MODULES:
                continue
            rel_file = path.relative_to(ROOT).as_posix()
            lines = path.read_text(encoding="utf-8").splitlines()
            starts = [
                i
                for i, line in enumerate(lines)
                if re.match(r"^##\s+(?:错题|好题)", line)
            ]
            for idx, start in enumerate(starts):
                end = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
                parsed = extract_external_block(lines[start:end])
                if not parsed:
                    continue
                parsed.update(
                    module=module,
                    file=rel_file,
                    id=f"ext-{module}-{parsed['num']:02d}",
                )
                blocks[parsed["id"]] = parsed
    return blocks


def external_image_path(rel_file, raw):
    raw = raw.strip().strip("<>")
    if re.match(r"^[a-z]+://", raw):
        return raw
    if raw.startswith("external-notes/"):
        return raw
    # 外部库内部有时写 `考研数学/模块/images/...`，此时相对的是 external-notes/
    # 而不是当前笔记目录；再拼一次父目录会得到 `.../模块/考研数学/模块/...`。
    if raw.startswith("考研数学/") or raw.startswith("线性代数/"):
        return f"external-notes/{raw}"
    return (Path(rel_file).parent / raw).as_posix()


def normalize_external_embeds(text, rel_file):
    """把外部错题本的相对图片改成 vault 内完整路径。

    880 的 `images/<hash>` 可以按文件名跨目录解析；外部图片放在
    `assets/错题本/` 下，文件名不一定全库唯一，用完整路径更稳，也能被
    `lint_content.py` 的路径解析器核验。
    """

    def wiki(match):
        target = match.group(1).strip()
        if target.startswith("external-notes/") or re.match(r"^[a-z]+://", target):
            return match.group(0)
        return f"![[{external_image_path(rel_file, target)}]]"

    def markdown(match):
        target = match.group(1).strip()
        if re.match(r"^[a-z]+://", target):
            return match.group(0)
        return f"![[{external_image_path(rel_file, target)}]]"

    text = re.sub(r"!\[\[([^\]]+)\]\]", wiki, text)
    text = re.sub(r"!\[[^\]]*\]\(([^)]+)\)", markdown, text)
    return text


def clean_external_solution(text, rel_file):
    text = normalize_external_embeds(str(text or ""), rel_file)
    # 外部错题本里有些 callout 标记没有 `>` 前缀，直接渲染会裸露成 `[!tip]`。
    text = re.sub(
        r"^[ \t]*\[!(\w+)\][-+]?[ \t]*(.*)$",
        lambda m: f"**{m.group(2).strip()}**" if m.group(2).strip() else "",
        text,
        flags=re.M,
    )
    # 相关知识点链接指向外部库自己的目录，保留会变成死链；图片嵌入不动。
    text = re.sub(r"(?<!!)\[\[[^\]]+\]\]", "", text)
    text = re.sub(r"\[([^\]]*)\]\(#[^)]+\)", r"\1", text)
    text = re.sub(r"^\s*[-*]\s*$\n?", "", text, flags=re.M)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_external_answer(solution):
    patterns = [
        r"\*\*正确答案\*\*[：:]\s*([^\n]+)",
        r"\*\*答案\*\*[：:]\s*([^\n]+)",
        r"^答案[：:]\s*([^\n]+)",
        r"答案速览[^\n]*[：:]\s*([^\n]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, solution, flags=re.M)
        if match:
            answer = match.group(1).strip().strip("*")
            if answer and len(answer) <= 200:
                return answer
    boxed = re.search(r"\\boxed\{([^{}\n]{1,160})\}", solution)
    if boxed:
        return boxed.group(1).strip()
    choice = re.search(r"(?:选|答案[是为：:])\s*\**\(?([A-D])\)?\**", solution)
    if choice:
        return choice.group(1)
    return ""


# ------------------------------------------------------------------------- 统计
def load_data():
    plan = load_json(PLAN_PATH)
    gs = {q["id"]: q for q in load_json(HIGH_MATH_INDEX)["questions"]}
    la = {q["id"]: q for q in load_json(LINEAR_ALGEBRA_INDEX)["questions"]}
    questions = {**gs, **la}
    zhenti = load_json(ZHENTI_PATH)["problems"]
    attempts = load_json(ATTEMPTS_PATH)["attempts"]
    analysis = load_json(ANALYSIS_PATH, {"items": {}}).get("items", {})
    external = load_external_blocks()
    return plan, questions, zhenti, attempts, analysis, external


def attempts_by_qid(attempts, zhenti):
    by_qid = defaultdict(list)
    for item in attempts:
        by_qid[item["qid"]].append(
            ("880", item.get("when", ""), item.get("recorded_at", ""), item["grade"])
        )
    for qid, record in zhenti.items():
        for item in record.get("attempts", []):
            by_qid[qid].append(("zt", item.get("date", ""), "", item["grade"]))
    for qid in by_qid:
        by_qid[qid].sort(key=lambda x: (x[1], x[2]))
    return by_qid


def compute_stats(plan, by_qid):
    stats = {
        kp: {"n": 0, "ok": 0, "active": 0, "focus": 0, "mastered": 0}
        for kp in plan["kp_meta"]
    }
    for qid, records in by_qid.items():
        kp = plan["qid_kp"].get(qid)
        if not kp or kp not in stats:
            continue
        records = sorted(records, key=lambda x: (x[1], x[2]))
        item = stats[kp]
        item["n"] += 1
        if records[0][3] == "correct":
            item["ok"] += 1
        if records[-1][3] != "correct":
            item["active"] += 1
            if records[-1][3] in ("cannot", "half"):
                item["focus"] += 1
        elif any(r[3] != "correct" for r in records[:-1]):
            item["mastered"] += 1
    for item in stats.values():
        item["acc"] = item["ok"] / item["n"] if item["n"] else 0.0
        item["level"] = mastery_level(item)
        item["score"] = weakness_score(item)
    return stats


def mastery_level(item):
    if item["n"] == 0:
        return "未测"
    if item["active"] >= 2 or (item["active"] >= 1 and item["acc"] < 0.5):
        return "薄弱"
    if item["active"] == 1 or item["acc"] < 0.6:
        return "一般"
    return "已掌握"


def weakness_score(item):
    if item["n"] == 0:
        return 0.0
    return (
        3 * item["focus"]
        + 1.5 * (item["active"] - item["focus"])
        + 2 * (1 - item["acc"])
        + 0.5 * min(item["active"], 5)
    )


# ------------------------------------------------------------------------- 选题
def build_entries(plan, questions, zhenti, by_qid, external):
    """按计划顺序组装题目；新出现的活跃错题自动补入，避免漏掉当前错题。"""
    selected = {qid for items in plan["selection"].values() for qid, _ in items}
    duplicate_of = plan.get("duplicate_of", {})
    additions = defaultdict(list)
    for qid, records in by_qid.items():
        kp = plan["qid_kp"].get(qid)
        if not kp or kp not in plan["kp_meta"] or qid in selected or qid in duplicate_of:
            continue
        if records[-1][3] != "correct":
            role = "active_focus" if records[-1][3] in ("cannot", "half") else "active_light"
            additions[kp].append((qid, role))

    entries = []
    qnum = 0
    kp_order = []
    for kp, meta in plan["kp_meta"].items():
        items = list(plan["selection"].get(kp, []))
        items.extend(additions.get(kp, []))
        kp_entries = []
        for qid, role in items:
            if qid in duplicate_of:
                continue
            qnum += 1
            entry = {"number": qnum, "qid": qid, "role": role, "kp": kp}
            if qid.startswith("ext-"):
                external_block = external.get(qid)
                if not external_block or not external_block.get("stem"):
                    raise SystemExit(f"外部错题缺少可渲染内容：{qid}")
                entry.update(
                    source="external",
                    title=external_block["title"],
                    stem=normalize_external_embeds(external_block["stem"], external_block["file"]),
                    solution=clean_external_solution(
                        external_block["solution"], external_block["file"]
                    ),
                    answer=extract_external_answer(external_block["solution"]),
                    module=external_block["module"],
                    num=external_block["num"],
                    heading=external_block["heading"],
                    file=external_block["file"],
                )
            elif qid.startswith("zt-"):
                record = zhenti.get(qid)
                if not record or not record.get("stem") or not record.get("solution"):
                    raise SystemExit(f"真题错题缺少题干或解析：{qid}")
                entry.update(
                    source="zhenti",
                    stem=record["stem"],
                    solution=record["solution"],
                    answer=record.get("answer", ""),
                    year=record.get("year", ""),
                    no=record.get("no", ""),
                    paper=record.get("paper", ""),
                )
            else:
                record = questions.get(qid)
                if not record:
                    raise SystemExit(f"880 题号不存在：{qid}")
                entry.update(
                    source="880",
                    stem=lib880.effective_text(record),
                    solution=lib880.effective_solution(record),
                    answer=record.get("answer", ""),
                    chapter=record.get("chapter_title", ""),
                    type_zh=record.get("type_zh", ""),
                    difficulty_zh=record.get("difficulty_zh", ""),
                    q_num=record.get("q_num", ""),
                )
            kp_entries.append(entry)
            entries.append(entry)
        kp_order.append((kp, kp_entries))
    return entries, kp_order, additions


def chapter_groups(plan, kp_order):
    groups = []
    current = None
    chapter_index = 0
    kp_index = 0
    for kp, kp_entries in kp_order:
        meta = plan["kp_meta"][kp]
        chapter = meta["chapter"]
        if current is None or current["title"] != chapter:
            chapter_index += 1
            kp_index = 0
            current = {"index": chapter_index, "title": chapter, "kps": []}
            groups.append(current)
        kp_index += 1
        current["kps"].append(
            {
                "kp": kp,
                "meta": meta,
                "no": f"{chapter_index}.{kp_index}",
                "entries": kp_entries,
            }
        )
    return groups


# ------------------------------------------------------------------------- 文案
def source_counts(entries):
    return Counter(e["source"] for e in entries)


def level_text(item):
    if item["n"] == 0:
        return "⚪ 尚未测到 ｜ 880/真题 0 道判分记录"
    return (
        f"{LEVEL_BADGE[item['level']]} ｜ 首做正确率 {item['acc']:.0%}"
        f"（{item['ok']}/{item['n']}）｜ 活跃错题 {item['active']} 道"
        f"（重点 {item['focus']} 道）｜ 已掌握归档 {item['mastered']} 道"
    )


def kp_callout(item, count):
    level = item["level"]
    if level == "未测":
        return (
            "> [!question] 还没有被 880/真题验证\n"
            "> 880 与真题里没有这一知识点的判分记录；本组题全部来自外部错题本。"
            "做完这组不等于通过验证，建议再用 880 同章新题或真题同考点限时验一次。"
        )
    if level == "薄弱":
        return (
            "> [!warning] 这是本册的重点\n"
            f"> 首做正确率仅 {item['acc']:.0%}（{item['ok']}/{item['n']}），"
            f"当前还有 {item['active']} 道活跃错题（重点 {item['focus']} 道）。"
            f"先做本组前 {min(3, count)} 题，做完立刻对答案；如果仍卡，回到「必会通法」逐条对照。"
        )
    if level == "一般":
        return (
            "> [!tip] 掌握度一般\n"
            f"> 首做正确率 {item['acc']:.0%}，当前 {item['active']} 道活跃错题。"
            "这组题用来把方法补齐，不必追求速度；做完重点看步骤是否完整。"
        )
    note = (
        "> [!success] 已掌握\n"
        f"> 当前无活跃错题，首做正确率 {item['acc']:.0%}。"
        "这组题用于保持手感；若重做卡住，按薄弱处理。"
    )
    if item["n"] < 3:
        note += f"\n> 注意：样本只有 {item['n']} 道，掌握度证据偏薄。"
    return note


def source_label(entry):
    if entry["source"] == "880":
        return (
            f"【880 · {entry.get('chapter', '')} · {entry.get('type_zh', '')} · "
            f"{entry.get('difficulty_zh', '')} · 第{entry.get('q_num', '')}题】"
        )
    if entry["source"] == "zhenti":
        return f"【真题 · {entry.get('year', '')} · {entry.get('paper', '')} · {entry.get('no', '')}】"
    label = entry.get('heading', '').split('：')[0]
    return f"【外部 · {entry.get('module', '')} · {label}】"


def source_title(entry):
    if entry["source"] == "880":
        return (
            f"880 做题本 · {entry.get('chapter', '')} · {entry.get('type_zh', '')} "
            f"第{entry.get('q_num', '')}题（`{entry['qid']}`）"
        )
    if entry["source"] == "zhenti":
        return f"真题 · {entry.get('year', '')} {entry.get('paper', '')} · {entry.get('no', '')}"
    display = entry["heading"].split("：")[0]
    return f"外部错题本 · {entry['module']} · {display}"


def role_note(entry):
    if entry["role"] == "zhenti":
        records = entry.get("_records")
        if records and records[-1][3] != "correct":
            return "真题原题，且当前仍在错题本里；按考场标准重做，不要先看答案。"
        return "真题原题，已做对过；用来检验能否在综合题里认出这个考点。"
    return ROLE_NOTE.get(entry["role"], ROLE_NOTE["mastered"])


def trap_note(entry, kp_traps):
    if not kp_traps:
        return ""
    trap = kp_traps[(entry["number"] - 1) % len(kp_traps)]
    return TRAP_PREFIX.get(entry["role"], "注意：") + trap


def chapter_summary(plan, chapter, stats):
    kps = chapter["kps"]
    n = sum(stats[k["kp"]]["n"] for k in kps)
    ok = sum(stats[k["kp"]]["ok"] for k in kps)
    active = sum(stats[k["kp"]]["active"] for k in kps)
    focus = sum(stats[k["kp"]]["focus"] for k in kps)
    weak = sum(1 for k in kps if stats[k["kp"]]["level"] == "薄弱")
    untested = sum(1 for k in kps if stats[k["kp"]]["level"] == "未测")
    count = sum(len(k["entries"]) for k in kps)
    sources = Counter(e["source"] for k in kps for e in k["entries"])
    acc = f"{ok / n:.0%}" if n else "—"
    return (
        f"本章 {len(kps)} 个知识点，{weak} 个薄弱、{untested} 个未测；"
        f"本册选 {count} 道（880 {sources['880']} · 真题 {sources['zhenti']} · 外部 {sources['external']}）；"
        f"本章累计已判 {n} 道，首做正确率 {acc}；活跃错题 {active} 道（重点 {focus} 道）。"
    )


def md_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows)
    return "\n".join(lines)


def kp_anchor(no, name):
    return f"{no} {name}"


def kp_link(no, name):
    return f"[[数二知识点习题集#{kp_anchor(no, name)}|{name}]]"


def answer_link(no, name):
    return f"[[数二知识点习题集-答案#{kp_anchor(no, name)}|本组答案与解析]]"


# ------------------------------------------------------------------------- 主卷
def render_book(plan, groups, stats, entries, analysis, questions):
    date = plan.get("date", "2026-11-08")
    all_stats = list(stats.values())
    level_counts = Counter(item["level"] for item in all_stats)
    level_problems = Counter()
    for group in groups:
        for kp in group["kps"]:
            level_problems[stats[kp["kp"]]["level"]] += len(kp["entries"])

    by_qid = {e["qid"]: e for e in entries}
    total_880 = len(questions)
    # 统计口径直接数判分记录，避免把“题库里有但没做”的题算进首做正确率。
    attempt_qids = {qid for qid, recs in _ATTEMPT_CACHE.items() if recs and not qid.startswith("zt-")}
    zt_qids = {qid for qid, recs in _ATTEMPT_CACHE.items() if recs and qid.startswith("zt-")}
    n880 = len(attempt_qids)
    nzt = len(zt_qids)
    ok880 = sum(1 for qid in attempt_qids if _ATTEMPT_CACHE[qid][0][3] == "correct")
    okzt = sum(1 for qid in zt_qids if _ATTEMPT_CACHE[qid][0][3] == "correct")
    active880 = sum(1 for qid in attempt_qids if _ATTEMPT_CACHE[qid][-1][3] != "correct")
    activezt = sum(1 for qid in zt_qids if _ATTEMPT_CACHE[qid][-1][3] != "correct")
    focus880 = sum(
        1 for qid in attempt_qids if _ATTEMPT_CACHE[qid][-1][3] in ("cannot", "half")
    )
    focuszt = sum(1 for qid in zt_qids if _ATTEMPT_CACHE[qid][-1][3] in ("cannot", "half"))

    lines = [
        "---",
        "type: 文档",
        f"date: {date}",
        f"updated: {date}",
        "tags: [考研数学, 数二, 习题集, 高数, 线代]",
        "---",
        "",
        "# 考研数学二 · 知识点错题习题集",
        "",
        "> [!info] 这本书怎么用",
        "> - **题源**：880 错题本（高数 + 线代）、真题错题本、`external-notes/` 下的错题本。同一道题只出现一次，答案与解析在 "
        "[[数二知识点习题集-答案]]。",
        "> - **薄弱判定**：只看 880 与真题的判分记录（`attempts.json` + `zhenti-problems.json`）；"
        "external-notes 只作为选题池，不参与掌握度计算。",
        "> - **题量规则**：薄弱 5 道、一般 3 道、已掌握 2 道、尚未测到 3 道；薄弱知识点优先放“当前仍错”的题。"
        "活跃错题全部纳入，所以个别知识点会略高于目标；错题本里不够的，见「需要补充的」。",
        "> - **标记**：🔴 薄弱 · 🟡 一般 · 🟢 已掌握 · ⚪ 尚未测到；`【880】` `【真题】` `【外部】` 标明题源。",
        "> - **建议顺序**：先做标 🔴 的知识点，每个知识点限时做完再对答案；错题回到 [[错题本]] / "
        "[[真题错题本]] 更新状态。",
        "",
        f"> [!summary] 一句话结论（数据截至 {date}）",
        f"> 你的数二错题不是“题量不够”，而是**线代后三章（方程组、相似、二次型）和高数极限/中值定理**成片薄弱："
        f"{level_counts['薄弱']} 个知识点标红，{active880 + activezt} 道活跃错题全部收入本册。"
        "先按「最该先补的 5 个」做，再按章清理。",
        "",
        "## 掌握度总览",
        "",
        "### 判分口径",
        "",
        md_table(
            ["口径", "880", "真题", "合计"],
            [
                ["题量", total_880, nzt, total_880 + nzt],
                ["已判", n880, nzt, n880 + nzt],
                [
                    "首次正确率",
                    f"{ok880 / n880:.1%}" if n880 else "—",
                    f"{okzt / nzt:.1%}" if nzt else "—",
                    f"{(ok880 + okzt) / (n880 + nzt):.1%}" if n880 + nzt else "—",
                ],
                ["活跃错题", active880, activezt, active880 + activezt],
                ["其中重点", focus880, focuszt, focus880 + focuszt],
            ],
        ),
        "",
        "> [!note] 为什么不用 external-notes 判薄弱",
        "> 外部错题本没有 880/真题的判分记录，混进来会把“看过解析”误当成“会做”。"
        "它在这里只负责补题目角度；掌握度仍以 880 和真题的首做结果为准。",
        "",
        "### 掌握度分布",
        "",
        md_table(
            ["掌握度", "知识点", "本册题数", "题量规则"],
            [
                [
                    LEVEL_BADGE[level],
                    level_counts[level],
                    level_problems[level],
                    f"{MASTERY_TARGET[level]} 道"
                    + ("（活跃错题全收）" if level == "薄弱" else "")
                    + ("（外部补）" if level == "未测" else ""),
                ]
                for level in LEVEL_ORDER
            ],
        ),
        "",
        "### 章节分布",
        "",
        md_table(
            ["章节", "知识点", "薄弱", "未测", "本册题数", "首做正确率", "活跃错题"],
            [
                [
                    group["title"],
                    len(group["kps"]),
                    sum(1 for k in group["kps"] if stats[k["kp"]]["level"] == "薄弱"),
                    sum(1 for k in group["kps"] if stats[k["kp"]]["level"] == "未测"),
                    sum(len(k["entries"]) for k in group["kps"]),
                    (
                        f"{sum(stats[k['kp']]['ok'] for k in group['kps']) / sum(stats[k['kp']]['n'] for k in group['kps']):.0%}"
                        if sum(stats[k["kp"]]["n"] for k in group["kps"])
                        else "—"
                    ),
                    sum(stats[k["kp"]]["active"] for k in group["kps"]),
                ]
                for group in groups
            ],
        ),
        "",
        "### 最薄弱的 15 个知识点",
        "",
    ]
    ranked = sorted(
        (item for item in all_stats if item["n"] > 0),
        key=lambda item: (-item["score"], -item["active"], -item["focus"]),
    )[:15]
    rank_rows = []
    for rank, item in enumerate(ranked, start=1):
        kp = next(k for k, v in stats.items() if v is item)
        meta = plan["kp_meta"][kp]
        count = len(next(k["entries"] for g in groups for k in g["kps"] if k["kp"] == kp))
        rank_rows.append(
            [
                rank,
                kp_link(next(k["no"] for g in groups for k in g["kps"] if k["kp"] == kp), meta["name"]),
                meta["chapter"],
                item["n"],
                f"{item['acc']:.0%}",
                f"{item['active']}（{item['focus']}）",
                count,
            ]
        )
    lines.append(
        md_table(
            ["#", "知识点", "章节", "已判", "首对率", "活跃（重点）", "本册"],
            rank_rows,
        )
    )
    lines.extend(["", "> [!warning] 如果只有一周", "> 按顺序做下面 5 个，共 27 道；每天 4–5 道，第 7 天回炉。", ">"])
    for rank, item in enumerate(ranked[:5], start=1):
        kp = next(k for k, v in stats.items() if v is item)
        meta = plan["kp_meta"][kp]
        no = next(k["no"] for g in groups for k in g["kps"] if k["kp"] == kp)
        count = len(next(k["entries"] for g in groups for k in g["kps"] if k["kp"] == kp))
        lines.append(
            f"> {rank}. {kp_link(no, meta['name'])}（{meta['chapter']}）："
            f"{item['n']} 道已判，首对率 {item['acc']:.0%}，活跃 {item['active']} 道（重点 {item['focus']} 道），本组 {count} 道。"
        )

    lines.append("")
    for group in groups:
        lines.extend([f"## {group['title']}", "", chapter_summary(plan, group, stats), ""])
        for kp in group["kps"]:
            item = stats[kp["kp"]]
            meta = kp["meta"]
            entries_kp = kp["entries"]
            sources = source_counts(entries_kp)
            lines.extend(
                [
                    f"### {kp_anchor(kp['no'], meta['name'])}",
                    "",
                    f"**掌握度：** {level_text(item)}",
                    "",
                    f"**本组题量：** {len(entries_kp)} 道（880 {sources['880']} · 真题 {sources['zhenti']} · 外部 {sources['external']}）",
                    "",
                    kp_callout(item, len(entries_kp)),
                    "",
                    "**这一知识点怎么考**",
                    "",
                    inline(plan["kps"][kp["kp"]]["core"]),
                    "",
                    "**必会通法**",
                    "",
                ]
            )
            for method in plan["kps"][kp["kp"]]["methods"]:
                lines.append(f"- {inline(method)}")
            lines.extend(["", "**高频陷阱**", ""])
            for trap in plan["kps"][kp["kp"]]["traps"]:
                lines.append(f"- {inline(trap)}")
            lines.extend(["", f"**代表题（{len(entries_kp)} 道）**", ""])
            for entry in entries_kp:
                lines.extend(
                    [
                        f"**Q{entry['number']}**　{source_label(entry)}",
                        "",
                        block(format_stem(entry["stem"])),
                        "",
                    ]
                )
            lines.extend(
                [
                    f"*答案与解析：{answer_link(kp['no'], meta['name'])}*",
                    "",
                ]
            )

    lines.extend(render_supplement(plan, groups, stats, ranked, active880 + activezt))
    lines.extend(
        [
            "## 关联",
            "",
            "- 答案与解析：[[数二知识点习题集-答案]]",
            "- 880 错题本：[[错题本]]",
            "- 线代错题本：[[线代错题本]]",
            "- 真题错题本：[[真题错题本]]",
            "- 进度总览：[[进度总览]]",
            "",
        ]
    )
    return "\n".join(lines)


def render_supplement(plan, groups, stats, ranked, active_total):
    kp_meta = plan["kp_meta"]
    kp_no = {k["kp"]: k["no"] for g in groups for k in g["kps"]}
    kp_entries = {k["kp"]: k["entries"] for g in groups for k in g["kps"]}

    under = []
    for kp, meta in kp_meta.items():
        item = stats[kp]
        target = MASTERY_TARGET[item["level"]]
        count = len(kp_entries[kp])
        if count < target:
            under.append((target - count, kp, meta, item, count, target))

    lines = [
        "## 需要补充的",
        "",
        "> [!warning] 这份习题集没有覆盖什么",
        "> 它只覆盖“错题本里已经有的题”。下面这些缺口，是下一阶段该补的题和该换的练法；"
        "不是让你把整本 880 再刷一遍。",
        "",
        "### 一、题量没到目标的知识点",
        "",
    ]
    under_rows = []
    for gap, kp, meta, item, count, target in sorted(
        under, key=lambda x: (LEVEL_ORDER.index(x[3]["level"]), -x[0])
    ):
        if gap <= 1:
            hint = "从 880 同章补 1 道同题型"
        elif gap == 2:
            hint = "从 880 同章补 2 道，或外部同模块再筛 1 道"
        else:
            hint = "从 880 同章补 2–3 道基础题，先把概念打牢"
        under_rows.append(
            [
                kp_link(kp_no[kp], meta["name"]),
                LEVEL_BADGE[item["level"]],
                f"{count}/{target}",
                gap,
                hint,
            ]
        )
    lines.append(md_table(["知识点", "掌握度", "现有/目标", "缺口", "建议"], under_rows))
    lines.extend(
        [
            "",
            "> [!warning] 有 6 个知识点在外部错题本里没有独立模块",
            "> 函数性质与函数方程、偏导数与全微分计算、交换积分次序、二阶常系数齐次线性方程、"
            "行列式与伴随矩阵综合、二次型与特征值综合。这些只能从 880 同章新题或真题同考点补，"
            "不要硬等外部错题本更新。",
            "",
            "### 二、880/真题还没验证过的知识点",
            "",
        ]
    )
    untested = [(kp, meta) for kp, meta in kp_meta.items() if stats[kp]["level"] == "未测"]
    untested_rows = []
    for kp, meta in untested:
        entries_kp = kp_entries[kp]
        untested_rows.append(
            [
                kp_link(kp_no[kp], meta["name"]),
                len(entries_kp),
                "全部外部",
                "没有 880/真题判分记录，可能“看懂但不会做”",
                "先用 880 同章 3 道基础题限时验证，正确率 ≥80% 才算过",
            ]
        )
    lines.append(md_table(["知识点", "本组题", "题源", "风险", "验证动作"], untested_rows))
    lines.extend(
        [
            "",
            "### 三、证据偏薄：只有 1–2 道判分记录",
            "",
            "这些知识点的“已掌握/一般”结论只来自 1–2 道题，参考价值有限；"
            "如果你重做本组题仍不顺，直接按薄弱处理。",
            "",
        ]
    )
    thin_rows = []
    for kp, meta in kp_meta.items():
        item = stats[kp]
        if 0 < item["n"] < 3:
            thin_rows.append(
                [
                    kp_link(kp_no[kp], meta["name"]),
                    LEVEL_BADGE[item["level"]],
                    item["n"],
                    f"{item['acc']:.0%}",
                ]
            )
    lines.append(md_table(["知识点", "当前判定", "已判", "首对率"], thin_rows))
    lines.extend(
        [
            "",
            "### 四、下一步练什么（6 周）",
            "",
        ]
    )
    weak = [(item, kp) for kp, item in stats.items() if item["level"] == "薄弱"]
    weak.sort(key=lambda pair: (-pair[0]["score"], -pair[0]["active"], -pair[0]["focus"]))

    def count_range(start, end):
        return sum(len(kp_entries[weak[i][1]]) for i in range(start, min(end, len(weak))))

    rest = weak[15:]
    rest_gs = [kp for _, kp in rest if kp_meta[kp]["subject"] == "高数"]
    rest_la = [kp for _, kp in rest if kp_meta[kp]["subject"] == "线代"]
    plan_rows = [
        [
            "第 1 周",
            "最薄弱的 5 个",
            count_range(0, 5),
            "每天 4–5 道；先重做活跃错题，做完立刻对答案",
        ],
        [
            "第 2 周",
            "第 6–10 个",
            count_range(5, 10),
            "按知识点分组限时，重点看起手方法",
        ],
        [
            "第 3 周",
            "第 11–15 个",
            count_range(10, 15),
            "每个知识点先看「必会通法」，再做前 2 题",
        ],
        [
            "第 4 周",
            "高数剩余薄弱",
            sum(len(kp_entries[kp]) for kp in rest_gs),
            "按章拆分，每天 8–9 道；错题当天回炉",
        ],
        [
            "第 5 周",
            "线代剩余薄弱",
            sum(len(kp_entries[kp]) for kp in rest_la),
            "隔日重做；线代证明题要写完整步骤",
        ],
        [
            "第 6 周",
            "真题 + 未测 + 模拟卷",
            "15 + 6 + 1 张",
            "2018/2019 活跃真题限时；gs6-2、gs6-4 用 880 验证；最后拼 1 张模拟卷",
        ],
    ]
    lines.append(md_table(["时间", "内容", "题量", "做法"], plan_rows))
    lines.extend(
        [
            "",
            "### 五、比刷题更该先修的",
            "",
            "1. **概念/定理的条件**：已做过程归因的 10 道题里，5 道是概念/定理错误。"
            "每做一个知识点，先用一句话说清“定理成立需要什么条件”，再动笔。",
            "2. **最后 30 秒回代**：1 道计算/代数错误、2 道步骤/逻辑遗漏。"
            "解完方程、定完积分、写完通解，都把结果代回原条件检查一遍。",
            "3. **真题限时**：2018 年真题当前还有 10 道活跃错题，2019 年有 5 道。"
            "不要按知识点拆着做，按 180 分钟整卷做一次，暴露时间分配问题。",
            "4. **外部错题本不是进度**：external-notes 的题做对，不要拿去把 880 错题标“已掌握”；"
            "两套记录分开，否则进度总览会虚高。",
            "",
            f"> [!tip] 最后一句\n> 本册共 {sum(len(v) for v in kp_entries.values())} 道题，"
            f"其中 {active_total} 道是你当前仍错的活跃错题。先把这 {active_total} 道清掉，"
            "比再找 100 道新题更有用。",
            "",
        ]
    )
    return lines


# ------------------------------------------------------------------------- 答案卷
def render_answer(plan, groups, stats, entries, analysis):
    date = plan.get("date", "2026-11-08")
    lines = [
        "---",
        "type: 文档",
        f"date: {date}",
        f"updated: {date}",
        "tags: [考研数学, 数二, 习题集, 答案]",
        "---",
        "",
        "# 数二知识点习题集 · 答案与解析",
        "",
        "> [!info] 怎么用这本答案",
        f"> - 题号 Q1–Q{len(entries)} 与 [[数二知识点习题集]] 一一对应，按章节/知识点同序排列。",
        "> - 先独立做完再对照；解析保留 880 解析册原文、真题解析和外部错题本的错因分析。",
        "> - **易错点** 按本知识点的陷阱轮换提示，不是这道题的唯一错法；"
        "**为什么选它** 说明它在组里的角色。",
        "> - 外部题的“答案”若写“见解析”，是因为原错题本把答案写在推导里；以解析中的最终结果为准。",
        "",
    ]
    for group in groups:
        lines.extend([f"## {group['title']}", ""])
        for kp in group["kps"]:
            meta = kp["meta"]
            entries_kp = kp["entries"]
            item = stats[kp["kp"]]
            numbers = [e["number"] for e in entries_kp]
            span = f"Q{numbers[0]}–Q{numbers[-1]}" if len(numbers) > 1 else f"Q{numbers[0]}"
            lines.extend(
                [
                    f"### {kp_anchor(kp['no'], meta['name'])}",
                    "",
                    f"**本组题号：** {span} ｜ **掌握度：** {LEVEL_BADGE[item['level']]}",
                    "",
                ]
            )
            for entry in entries_kp:
                lines.extend(
                    [
                        f"#### Q{entry['number']}",
                        "",
                        f"**题源：** {source_title(entry)}",
                        "",
                        f"**答案：** {render_answer_value(entry)}",
                        "",
                        "**解析：**",
                        "",
                        render_solution(entry),
                        "",
                        f"**易错点：** {inline(trap_note(entry, plan['kps'][kp['kp']]['traps']))}",
                        "",
                        f"**为什么选它：** {role_note(entry)}",
                        "",
                    ]
                )
                cause = analysis.get(entry["qid"])
                if cause:
                    lines.extend(
                        [
                            "> [!info] 错因分析",
                            f"> **错因：** {inline(cause.get('cause', ''))}",
                            f"> **出错环节：** {inline(cause.get('step', ''))}",
                            f"> **建议：** {inline(cause.get('advice', ''))}",
                            "",
                        ]
                    )
                if entry["source"] == "external":
                    display = entry["heading"].split("：")[0]
                    lines.append(
                        f"*来源：[[{entry['file']}#{entry['heading']}|外部错题本 · "
                        f"{entry['module']} · {display}]]*"
                    )
                    lines.append("")
            lines.append(f"*返回题目：{kp_link(kp['no'], meta['name'])}*")
            lines.append("")
    lines.extend(
        [
            "## 关联",
            "",
            "- 题目：[[数二知识点习题集]]",
            "- 880 错题本：[[错题本]]",
            "- 线代错题本：[[线代错题本]]",
            "- 真题错题本：[[真题错题本]]",
            "",
        ]
    )
    return "\n".join(lines)


def render_answer_value(entry):
    answer = str(entry.get("answer") or "").strip()
    if not answer:
        return "见解析"
    # 外部题抽到的答案可能是整段 `$$...$$`；嵌在“**答案：**”同一行时必须降级为
    # 行内 `$...$`，否则会撑破所在段落（obsidian-content.md 第 5 条）。
    answer = re.sub(r"^\s*\$\$(.+?)\$\$\s*$", r"$\1$", answer, flags=re.S)
    return lib880.markdown_math_answer(inline(answer))


def render_solution(entry):
    text = block(entry.get("solution", ""))
    text = lib880.demote_solution_headings(text, item_level=4)
    return text


# --------------------------------------------------------------------------- 校验
def validate(plan, entries, groups, stats):
    errors = []
    if len(plan["kps"]) != len(plan["kp_meta"]):
        errors.append("kps 与 kp_meta 数量不一致")
    qids = [e["qid"] for e in entries]
    dup = [qid for qid, count in Counter(qids).items() if count > 1]
    if dup:
        errors.append(f"题目重复：{dup[:5]}")
    selected = {qid for items in plan["selection"].values() for qid, _ in items}
    for qid, target in plan.get("duplicate_of", {}).items():
        if target not in selected:
            errors.append(f"重复题替代目标未入选：{qid} → {target}")
    if not entries:
        errors.append("没有可渲染题目")
    for group in groups:
        for kp in group["kps"]:
            if not kp["entries"]:
                errors.append(f"{kp['kp']} 没有题目")
    if errors:
        raise SystemExit("；".join(errors))


# --------------------------------------------------------------------------- main
_ATTEMPT_CACHE = {}


def main():
    parser = argparse.ArgumentParser(description="生成数二知识点习题集")
    parser.add_argument("--check", action="store_true", help="只校验，不写文件")
    args = parser.parse_args()

    plan, questions, zhenti, attempts, analysis, external = load_data()
    by_qid = attempts_by_qid(attempts, zhenti)
    _ATTEMPT_CACHE.update(by_qid)
    stats = compute_stats(plan, by_qid)
    entries, kp_order, additions = build_entries(plan, questions, zhenti, by_qid, external)
    groups = chapter_groups(plan, kp_order)
    validate(plan, entries, groups, stats)

    added = sum(len(v) for v in additions.values())
    if added:
        print(f"自动补入 {added} 道新活跃错题（计划文件未列）。")

    book = render_book(plan, groups, stats, entries, analysis, questions)
    answer = render_answer(plan, groups, stats, entries, analysis)

    if args.check:
        print(f"校验通过：{len(entries)} 道题，{len(groups)} 章，{len(plan['kp_meta'])} 个知识点。")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    BOOK_PATH.write_text(book, encoding="utf-8")
    ANSWER_PATH.write_text(answer, encoding="utf-8")
    print(f"已生成：{BOOK_PATH.relative_to(ROOT)}")
    print(f"已生成：{ANSWER_PATH.relative_to(ROOT)}")
    print(f"题目 {len(entries)} 道；知识点 {len(plan['kp_meta'])} 个；章节 {len(groups)} 个。")


if __name__ == "__main__":
    main()
