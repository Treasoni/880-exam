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
import lib880
import make_paper


class Lib880Test(unittest.TestCase):
    def setUp(self):
        self.schema = lib880.load_schema()

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


if __name__ == "__main__":
    unittest.main()
