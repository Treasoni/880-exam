# 2026-10-19 维护归档

本次维护对象：2026-10-17 的 3 条 LEARNINGS 记录（索引主键字段、列表项公式、覆盖层重刷）。

审计结论：活跃 `ERRORS.md` 无待观察记录；`LEARNINGS.md` 剩 2 条数学知识缺口（数列极限根式差、二次型正交变换），不属于流程缺陷，继续保留。3 条流程类记录的内核均已进 `RULES.md`，本次逐条核对后归档；其中「索引主键」一条与当前事实源不符，先纠正规则再归档。

---

## 1. LEARNINGS：题目主键字段名按层分（原记录有误，已纠正）

**原记录摘要**：旧笔记称高数索引 `question-index.json` 用 `qid`、线代索引 `linear-algebra-question-index.json` 用 `id`，`papers.json` 用 `qid`。

**核实结果**：旧笔记的后半段正确，前半段**错误**——两个索引的题目主键字段当前**都是 `id`**，没有任何 `qid` 字段。实际契约：
- `workspace/question-index.json`：618 条，主键 `id`；
- `workspace/linear-algebra-question-index.json`：311 条，主键 `id`；
- `workspace/records/papers.json`：`questions[].qid`，值为索引里的 `id`（`make_paper.py` 写入 `{"qid": q["id"]}`）；
- `workspace/records/zhenti-problems.json`：`problems` 为以 `zt-…` 为键的对象，记录内题干字段叫 `stem`（不是 `text`）。

**修复路径**：
- `RULES.md`「事实源主键字段按层分」改写为上述实际契约，并删去「高数用 qid」的错误说法。
- 新增回归测试 `tests/test_core.py::FactSourceKeyFieldTest::test_fact_source_key_fields` 与 `test_zhenti_problems_use_stem_not_text`，锁死索引、卷子记录、真题记录的字段名。

**验证方式**：
- 正样本：`python3 -m unittest tests.test_core.FactSourceKeyFieldTest -v` → `Ran 2 tests ... OK`。
- 负样本：把索引样本改成 `{"questions":[{"qid":"…"}]}` 后同一判据返回 `False`，确认错误字段名会被拦下。
- `grep` 确认 `.learnings/` 之外没有「高数索引用 qid」的残留引用。

**处理结果**：已归档（含纠错）。旧笔记按错字段名查会静默返回 0 条，现已由规则 + 测试双重兜底。

---

## 2. LEARNINGS：列表项里的公式用行内 `$...$`

**原记录摘要**：Markdown 列表项（`- …`）里写独立 `$$…$$` 会关闭列表上下文，把公式块和后续段落切出列表，后面条目另起 `<ul>`；列表项内一律用行内 `$...$`。

**修复路径**：`RULES.md`「列表项里用行内公式」已写明禁用场景与替代写法；该结论来自 vault 实测（`MarkdownRenderer` oracle），不是原理推导。

**验证方式**：
- 用脚本扫描 `workspace/wrong-book/真题错题本.md`（本次 linked content）：列表项后紧跟独立 `$$` 块 0 处，盘面无该缺陷。
- 规则条目与 `obsidian-content.md` 的块级空行/公式章节不冲突：行内 `$...$` 不受块级空行规则影响。

**处理结果**：已归档。维持规则层约束；生成器无需自动降级——该写法需按意图判断，规则比正则更可靠。

---

## 3. LEARNINGS：改覆盖层要重刷所有含该题的卷子

**原记录摘要**：同一 qid 可能被多张卷子抽中；只刷「手头这张」会漏掉其余卷子，它们的答案卷仍是旧解析。

**修复路径**：
- `RULES.md`「改覆盖层要重刷所有含该题的卷子」：先用 `papers.json` 反查该 qid 的全部 `paper_id`，再逐张 `--rebuild-answers <paper_id>`（或直接 `--rebuild-answers all`）。
- `.claude/skills/880-paper/SKILL.md` 已把 `--rebuild-answers all` 写成固定动作，并区分题干覆盖（还需逐卷 `--rebuild`）与解析覆盖。

**验证方式**：
- `grep` 确认 `make_paper.py --rebuild-answers` 支持 `PAPER_ID|all`，`all` 分支遍历全部卷子记录。
- `papers.json` 当前 11 张卷、每题均以 `qid` 引用索引，可按 `qid` 反查全部命中卷。

**处理结果**：已归档。规则 + skill 步骤 + `all` 入口构成可执行机制。

---

## 本次未处理项

- 真题错题本 `zhenti-problems.json` 有 5 条记录（`zt-2010-数二-解答17`～`解答21`）没有记录内 `id` 字段，仅靠 `problems` 的字典键标识；当前无代码读取 `p["id"]`（`problem_key` 未被调用），不构成活跃缺陷。回归测试按「`id` 可省略、以字典键为准」断言，未改用户数据。
- 历史 hotspot（`880-wrongbook` 16 条、`interaction` 15 条、`markdown` 30 条）均为已归档记录，活跃侧无复发，不再重复开单。
