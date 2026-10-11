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
import lint_content
import make_paper
import merge_extraction
import wrong_book
import zhenti_wrong_book


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

    def test_redo_state_demotes_mastered_on_failure(self):
        # 回炉做对 → 保持已掌握；做错 → 已掌握退回未复习
        self.assertEqual(lib880.redo_state("correct", "已掌握"), "已掌握")
        self.assertEqual(lib880.redo_state("wrong", "已掌握"), "未复习")
        self.assertEqual(lib880.redo_state("cannot", "已掌握"), "未复习")
        # 已在『已重做』的题不因再次做错而降级；未复习保持未复习
        self.assertEqual(lib880.redo_state("half", "已重做"), "已重做")
        self.assertEqual(lib880.redo_state("careless", "未复习"), "未复习")


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

    def test_lint_text_overrides_flags_unknown_qid_and_bad_math(self):
        """题干覆盖层校验：题号写错不会报渲染错误、只会静默不生效，必须拦住。

        覆盖层的键是 qid——拼错时 ``effective_text`` 取不到，产物照常生成但修正
        从未落地。与真题 ``stem``/``text`` 字段名漂移同一类空转，故 lint 要显式比对
        题库索引，而不是只把每条覆盖值过一遍公式判据。
        """
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            overrides_path = tmp / "records" / "text-overrides.json"
            overrides_path.parent.mkdir(parents=True)
            overrides_path.write_text(json.dumps(
                {"texts": {
                    "q-known": {"text": "正常题干 $x^2$"},
                    "q-typo": {"text": "题号写错的覆盖"},
                    "q-bad": {"text": "坏公式 \\(x\\) 行内定界符"},
                }}, ensure_ascii=False), encoding="utf-8")
            index_path = tmp / "question-index.json"
            index_path.write_text(json.dumps(
                {"questions": [{"id": "q-known"}]}, ensure_ascii=False), encoding="utf-8")
            with patch.multiple(
                lib880,
                ROOT=tmp,
                TEXT_OVERRIDES_PATH=overrides_path,
                INDEX_PATH=index_path,
                LINEAR_ALGEBRA_INDEX_PATH=tmp / "missing-la-index.json",
            ):
                rel, errors = lint_content.lint_text_overrides()
        self.assertTrue(any("q-typo" in e and "不会生效" in e for e in errors),
                        f"未拦下写错的题号：{errors}")
        self.assertTrue(any("q-bad" in e for e in errors), f"未拦下坏公式：{errors}")
        self.assertFalse(any("q-known" in e for e in errors), f"误报正常覆盖：{errors}")


class RenderLayerTest(unittest.TestCase):
    """渲染层归一（lib880）与产物侧 lint 判据的回归。

    三个缺陷来自 paper-06（用户报「渲染失败了」）：选项行的裸 ``<`` 让 Live Preview
    把整段当 HTML 块（选择题 4）、行内 ``$$…$$`` 撑破段落（解答题 4）、相对图片路径
    解析不到（选择题 6 的示意图）。事实源只读、原貌保留，修在渲染层，lint 只在产物侧
    拦残留——所以下面既测渲染层吸收，也测 lint 判据本身。
    """

    def test_escape_bare_angle_brackets_only_outside_math(self):
        # 裸 `<` 且同行无 `>` 收尾：Live Preview 会当 HTML 块起始，必须转义
        self.assertEqual(lib880.escape_bare_angle_brackets("A. M<N<P"),
                         r"A. M\<N\<P")
        # 行内公式、独立公式块、行内代码里的 `<` 是数学/代码内容，一律不动
        self.assertEqual(lib880.escape_bare_angle_brackets("设 $x<0$ 时"), "设 $x<0$ 时")
        self.assertEqual(lib880.escape_bare_angle_brackets("$$\nr(A)<n-1\n$$"),
                         "$$\nr(A)<n-1\n$$")
        self.assertEqual(lib880.escape_bare_angle_brackets("用 `a<b` 表示"), "用 `a<b` 表示")
        # 完整 HTML 标签不算「开不出的标签」；`&lt;` 不是本项目的正解（实时预览不解码实体）
        self.assertEqual(lib880.escape_bare_angle_brackets("<td>x</td>"), "<td>x</td>")

    def test_prepare_stem_text_escapes_bare_lt(self):
        stem = "**4.** 设 $f(x)$ 连续, 记 $M=\\int_{0}^{1}f\\mathrm{d}x$, 则 ( ).\n" \
               "A. M<N<P B. N<M<P C. P<M<N D. P<N<M"
        out = lib880.prepare_stem_text(stem)
        self.assertNotIn("<", out.replace(r"\<", ""))
        self.assertIn(r"M\<N\<P", out)

    def test_prepare_stem_text_demotes_inline_display_math(self):
        stem = ("**4.** 设 $$x _ {1} = \\frac {1}{2}$$ ，求 "
                "$$\\lim _ {n \\rightarrow \\infty} \\left(\\right).$$")
        out = lib880.prepare_stem_text(stem)
        self.assertNotIn("$$", out)
        self.assertIn("$x _ {1} = \\frac {1}{2}$", out)

    def test_prepare_stem_text_rewrites_relative_image_embed(self):
        out = lib880.prepare_stem_text("如图 ![](images/abc123.jpg) 所示")
        self.assertIn("![[abc123.jpg]]", out)
        self.assertNotIn("images/", out)

    def test_lint_predicates_flag_product_residue(self):
        self.assertEqual(lint_content.inline_dollar_lines("设 $$a$$ 求"), [1])
        self.assertEqual(lint_content.inline_dollar_lines("$$\nx\n$$"), [])
        # 整行公式 `$$x=1$$` 渲染正常，渲染层不降级，lint 也不得误报
        self.assertEqual(lint_content.inline_dollar_lines("$$x=1$$"), [])
        self.assertEqual(lint_content.bare_angle_lines("A. M<N<P"), [1])
        self.assertEqual(lint_content.bare_angle_lines(r"A. M\<N"), [])
        self.assertEqual(lint_content.relative_image_lines("![](images/a.jpg)"), [1])

    def test_source_image_wikilink_resolves(self):
        # 渲染层把图片改成 `![[<hash>.jpg]]`，解析根必须覆盖只读源里的图片，
        # 否则正确的写法会被 lint 误判成死链
        images = list((lib880.ROOT / "880").rglob("*.jpg"))
        if not images:
            self.skipTest("源题库图片未入库")
        self.assertTrue(lint_content._wikilink_resolves(images[0].name))


class MergeExtractionTest(unittest.TestCase):
    def test_literal_newlines_are_decoded_without_changing_latex_commands(self):
        extracted = r"前文\n$$\n\begin{array}{r l} x \neq 0 \n故\n$$"

        normalized = merge_extraction.decode_literal_newlines(extracted)

        self.assertEqual(normalized, "前文\n$$\n\\begin{array}{r l} x \\neq 0 \n故\n$$")


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

    def test_rebuild_keeps_ticked_card_and_refreshes_answer_sheet_safely(self):
        """重建不能吃掉待判勾选；答案卷按题级标题重刷且保留创建日。"""
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            schema_path = tmp / "schema.yaml"
            index_path = tmp / "question-index.json"
            attempts_path = tmp / "records" / "attempts.json"
            papers_path = tmp / "records" / "papers.json"
            papers_dir = tmp / "papers"
            overrides_path = tmp / "records" / "solution-overrides.json"
            schema_path.write_text((ROOT / "workspace/schema.yaml").read_text(encoding="utf-8"), encoding="utf-8")
            index_path.write_text((ROOT / "workspace/question-index.json").read_text(encoding="utf-8"), encoding="utf-8")
            attempts_path.parent.mkdir(parents=True)
            attempts_path.write_text(json.dumps({"attempts": [], "wrong_book_status": {}}), encoding="utf-8")
            papers_path.write_text(json.dumps({"papers": []}), encoding="utf-8")
            overrides_path.write_text(json.dumps({"solutions": {}}, ensure_ascii=False), encoding="utf-8")

            with patch.multiple(
                lib880,
                SCHEMA_PATH=schema_path,
                INDEX_PATH=index_path,
                ATTEMPTS_PATH=attempts_path,
                PAPERS_PATH=papers_path,
                PAPERS_DIR=papers_dir,
                SOLUTION_OVERRIDES_PATH=overrides_path,
                WRONG_BOOK_PATH=tmp / "wrong-book" / "错题本.md",
                PROGRESS_PATH=tmp / "preview" / "进度总览.md",
            ):
                with patch.object(sys, "argv", ["make_paper.py", "--n", "1", "--seed", "7"]):
                    make_paper.main()
                card_path = papers_dir / "paper-01" / "判分卡-01.md"
                answer_path = papers_dir / "paper-01" / "卷子-01-答案.md"

                # 用户勾了一道题，随后（未判分状态下）重建
                ticked = card_path.read_text(encoding="utf-8").replace("- [ ] 对", "- [x] 对", 1)
                card_path.write_text(ticked, encoding="utf-8")
                with patch.object(sys, "argv", ["make_paper.py", "--rebuild", "paper-01"]):
                    make_paper.main()
                self.assertEqual(card_path.read_text(encoding="utf-8"), ticked)
                # 显式 --rebuild-card 才允许清空勾选
                with patch.object(sys, "argv",
                                  ["make_paper.py", "--rebuild", "paper-01", "--rebuild-card"]):
                    make_paper.main()
                self.assertNotIn("- [x]", card_path.read_text(encoding="utf-8"))

                # 答案卷：每题一个题级标题，题干题号保留
                answer = answer_path.read_text(encoding="utf-8")
                self.assertIn("### 第 1 题", answer)
                self.assertIn("**1.** ", answer)
                self.assertIn("### 第 6 题", answer)

            # 解析覆盖层改动 → --rebuild-answers 重刷：保留创建日，自定义解析降级到 ####
                qid = json.loads(papers_path.read_text(encoding="utf-8"))["papers"][0]["questions"][0]["qid"]
                lines = answer_path.read_text(encoding="utf-8").splitlines()
                for i, line in enumerate(lines[:10]):
                    if line.startswith("date: "):
                        lines[i] = "date: 2026-01-02"
                    elif line.startswith("updated: "):
                        lines[i] = "updated: 2026-01-02"
                answer_path.write_text("\n".join(lines), encoding="utf-8")

                card_before = card_path.read_text(encoding="utf-8")
                with patch.object(sys, "argv", ["make_paper.py", "--rebuild-answers", "paper-01"]):
                    make_paper.main()
                # 内容未变则不写盘，updated 不空转；判分卡不被碰
                unchanged = answer_path.read_text(encoding="utf-8")
                self.assertIn("date: 2026-01-02", unchanged)
                self.assertIn("updated: 2026-01-02", unchanged)
                self.assertEqual(card_path.read_text(encoding="utf-8"), card_before)

                overrides_path.write_text(json.dumps(
                    {"solutions": {qid: {"solution": "### 思路\n\n换元后用等价无穷小定阶。"}}},
                    ensure_ascii=False), encoding="utf-8")
                with patch.object(sys, "argv", ["make_paper.py", "--rebuild-answers", "paper-01"]):
                    make_paper.main()
                refreshed = answer_path.read_text(encoding="utf-8")
                self.assertIn("date: 2026-01-02", refreshed)
                self.assertIn(f"updated: {lib880.today_str()}", refreshed)
                self.assertIn("#### 思路", refreshed)
                self.assertEqual(card_path.read_text(encoding="utf-8"), card_before)

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

    def test_text_override_replaces_stem_in_paper_and_answers(self):
        """题干覆盖层：卷子与答案卷都改用修正后的题干；未启用时回退原文。

        覆盖层修正的是做题本 OCR 的重复错误（如
        ``gs-c02-comprehensive-choice-024``），索引与原文源保持不变，所以只要卷子/
        答案卷/错题本任一处没接上覆盖层，重复题干就会漏出去。
        """
        plan = {
            "choice": [{"id": "q-1", "text": "原文题干（含重复）。重复了一遍。", "answer": "A"}],
            "fill": [],
            "solution": [],
        }
        schema = lib880.load_schema()
        with tempfile.TemporaryDirectory() as directory:
            overrides_path = Path(directory) / "records" / "text-overrides.json"
            with patch.object(lib880, "TEXT_OVERRIDES_PATH", overrides_path):
                # 文件不存在：功能未启用，忠实回退索引原文
                paper = make_paper.render_paper(
                    lib880.SUBJECT_HIGH_MATH, schema, "paper-01", plan, {})
                self.assertIn("原文题干", paper)
                overrides_path.parent.mkdir(parents=True)
                overrides_path.write_text(json.dumps(
                    {"texts": {"q-1": {"text": "修正后的题干"}}}, ensure_ascii=False),
                    encoding="utf-8")
                paper = make_paper.render_paper(
                    lib880.SUBJECT_HIGH_MATH, schema, "paper-01", plan, {})
                answers = make_paper.render_answers(
                    lib880.SUBJECT_HIGH_MATH, schema, "paper-01", plan)
        for rendered in (paper, answers):
            self.assertIn("修正后的题干", rendered)
            self.assertNotIn("原文题干", rendered)

    def test_text_override_accepts_bare_string_value(self):
        with tempfile.TemporaryDirectory() as directory:
            overrides_path = Path(directory) / "text-overrides.json"
            overrides_path.write_text(json.dumps({"texts": {"q-1": "纯字符串题干"}},
                                                 ensure_ascii=False), encoding="utf-8")
            with patch.object(lib880, "TEXT_OVERRIDES_PATH", overrides_path):
                self.assertEqual(lib880.effective_text({"id": "q-1", "text": "原文"}), "纯字符串题干")
                # 未覆盖的题仍取索引原文
                self.assertEqual(lib880.effective_text({"id": "q-2", "text": "原文"}), "原文")


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

    def test_due_rows_filters_by_age_and_membership(self):
        index = {"by_id": {
            "old": {"id": "old", "chapter_no": 3, "type": "choice", "difficulty": "basic", "q_num": 1},
            "fresh": {"id": "fresh", "chapter_no": 3, "type": "choice", "difficulty": "basic", "q_num": 2},
        }}
        attempts = {"wrong_book_status": {
            "old": {"state": "已掌握", "updated": "2026-08-01"},      # 满 30 天
            "fresh": {"state": "已掌握", "updated": "2026-10-04"},    # 未满
            "not-mastered": {"state": "未复习", "updated": "2026-08-01"},
            "other-subject": {"state": "已掌握", "updated": "2026-08-01"},  # 不在本索引
        }}
        today = date(2026, 10, 5)
        rows = wrong_book.due_rows(index, attempts, days=30, today=today)
        self.assertEqual([r["q"]["id"] for r in rows], ["old"])
        # days=0 列出全部已掌握（仍只认本索引内的题）
        all_rows = wrong_book.due_rows(index, attempts, days=0, today=today)
        self.assertEqual(sorted(r["q"]["id"] for r in all_rows), ["fresh", "old"])

    def test_all_regenerates_both_subjects_but_subject_stays_scoped(self):
        """写入模式下 --all 必须重刷两科，--subject 只重刷该科。

        2026-10-11：`--all` 曾只作用于 --check/--due，写入路径仍是单科，导致线代
        错题本静默停在旧版本（生成器换了、盘面没跟上）。这里锁死两条语义。
        """
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            gm_wrong = tmp / "wrong-book" / "错题本.md"
            la_wrong = tmp / "wrong-book" / "线代错题本.md"
            attempts_path = tmp / "records" / "attempts.json"
            attempts_path.parent.mkdir(parents=True)
            attempts_path.write_text(
                json.dumps({"attempts": [], "wrong_book_status": {}}), encoding="utf-8")
            (tmp / "schema.yaml").write_text(
                (ROOT / "workspace/schema.yaml").read_text(encoding="utf-8"), encoding="utf-8")
            (tmp / "question-index.json").write_text(
                (ROOT / "workspace/question-index.json").read_text(encoding="utf-8"),
                encoding="utf-8")
            (tmp / "la-schema.yaml").write_text(
                (ROOT / "workspace/linear-algebra-schema.yaml").read_text(encoding="utf-8"),
                encoding="utf-8")
            (tmp / "la-question-index.json").write_text(
                (ROOT / "workspace/linear-algebra-question-index.json").read_text(encoding="utf-8"),
                encoding="utf-8")

            with patch.multiple(
                lib880,
                SCHEMA_PATH=tmp / "schema.yaml",
                INDEX_PATH=tmp / "question-index.json",
                LINEAR_ALGEBRA_SCHEMA_PATH=tmp / "la-schema.yaml",
                LINEAR_ALGEBRA_INDEX_PATH=tmp / "la-question-index.json",
                ATTEMPTS_PATH=attempts_path,
                WRONG_BOOK_PATH=gm_wrong,
                LINEAR_ALGEBRA_WRONG_BOOK_PATH=la_wrong,
                EXTERNAL_LINKS_PATH=tmp / "records" / "external-links.json",
                ANALYSIS_PATH=tmp / "records" / "analysis.json",
                SOLUTION_OVERRIDES_PATH=tmp / "records" / "solution-overrides.json",
                TEXT_OVERRIDES_PATH=tmp / "records" / "text-overrides.json",
            ):
                # 全量：--all 一口气重刷两科（旧实现只刷默认科目，这条会红）
                with patch.object(sys, "argv", ["wrong_book.py", "--all"]):
                    wrong_book.main()
                self.assertTrue(gm_wrong.exists())
                self.assertTrue(la_wrong.exists(), "--all 必须覆盖两科")

                # 单科：--subject 只重刷该科，不碰其它
                gm_wrong.unlink()
                with patch.object(sys, "argv",
                                  ["wrong_book.py", "--subject", "linear-algebra"]):
                    wrong_book.main()
                self.assertTrue(la_wrong.exists())
                self.assertFalse(gm_wrong.exists(), "--subject 不应动其它科目")


class ZhentiWrongBookTest(unittest.TestCase):
    """真题覆盖表的状态派生（回归：整卷聚合，不是首条记录说了算）。"""

    MODULES = {"高数": ["微分方程", "高数-一元函数积分学"], "线代": []}

    def _doc(self, coverage=None, attempts=True):
        problems = {
            # ★ 本题故意排在本卷最前且**没有** attempts：旧实现逐条 setdefault 时
            # 由它定整卷状态，会把整卷误锁成「未做」。
            "zt-2010-数二-选择1": {
                "module": "微分方程", "year": 2010, "paper": "数二", "no": "选择1",
                "stem": "题", "answer": "A", "solution": "解",
            },
            "zt-2010-数二-解答18": {
                "module": "高数-一元函数积分学", "year": 2010, "paper": "数二", "no": "解答18",
                "stem": "题", "answer": "A", "solution": "解",
            },
        }
        if attempts:
            problems["zt-2010-数二-解答18"]["attempts"] = [
                {"date": "2026-09-20", "grade": "wrong"}]
        return {"problems": problems, "coverage": coverage or {}}

    def _coverage_row(self, doc):
        text = zhenti_wrong_book.render(lib880.load_schema(), doc, self.MODULES)
        return [ln for ln in text.splitlines()
                if ln.startswith("| 2010-数二 |")][0]

    def test_coverage_status_aggregates_over_whole_paper(self):
        # 本卷 2 题中 1 题有作答 → 整卷「做过」；若某卷全无作答仍为「未做」。
        self.assertIn("| 做过 | 2 |", self._coverage_row(self._doc()))
        self.assertIn("| 未做 | 2 |", self._coverage_row(self._doc(attempts=False)))

    def test_explicit_coverage_beats_derived_status(self):
        doc = self._doc(coverage={"2010-数二": {"status": "已复盘", "note": "整卷过完"}})
        row = self._coverage_row(doc)
        self.assertIn("| 已复盘 |", row)
        self.assertIn("整卷过完", row)

    def test_due_problems_selects_mastered_by_age(self):
        doc = {"problems": {
            "zt-a": {"review_state": "已掌握", "review_updated": "2026-08-01",
                     "year": 2010, "paper": "数二", "no": "解答18"},
            "zt-b": {"review_state": "已掌握", "review_updated": "2026-10-04",
                     "year": 2011, "paper": "数二", "no": "选择1"},
            "zt-c": {"review_state": "未复习", "review_updated": "2026-08-01",
                     "year": 2012, "paper": "数二", "no": "解答19"},
            "zt-d": {"review_state": "已掌握", "year": 2013, "paper": "数二", "no": "解答20"},
        }}
        today = date(2026, 10, 5)
        rows = zhenti_wrong_book.due_problems(doc, days=30, today=today)
        self.assertEqual([r["id"] for r in rows], ["zt-a"])
        # days=0 列出全部已掌握（缺 review_updated 的按今天算，不计为到期）
        all_rows = zhenti_wrong_book.due_problems(doc, days=0, today=today)
        self.assertEqual(sorted(r["id"] for r in all_rows), ["zt-a", "zt-b", "zt-d"])


if __name__ == "__main__":
    unittest.main()
