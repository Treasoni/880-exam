# 铁律

从 `LEARNINGS.md` 和 `ERRORS.md` 提炼出的最高优先级规则。

---

_最后更新：2026-09-02_

## 880 产物格式

- **答案卷补充同步错题本源**：对已在错题本中的题目补充解析时，不能只改答案卷；同步更新错题本事实源（如 `workspace/question-index.json` 或 `workspace/records/*.json`）并重跑 `python3 scripts/wrong_book.py`，最后核验错题本对应条目。

- **格式修改链路**：改 880 产物格式必须先改 `.claude/rules/common/obsidian-content.md`，再同步 `scripts/` 生成脚本与对应 skill（880-paper / 880-grade / 880-wrongbook / 880-progress），最后重建受影响产物。
- **重建不换题**：重建已有卷子的产物（如答案卷）时，从 `workspace/records/papers.json` 读取同一批题目重建，禁止重新抽题覆盖用户正在做的卷子。
- **重建入口 --rebuild**：重建已有卷产物用 `python3 scripts/make_paper.py --rebuild <paper_id>`（从 papers.json 读同一批题；判分卡总是重建，卷子/答案仅在未判分时重建）。
- **答案卷内容**：答案卷每题包含「题目原文 + 答案 + 解析」（用户明确偏好，以后生成卷子都这样）。
- **答案卷唯一锚点**：编辑重复题号的答案卷时，用章节标题加完整题干定位，并在写入前后断言匹配唯一；禁止只用 `**N.**` 作为边界。
- **解析换行归一化**：合并结构化提取结果时，将不属于 LaTeX 命令的字面量 `\\n` 解码为真实换行；禁止全局替换，以免破坏 `\\neq` 等命令。
- **Obsidian 公式定界符**：独立 LaTeX 公式统一使用 `$$...$$`；修改后检查定界符成对，并按用户选中的完整区域核验渲染格式。
- **判分卡勾选**：判分卡状态用任务清单复选框（`- [ ] 对` 等，阅读视图可点击），不用表格内 `[ ]`；每题只勾一个状态，多勾判分报错（用户明确偏好，以后都这样）。
- **可点击勾选用任务清单**：Obsidian 需要点击切换的复选框必须写 `- [ ]` 列表项；Markdown 表格里的 `[ ]` 在阅读视图不可点击。
- **已掌握题归档保留**：错题重做正确后，状态设为「已掌握」并保留在错题本末尾归档；不得因最近判分为「对」而删除或隐藏该条记录。

## Obsidian 双链

- **跨库引用用 symlink**：wikilink 只在本 vault 内解析；引用外部库笔记时，把外部目录 symlink 进 vault（如 `external-notes/`，加入 .gitignore），再用真实 `[[external-notes/…]]`。
- **生成产物不手改**：会被脚本重建的产物（错题本等），映射/配置存 `workspace/records/*.json`，由脚本渲染，禁止手改产物。
- **wikilink 锚点先校验**：生成带 `#锚点` 的 wikilink 前，程序化确认锚点与目标文件标题精确一致（全角标点、空格都要对）。
- **映射先盘点源容量**：做「题目→外部资源」映射/关联时，先统计源库存量与主题覆盖，再决定一对一或一对多结构，避免「每题只配一条」覆盖不足。
- **lint 校验路径型 wikilink**：校验 wikilink 时，裸名按 workspace 文件 stem 匹配；路径型 `[[a/b#锚点]]` 先拆 `#锚点`、按 vault 根补 `.md` 后 `Path.exists()` 判定（跟随 `external-notes/` symlink）。

## 工作流状态机

- **状态模板带机器 token**：`.claude/workflows/*/state-template.md` 每行阶段必须带 `{not_started}`/`{in_progress}`/`{complete}`/`{skipped}` token（如 `> [P0] ⬜ 未开始 {not_started} — 入库`）；todo-state.sh 的判据全按行尾 token 匹配，模板缺 token 会导致 `{complete}` 字面量泄漏、状态机跳档。

## 工作流

- **任务收尾做 digest**：用户要求每次任务后按 `/digest` 做自我学习，沉淀真实学习点与错误（以后都这样）。
