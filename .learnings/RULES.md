# 铁律

从 `LEARNINGS.md` 和 `ERRORS.md` 提炼出的最高优先级规则。

---

_最后更新：2026-09-15_

## 880 产物格式

- **答案卷补充同步错题本源**：对已在错题本中的题目补充解析时，不能只改答案卷；同步更新错题本事实源（如 `workspace/question-index.json` 或 `workspace/records/*.json`）并重跑 `python3 scripts/wrong_book.py`，最后核验错题本对应条目。

- **格式修改链路**：改 880 产物格式必须先改 `.claude/rules/common/obsidian-content.md`，再同步 `scripts/` 生成脚本与对应 skill（880-paper / 880-grade / 880-wrongbook / 880-progress），最后重建受影响产物。
- **重建不换题**：重建已有卷子的产物（如答案卷）时，从 `workspace/records/papers.json` 读取同一批题目重建，禁止重新抽题覆盖用户正在做的卷子。
- **重建入口 --rebuild**：重建已有卷产物用 `python3 scripts/make_paper.py --rebuild <paper_id>`（从 papers.json 读同一批题；判分卡总是重建，卷子/答案仅在未判分时重建）。
- **重建保护用户状态**：`--rebuild` 会清空判分卡未判勾选、重置 frontmatter `date`、并按索引原文重渲染答案卷；重建前先提交/备份受影响卷目录，重建后逐项核验（判分卡勾选、其它题解析、`date`），发现被回退立即 `git checkout HEAD --` 还原。**勾选数与其它卷面状态一律以重建前的工作区实测为准**（`grep -c '\[x\]'`），不要沿用记忆或上一轮的数字——用户可能在两次重建之间继续做题。
- **答案卷改动先写事实源**：答案卷任何解析改动必须先写入 `workspace/question-index.json` 的 `solution`，再 `--rebuild`；禁止只改答案卷（否则下次重建即丢失）。
- **答案卷内容**：答案卷每题包含「题目原文 + 答案 + 解析」（用户明确偏好，以后生成卷子都这样）。
- **答案卷唯一锚点**：编辑重复题号的答案卷时，用章节标题加完整题干定位，并在写入前后断言匹配唯一；禁止只用 `**N.**` 作为边界。
- **解析换行归一化**：合并结构化提取结果时，将不属于 LaTeX 命令的字面量 `\\n` 解码为真实换行；禁止全局替换，以免破坏 `\\neq` 等命令。
- **Obsidian 公式定界符**：独立 LaTeX 公式（包括复习消息）统一使用 `$$...$$`；修改后检查定界符成对，并按用户选中的完整区域核验渲染格式。
- **Obsidian 公式块结构校验**：仅统计 `$$` 成对不够；必须运行 `scripts/lint_content.py`，确认公式块未吞入 Markdown 题号/标题，且没有控制字符或错位定界符。
- **脚本写入 LaTeX**：生成 JSON/Markdown 解析时使用 raw 字符串或显式转义反斜杠；写入后检查不存在控制字符（尤其 `\x0c`），并核验渲染结果。
- **生成前置校验**：`wrong_book.py` 写入前拒绝控制字符、独立式 `\[...\]` 与转义形式，并把行内 `\(...\)` 归一为 `$...$`；重建后必须运行 `python3 scripts/lint_content.py`（**先校验事实源**两个索引的 `text`/`answer`/`solution`，再校验产物——源头坏了重建后必然流回产物）。
- **公式定界符只认 Obsidian 原生两种**：行内 `$...$`、独立 `$$...$$`；禁止 `\(...\)` / `\[...\]`——Obsidian 不渲染，会以原文裸露。源文本不改，由渲染层 `lib880.normalize_math_delimiters` 归一，lint 双重拦截；`\\[2pt]` 这类 LaTeX 换行不是定界符，勿误报。
- **坏内容判据单一出处**：一类产物的校验正则/常量只放在 `scripts/lib880.py`，渲染层与 `lint_content.py` 都引用它；修「某种写法漏检」时把同族形式一次列全，禁止在多个文件各存一份正则。
- **判分卡勾选**：判分卡状态用任务清单复选框（`- [ ] 对` 等，阅读视图可点击），不用表格内 `[ ]`；每题只勾一个状态，多勾判分报错（用户明确偏好，以后都这样）。
- **可点击勾选用任务清单**：Obsidian 需要点击切换的复选框必须写 `- [ ]` 列表项；Markdown 表格里的 `[ ]` 在阅读视图不可点击。
- **已掌握题归档保留**：错题重做正确后，状态设为「已掌握」并保留在错题本末尾归档；不得因最近判分为「对」而删除或隐藏该条记录。
- **复用文本标题降级**：把带标题的源文本（解析等）拼进嵌套型产物（错题本条目 `####`/`#####`）时，渲染层自动把最浅标题降到条目标题之下（待复习→内容 `#####`、已掌握→内容 `######`，更深保持相对层级、封顶 `######`）；源文本保留原层级，禁止把 `###` 原样嵌进 `####` 条目破坏大纲。
- **陈旧产物要重刷**：生成器的写入前校验只管**新写入**，不会重写已落盘的旧产物——盘面上的坏渲染会一直躺在用户打开的文件里。用 `python3 scripts/wrong_book.py --check --all` 检测盘面是否已跟上事实源（陈旧则退出码 1 并给 diff）；修完事实源后对**整个**事实源重跑生成器并 `python3 scripts/lint_content.py` 到全绿，禁止只重建被点名的那几条；用户报渲染问题时按「`git show HEAD:<产物>` 看盘面 → 查事实源 → 查生成器」三层一起查。
- **补公式定界符必须回对源**：`$$` 计数是否成对**不能**决定补头还是补尾（两种都只把计数变偶）；补哪一侧、补什么前缀（如被剥掉的 `\begin{array}{r l} & {`）一律回对只读源 `880/` 定夺。解码字面 `\n` 只用 `lib880.decode_literal_newlines`，禁止 `str.replace("\\n", "\n")`（会砍断 `\neq` / `\nearrow` / `\nRightarrow`）。

## 改动核验

- **聚合事实源用结构化比对**：改 `workspace/question-index.json` 这类聚合 JSON 后，核验要按 `id` 逐条比对每个字段，断言「变更条目集合」与「每条变更字段集合」都与本次意图一一对应；`git diff` 行数、行 diff、`--stat` 都不作为判据（pretty-print 会把一处变长放大成全文件错位，且 HEAD 基线混带他人未提交改动）。写入前先做 round-trip（读入 → 原样 `json.dumps(ensure_ascii=False, indent=2) + "\n"` → 与源比对）确认零差异；写回也必须补末尾换行（`json.dumps` 不输出，会制造 `No newline at end of file` 假 diff）。
- **自检判据不得与被检内容共用字符集**：`git diff | grep -c "No newline at end of file"` 恒不为 0——经验库自己的正文里就写着这个字面串（`RULES.md`/`ERRORS.md` 一改，计数就 +n），这条判据是永久假阳性。改为锚定行首 `git diff | grep -c '^\ No newline at end of file'`，并优先用 `git diff -- <本次文件>` 收窄范围；同理 `grep -v` 裁 diff 前先自问「被裁的行会不会以同样字符开头」。
- **结论只从未过滤的原始输出得出**：`git diff` 的结论必须以未过滤输出为准，`grep -v` 只用于展示。`^[+-][+-]` 这类「滤文件头」模式会连同 `-- [ ] 错` / `+- [x] 错` 等真实变更行一起滤掉（变更行 = 标记 + 原文，原文首字符可能就是 `-`/`+`），静默造成「diff 为空」的误判；确需滤头用 `grep -v '^\(+++\|---\) '`。
- **核验脚本锚定期望集合**：切块/分组的核验必须先跟**事实源期望集合**比对（答案卷题块 ↔ `papers.json` 的 `paper_no`），不能只报「两版有无差异」——切块本身出错时「无差异」会伪装成「文件没被改动」。答案卷分块与判据只用 `lib880.split_answer_sheet` / `answer_sheet_key_errors`（`lint_content.py` 已接入），禁止在核验脚本里另写一份分块正则。
- **新校验判据要喂负样本**：新增/修改校验判据后，构造一个必然违规的样本确认它真会报错（本次：截掉第 6 题的答案卷），只跑正样本绿不算验证。
- **用户供稿先验算再写入**：用户贴来的解析里，**反例、构造、特例、推导链**当草稿逐条对题设验算（反例要与全部已知条件对表），只有格式与措辞照排；发现数学错误就换合法构造，并在回复里说明改了哪里、为什么——不静默照抄，也不静默改掉。
- **取事实源条目从卷面反查**：拿某道题的 qid / answer 一律由 `workspace/records/papers.json` 的 `paper_no → qid` 映射反查得到，禁止凭对同卷其他题的印象硬编码题号。查错对象会产出一个「格式正确、结论错误」的信号，并伪装成「事实源与产物不一致」——本次硬编码 `…choice-003` 取回一道多元函数题，答案对不上，差点按不一致立案。
- **用库函数前先读它的契约**：调 `lib880` 的解析函数时按函数**真实契约**写探针——`split_answer_sheet` 的题块**不含** `**N.** …` 题干行（块从题干下一行开始）。探针报异常先怀疑探针、回读函数源码，不要直接立案查文件缺陷。
- **断言冲突前先读对方盘面值**：报「A 与 B 不一致」之前必须读 B 的实际字段（如 `attempts.json` 里该 `paper_id` 的记录条数、卷子的 `status`）。转述、上下文摘要、上一轮结论都**不算**事实——本次那个「`attempts.json` 记为对」来自摘录转述，实查 paper-04 记录 0 条、`status: created`，冲突根本不存在。
- **单块改动用公共前缀/后缀定位**：证明「只改了目标块」算**公共前缀行数 + 公共后缀行数**（本次 357 / 322，改动区间 = 新 358..444 / 旧 358..358），断言改动区间 ⊆ 目标块行范围；边界由算法计算，禁止手写行号（本次手写 0-based 边界造出过一次「后段一致: False」的假警报）。行 diff 不作判据。
- **EOF 换行与中文路径核验**：判「文件末尾是否有换行」用 `git show HEAD:<f> | tail -c 1 | xxd -p` 与 `tail -c 1 <f> | xxd -p` 比对（`0a` = 有）；`git diff --name-only` 对非 ASCII 路径会加引号转义，`for f in $(git diff --name-only)` 会拿到带引号的假路径（`tail` 报 No such file），脚本里改用 `git config core.quotePath false` 或 pathspec 直接逐个点名。

## 配图

- **配图走事实源，不手改产物**：880 题目的配图按 `draw-visual-explanation` 用 Python + matplotlib 画、存 `workspace/wrong-book/images/`，图片嵌入与配图说明写进 `workspace/question-index.json` 的 `solution`（`![[workspace/wrong-book/images/<名>.png]]` + 说明它支持哪个结论），再重跑生成器；禁止直接编辑错题本/答案卷。
- **标注放空白区 + 引线回指**：图上文字标注不要贴着目标点放（必被坐标轴/射线/边线穿过）；用 `annotate(xytext=空白区, xy=目标点, arrowprops=...)`，标注整体落在图上留白处。
- **出图两步验收**：整图看布局；再对每处标注区域 2× 放大裁切回看压字。只做前者会漏掉十几像素级压字——缩略图上「看着还行」不算过。

## Obsidian 双链

- **跨库引用用 symlink**：wikilink 只在本 vault 内解析；引用外部库笔记时，把外部目录 symlink 进 vault（如 `external-notes/`，加入 .gitignore），再用真实 `[[external-notes/…]]`。
- **生成产物不手改**：会被脚本重建的产物（错题本等），映射/配置存 `workspace/records/*.json`，由脚本渲染，禁止手改产物。
- **wikilink 锚点先校验**：生成带 `#锚点` 的 wikilink 前，程序化确认锚点与目标文件标题精确一致（全角标点、空格都要对）。
- **映射先盘点源容量**：做「题目→外部资源」映射/关联时，先统计源库存量与主题覆盖，再决定一对一或一对多结构，避免「每题只配一条」覆盖不足。
- **lint 校验路径型 wikilink**：校验 wikilink 时，裸名按 workspace 文件 stem 匹配；路径型 `[[a/b#锚点]]` 先拆 `#锚点`、按 vault 根补 `.md` 后 `Path.exists()` 判定（跟随 `external-notes/` symlink）。

## 工作流状态机

- **状态行 token 必须在行尾**：`.claude/workflows/*/state-template.md` 与 `workspace/workflow-runs/*.workflow.md` 的阶段行写作 `> [P0] ⬜ 未开始 {not_started}` —— token 就是行尾，**后面不能再挂标签**。todo-state.sh 的三条判据（`phase_has_status` / `previous_open_phase_before` / `next_pending_phase_after`）全按 `\{token\}$` 匹配：写成 `… {not_started} — 入库` 的行对状态机完全不可见，后果是前序阶段校验失效 + `complete`/`skip` 后 `next_pending_phase_after` 返回空、frontmatter 被提前置为 `done/complete`（跳档）。阶段含义写在 `workflow.md`，不要挂在状态行尾。
- **状态文件必须有异常记录表**：state-template 与运行文件都要有 `## 异常记录` 表头，缺表时 `todo-state.sh skip|block` 以 `exception table not found` 直接失败（连跳过阶段都做不到）。改完状态文件/模板跑 `.claude/scripts/check-workflow-state.sh`（校验行尾 token、异常表、frontmatter `current_phase`/`current_status`）。

## 工作流

- **任务收尾做 digest**：用户要求每次任务后按 `/digest` 做自我学习，沉淀真实学习点与错误（以后都这样）。
- **复发缺陷修三层**：修一类反复复发的缺陷，机制要同时盖住①源头校验（坏数据在校验点暴露）、②陈旧检测（存量产物不静默留坏）、③流程步骤（skill 固定动作）；只补一层下次仍复发，三层都绿才归档经验库记录。
