#!/usr/bin/env python3
"""merge_extraction.py — 把提取 Workflow 的 journal 结果合并成 question-index.json。

用法：
  python3 scripts/merge_extraction.py --journal <journal.jsonl>
  也可 --journal 缺省时自动用 workspace/.build/latest_journal.jsonl
  # Windows 请把 python3 换成 py -3
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib880

Q_MARK_RE = re.compile(r"^[（(]\d+[)）]\s*")


def load_journal(path):
    extracts, verifies = {}, {}
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get("type") != "result":
            continue
        r = d.get("result")
        if not isinstance(r, dict):
            continue
        sid = r.get("section_id")
        if not sid:
            continue
        if "questions" in r:
            extracts[sid] = r  # 后到覆盖（重提取时用）
        elif "verdict" in r:
            verifies[sid] = r
    return extracts, verifies


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--journal", required=True)
    args = ap.parse_args()

    extracts, verifies = load_journal(args.journal)
    manifest = json.loads(
        (lib880.ROOT / "workspace/.build/sections/manifest.json").read_text(encoding="utf-8"))
    meta = {m["id"]: m for m in manifest}

    questions = []
    missing = 0
    verify_issues = 0
    skipped = []
    for sid, m in meta.items():
        ex = extracts.get(sid)
        if not ex:
            skipped.append(sid)
            continue
        qs = ex["questions"]
        # 题号连续校验
        nums = [q.get("q_num") for q in qs]
        if nums != list(range(1, len(qs) + 1)):
            print(f"!! {sid} 题号不连续: {nums}")
        vf = verifies.get(sid)
        if vf and vf.get("verdict") == "needs_review":
            verify_issues += 1
            print(f"!! {sid} 校验需复查: {[i.get('description') for i in vf.get('issues', [])]}")
        for q in qs:
            flags = q.get("flags", [])
            text = Q_MARK_RE.sub("", q.get("text", "")).strip()
            answer = (q.get("answer") or "").strip()
            solution = (q.get("solution") or "").strip()
            is_missing = ("answer_missing" in flags) or (not answer and not solution)
            if is_missing:
                missing += 1
            questions.append({
                "id": lib880.qid(m["chapter_no"], _diff_key(m["difficulty"]), _type_key(m["type"]), q["q_num"]),
                "subject": lib880.load_schema()["subject"],
                "chapter_no": m["chapter_no"],
                "chapter_title": m["chapter_title"],
                "difficulty": _diff_key(m["difficulty"]),
                "difficulty_zh": m["difficulty"],
                "type": _type_key(m["type"]),
                "type_zh": m["type"],
                "q_num": q["q_num"],
                "text": text,
                "answer": answer,
                "solution": solution,
                "answer_status": "missing" if is_missing else "ok",
                "flags": flags,
            })
    questions.sort(key=lambda q: (q["chapter_no"], _type_order(q["type"]), q["q_num"]))

    out = {
        "subject": lib880.load_schema()["subject"],
        "built_at": lib880.today_str(),
        "questions": questions,
        "stats": {
            "total": len(questions),
            "answer_missing": missing,
            "verify_needs_review": verify_issues,
            "sections_skipped": skipped,
        },
    }
    lib880.INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    lib880.INDEX_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"题目索引已生成：{lib880.INDEX_PATH}")
    print(f"总题数 {len(questions)} · 缺答案 {missing} · 校验需复查 {verify_issues}")
    if skipped:
        print(f"!! 未提取的节: {skipped}")


def _type_key(zh):
    return {"选择题": "choice", "填空题": "fill", "解答题": "solution"}[zh]


def _type_order(t):
    return {"choice": 0, "fill": 1, "solution": 2}[t]


def _diff_key(zh):
    return {"基础题": "basic", "综合题": "comprehensive", "拓展题": "extension"}[zh]


if __name__ == "__main__":
    main()
