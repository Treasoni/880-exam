"""880 核心规则的回归测试；所有文件写入都限制在临时目录。"""

import copy
import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import grade
import build_linear_algebra_index
import lib880
import make_paper
import wrong_book


class Lib880Test(unittest.TestCase):
    def setUp(self):
        self.schema = lib880.load_schema()

    def test_markdown_math_answer_wraps_bare_latex_only(self):
        self.assertEqual(lib880.markdown_math_answer(r"\frac{1}{2}"), r"$\frac{1}{2}$")
        self.assertEqual(lib880.markdown_math_answer("$x^2$"), "$x^2$")
        self.assertEqual(lib880.markdown_math_answer("A"), "A")

    def test_weakness_respects_minimum_attempts(self):
        schema = copy.deepcopy(self.schema)
        schema["weakness"]["min_attempts"] = 2
        index = {
            "by_id": {
                "q-1": {"chapter_no": 1},
                "q-2": {"chapter_no": 1},
            }
        }
        attempts = {"attempts": [{"qid": "q-1", "grade": "cannot", "when": "2026-08-04"}]}
        self.assertEqual(lib880.chapter_weakness(schema, index, attempts, date(2026, 8, 4)), {})

        attempts["attempts"].append({"qid": "q-2", "grade": "correct", "when": "2026-08-04"})
        self.assertEqual(lib880.chapter_weakness(schema, index, attempts, date(2026, 8, 4)), {1: 0.5})

    def test_latest_attempt_uses_recorded_time_not_file_order(self):
        attempts = {
            "attempts": [
                {"qid": "q-1", "grade": "correct", "when": "2026-08-04", "recorded_at": "2026-08-04T20:00:00+08:00"},
                {"qid": "q-1", "grade": "cannot", "when": "2026-08-03", "recorded_at": "2026-08-03T20:00:00+08:00"},
            ]
        }
        self.assertEqual(lib880.latest_attempt("q-1", attempts)["grade"], "correct")

    def test_index_validation_detects_duplicate_id(self):
        index = {
            "questions": [
                {"id": "same", "chapter_no": 1, "difficulty": "basic", "type": "choice", "q_num": 1,
                 "text": "题目", "answer": "A", "solution": "解析", "answer_status": "ok"},
                {"id": "same", "chapter_no": 1, "difficulty": "basic", "type": "choice", "q_num": 2,
                 "text": "题目", "answer": "B", "solution": "解析", "answer_status": "ok"},
            ],
            "stats": {"total": 2, "verify_needs_review": 0},
        }
        errors = lib880.validate_index(self.schema, index)
        self.assertTrue(any("重复" in error for error in errors))


class LinearAlgebraIndexTest(unittest.TestCase):
    def test_inline_next_question_keeps_the_previous_options(self):
        second = "A. first B. second C. third D. fourth(2) 下一题"
        items = build_linear_algebra_index.slice_items(
            ["(1) 题干", second],
            [(0, 0, 1), (1, second.index("(2)"), 2)],
            section=build_linear_algebra_index.SectionKey(8, "综合题", "选择题"),
        )
        self.assertEqual(len(items), 2)
        self.assertIn("D. fourth", items[0][1])
        self.assertNotIn("(2)", items[0][1])


class PaperRulesTest(unittest.TestCase):
    def test_missing_answer_status_is_not_available_for_sampling(self):
        index = {
            "questions": [
                {"id": "ok", "chapter_no": 1, "type": "choice", "difficulty": "basic", "answer_status": "ok"},
                {"id": "missing", "chapter_no": 1, "type": "choice", "difficulty": "basic", "answer_status": "missing"},
            ]
        }
        self.assertEqual([q["id"] for q in make_paper.cell_pool(index, 1, "choice", "basic")], ["ok"])

    def test_partial_and_complete_paper_statuses(self):
        paper = {"paper_id": "paper-01", "questions": [{"qid": "q-1"}, {"qid": "q-2"}]}
        partial = {"attempts": [{"paper_id": "paper-01", "qid": "q-1"}]}
        complete = {"attempts": [{"paper_id": "paper-01", "qid": "q-1"}, {"paper_id": "paper-01", "qid": "q-2"}]}
        self.assertEqual(grade.paper_grade_status(paper, partial), "partially_graded")
        self.assertEqual(grade.paper_grade_status(paper, complete), "graded")

    def test_existing_paper_requires_explicit_safe_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            schema_path = tmp / "schema.yaml"
            index_path = tmp / "question-index.json"
            attempts_path = tmp / "records" / "attempts.json"
            papers_path = tmp / "records" / "papers.json"
            papers_dir = tmp / "papers"
            schema_path.write_text((ROOT / "workspace/schema.yaml").read_text(encoding="utf-8"), encoding="utf-8")
            index_path.write_text((ROOT / "workspace/question-index.json").read_text(encoding="utf-8"), encoding="utf-8")
            attempts_path.parent.mkdir(parents=True)
            attempts_path.write_text(json.dumps({"attempts": [], "wrong_book_status": {}}), encoding="utf-8")
            papers_path.write_text(json.dumps({"papers": []}), encoding="utf-8")

            with patch.multiple(
                lib880,
                SCHEMA_PATH=schema_path,
                INDEX_PATH=index_path,
                ATTEMPTS_PATH=attempts_path,
                PAPERS_PATH=papers_path,
                PAPERS_DIR=papers_dir,
                WRONG_BOOK_PATH=tmp / "wrong-book" / "错题本.md",
                PROGRESS_PATH=tmp / "preview" / "进度总览.md",
            ):
                with patch.object(sys, "argv", ["make_paper.py", "--n", "1", "--seed", "7"]):
                    make_paper.main()
                with patch.object(sys, "argv", ["make_paper.py", "--n", "1"]):
                    with contextlib.redirect_stderr(io.StringIO()):
                        with self.assertRaises(SystemExit) as raised:
                            make_paper.main()
                self.assertEqual(raised.exception.code, 2)
                with patch.object(sys, "argv", ["make_paper.py", "--n", "1", "--seed", "8", "--replace-ungraded"]):
                    make_paper.main()

            records = json.loads(papers_path.read_text(encoding="utf-8"))["papers"]
            self.assertEqual([p["paper_id"] for p in records], ["paper-01"])

    def test_linear_algebra_paper_is_subject_scoped_and_uses_distinct_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            schema_path = tmp / "schema.yaml"
            index_path = tmp / "question-index.json"
            la_schema_path = tmp / "linear-algebra-schema.yaml"
            la_index_path = tmp / "linear-algebra-question-index.json"
            attempts_path = tmp / "records" / "attempts.json"
            papers_path = tmp / "records" / "papers.json"
            papers_dir = tmp / "papers"
            schema_path.write_text((ROOT / "workspace/schema.yaml").read_text(encoding="utf-8"), encoding="utf-8")
            index_path.write_text((ROOT / "workspace/question-index.json").read_text(encoding="utf-8"), encoding="utf-8")
            la_schema_path.write_text((ROOT / "workspace/linear-algebra-schema.yaml").read_text(encoding="utf-8"), encoding="utf-8")
            la_index_path.write_text((ROOT / "workspace/linear-algebra-question-index.json").read_text(encoding="utf-8"), encoding="utf-8")
            attempts_path.parent.mkdir(parents=True)
            attempts_path.write_text(json.dumps({"attempts": [], "wrong_book_status": {}}), encoding="utf-8")
            papers_path.write_text(json.dumps({"papers": []}), encoding="utf-8")

            with patch.multiple(
                lib880,
                SCHEMA_PATH=schema_path,
                INDEX_PATH=index_path,
                LINEAR_ALGEBRA_SCHEMA_PATH=la_schema_path,
                LINEAR_ALGEBRA_INDEX_PATH=la_index_path,
                ATTEMPTS_PATH=attempts_path,
                PAPERS_PATH=papers_path,
                PAPERS_DIR=papers_dir,
                WRONG_BOOK_PATH=tmp / "wrong-book" / "错题本.md",
                PROGRESS_PATH=tmp / "preview" / "进度总览.md",
                LINEAR_ALGEBRA_WRONG_BOOK_PATH=tmp / "wrong-book" / "线代错题本.md",
                LINEAR_ALGEBRA_PROGRESS_PATH=tmp / "preview" / "线代进度总览.md",
            ):
                with patch.object(sys, "argv", [
                    "make_paper.py", "--subject", "linear-algebra", "--n", "1", "--seed", "7",
                ]):
                    make_paper.main()

            records = json.loads(papers_path.read_text(encoding="utf-8"))["papers"]
            self.assertEqual(len(records), 1)
            paper = records[0]
            self.assertEqual(paper["paper_id"], "la-paper-01")
            self.assertEqual(paper["subject_key"], "linear-algebra")
            self.assertEqual(paper["subject_code"], "la")
            self.assertEqual(len(paper["questions"]), 22)
            self.assertTrue(all(q["qid"].startswith("la-") for q in paper["questions"]))
            folder = papers_dir / "la-paper-01"
            self.assertTrue((folder / "线代卷子-01.md").exists())
            self.assertTrue((folder / "线代卷子-01-答案.md").exists())
            self.assertTrue((folder / "线代判分卡-01.md").exists())
            self.assertTrue((tmp / "wrong-book" / "线代错题本.md").exists())
            self.assertTrue((tmp / "preview" / "线代进度总览.md").exists())
            paper_text = (folder / "线代卷子-01.md").read_text(encoding="utf-8")
            progress_text = (tmp / "preview" / "线代进度总览.md").read_text(encoding="utf-8")
            wrong_book_text = (tmp / "wrong-book" / "线代错题本.md").read_text(encoding="utf-8")
            self.assertIn("[[线代错题本]]", paper_text)
            self.assertIn("[[线代进度总览]]", paper_text)
            self.assertIn("[[线代错题本]]", progress_text)
            self.assertIn("[[线代进度总览]]", wrong_book_text)

    def test_linear_algebra_card_is_graded_against_its_own_index(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            schema_path = tmp / "schema.yaml"
            index_path = tmp / "question-index.json"
            la_schema_path = tmp / "linear-algebra-schema.yaml"
            la_index_path = tmp / "linear-algebra-question-index.json"
            attempts_path = tmp / "records" / "attempts.json"
            papers_path = tmp / "records" / "papers.json"
            papers_dir = tmp / "papers"
            schema_path.write_text((ROOT / "workspace/schema.yaml").read_text(encoding="utf-8"), encoding="utf-8")
            index_path.write_text((ROOT / "workspace/question-index.json").read_text(encoding="utf-8"), encoding="utf-8")
            la_schema_path.write_text((ROOT / "workspace/linear-algebra-schema.yaml").read_text(encoding="utf-8"), encoding="utf-8")
            la_index_path.write_text((ROOT / "workspace/linear-algebra-question-index.json").read_text(encoding="utf-8"), encoding="utf-8")
            attempts_path.parent.mkdir(parents=True)
            attempts_path.write_text(json.dumps({"attempts": [], "wrong_book_status": {}}), encoding="utf-8")
            papers_path.write_text(json.dumps({"papers": []}), encoding="utf-8")

            patches = dict(
                SCHEMA_PATH=schema_path,
                INDEX_PATH=index_path,
                LINEAR_ALGEBRA_SCHEMA_PATH=la_schema_path,
                LINEAR_ALGEBRA_INDEX_PATH=la_index_path,
                ATTEMPTS_PATH=attempts_path,
                PAPERS_PATH=papers_path,
                PAPERS_DIR=papers_dir,
                WRONG_BOOK_PATH=tmp / "wrong-book" / "错题本.md",
                PROGRESS_PATH=tmp / "preview" / "进度总览.md",
                LINEAR_ALGEBRA_WRONG_BOOK_PATH=tmp / "wrong-book" / "线代错题本.md",
                LINEAR_ALGEBRA_PROGRESS_PATH=tmp / "preview" / "线代进度总览.md",
            )
            with patch.multiple(lib880, **patches):
                with patch.object(sys, "argv", [
                    "make_paper.py", "--subject", "linear-algebra", "--n", "1", "--seed", "7",
                ]):
                    make_paper.main()

                card_path = papers_dir / "la-paper-01" / "线代判分卡-01.md"
                card_path.write_text(
                    card_path.read_text(encoding="utf-8").replace("- [ ] 对", "- [x] 对", 1),
                    encoding="utf-8",
                )
                with patch("subprocess.run") as run:
                    with patch.object(sys, "argv", ["grade.py", "--sheet", str(card_path)]):
                        grade.main()
                self.assertEqual(run.call_count, 2)

            attempts = json.loads(attempts_path.read_text(encoding="utf-8"))["attempts"]
            self.assertEqual(len(attempts), 1)
            self.assertTrue(attempts[0]["qid"].startswith("la-"))
            self.assertEqual(attempts[0]["paper_id"], "la-paper-01")
            paper_text = (papers_dir / "la-paper-01" / "线代卷子-01.md").read_text(encoding="utf-8")
            self.assertIn("status: partially_graded", paper_text)


class ScoreAndAnalysisTest(unittest.TestCase):
    def setUp(self):
        self.schema = copy.deepcopy(lib880.load_schema())
        self.schema["paper"]["sections"]["solution"]["score_seq"] = [10, 12, 12, 12]

    def _paper(self):
        return {"paper_id": "paper-01", "questions": [
            {"qid": "q1", "section": "choice", "paper_no": "一1"},
            {"qid": "q2", "section": "solution", "paper_no": "三1"},
            {"qid": "q3", "section": "solution", "paper_no": "三2"},
        ]}

    def _attempts(self, grades):
        return {"attempts": [
            {"qid": q, "grade": g, "when": "2026-08-11",
             "recorded_at": f"2026-08-11T{i:02d}:00:00+08:00"}
            for i, (q, g) in enumerate(grades)
        ]}

    def test_question_full_score(self):
        self.assertEqual(lib880.question_full_score(self.schema, "choice", 1), 5)
        self.assertEqual(lib880.question_full_score(self.schema, "solution", 1), 10)
        self.assertEqual(lib880.question_full_score(self.schema, "solution", 2), 12)

    def test_score_ratios(self):
        index = {"by_id": {"q1": {"chapter_no": 1}, "q2": {"chapter_no": 3}, "q3": {"chapter_no": 3}}}
        paper = self._paper()
        attempts = self._attempts([("q1", "correct"), ("q2", "half"), ("q3", "wrong")])
        s = lib880.compute_paper_scores(self.schema, paper, attempts, index)
        self.assertEqual(s["total_earned"], 10)          # 5 + 10*0.5 + 0
        self.assertEqual(s["total_full"], 27)            # 5 + 10 + 12
        self.assertEqual(s["sections"]["solution"]["earned"], 5)
        self.assertEqual(s["sections"]["choice"]["earned"], 5)

    def test_render_score_weakness_has_score_and_weakness(self):
        index = {"by_id": {"q1": {"chapter_no": 1}, "q2": {"chapter_no": 3}, "q3": {"chapter_no": 3}}}
        paper = self._paper()
        attempts = self._attempts([("q1", "correct"), ("q2", "cannot"), ("q3", "half")])
        text = grade.render_score_weakness(self.schema, paper, attempts, index)
        self.assertIn("## 得分与弱点分析", text)
        self.assertIn("总分", text)
        self.assertIn("本卷弱点", text)
        self.assertIn("第三章", text)

    def test_analysis_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            fake = Path(td) / "analysis.json"
            with patch.object(lib880, "ANALYSIS_PATH", fake):
                lib880.save_analysis({"items": {"q1": {"cause": "计算/代数错误", "date": "2026-08-11"}}})
                data = lib880.load_analysis()
        self.assertEqual(data["items"]["q1"]["cause"], "计算/代数错误")


class WrongBookTest(unittest.TestCase):
    def test_mastered_redo_is_preserved_in_archive(self):
        schema = lib880.load_schema()
        index = {"questions": [
            {"id": "active", "chapter_no": 1, "type": "choice", "difficulty": "basic", "q_num": 1},
            {"id": "mastered", "chapter_no": 1, "type": "choice", "difficulty": "basic", "q_num": 2},
            {"id": "ordinary-correct", "chapter_no": 1, "type": "choice", "difficulty": "basic", "q_num": 3},
        ]}
        attempts = {"attempts": [
            {"qid": "active", "grade": "cannot", "when": "2026-08-11"},
            {"qid": "mastered", "grade": "cannot", "when": "2026-08-11"},
            {"qid": "mastered", "grade": "correct", "when": "2026-08-31"},
            {"qid": "ordinary-correct", "grade": "correct", "when": "2026-08-31"},
        ], "wrong_book_status": {"mastered": {"state": "已掌握", "updated": "2026-08-31"}}}

        active, mastered = wrong_book.build_wrong_lists(schema, index, attempts)

        self.assertEqual([e["q"]["id"] for e in active], ["active"])
        self.assertEqual([e["q"]["id"] for e in mastered], ["mastered"])


if __name__ == "__main__":
    unittest.main()
