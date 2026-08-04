#!/usr/bin/env python3
"""grade.py — 判分（五态：对/错/不会/半会/粗心），更新判分记录并重生成错题本与进度。

用法：
  python3 scripts/grade.py --paper paper-01 \
      --grading '{"choice":{"1":"不会","2":"对"},"fill":{"3":"半会"},"solution":{"1":"不会"}}'
  python3 scripts/grade.py --paper paper-01 --grading '{"choice":{"1":"cannot"}}' --note "看了解析才懂"

grading 中 key 为题型内题号（1 起），value 为中文或英文判分态。
可加 --redo：表示这是错题重练（若判为『对』则复习状态置为已掌握，否则保持未复习）。
"""

import argparse
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", required=True)
    ap.add_argument("--grading", required=True, help="JSON：题型→{题号:判分}")
    ap.add_argument("--note", default="")
    ap.add_argument("--redo", action="store_true", help="错题重练模式")
    args = ap.parse_args()

    import json
    try:
        grading = json.loads(args.grading)
    except json.JSONDecodeError:
        print(f"!! --grading 不是合法 JSON: {args.grading}", file=sys.stderr)
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
    added = 0
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
            attempts["attempts"].append({
                "qid": qid,
                "paper_id": args.paper,
                "grade": grade_key,
                "when": today,
                "note": args.note,
            })
            # 复习状态联动
            if args.redo:
                prev = attempts["wrong_book_status"].get(qid, {}).get("state")
                new_state = "已掌握" if grade_key == "correct" else ("未复习" if prev != "已重做" else prev)
                attempts["wrong_book_status"][qid] = {"state": new_state, "updated": today}
            elif grade_key in set(schema["wrong_book"]["focus_grades"]):
                if qid not in attempts["wrong_book_status"]:
                    attempts["wrong_book_status"][qid] = {"state": "未复习", "updated": today}
            added += 1

    lib880.save_attempts(attempts)
    paper["status"] = "graded"
    lib880.save_papers(papers)

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
