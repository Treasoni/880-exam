# 学习心得

---

_最后更新：2026-10-11_

## 当前可复用学习

### 数列极限中的根式差

**类别**：knowledge_gap
**优先级**：medium
**状态**：pending
**范围**：高数 / 数列极限

**摘要**：把 $(n+1)^{1/n}-n^{1/(n+1)}$ 写成 $e^{A_n}-e^{B_n}$，用指数函数中值定理拆成 $e^{\xi_n}(A_n-B_n)$，再分别求阶。

---

## 2026-09-15

### 二次型正交变换：两次对角化的特征值顺序要对齐，`Q` 不唯一

**类别**：knowledge_gap
**优先级**：medium
**状态**：pending
**范围**：线代 / 二次型（`la-c12-comprehensive-solution-011`）

**摘要**：求使 $Q^{\mathsf T}AQ=B$ 的正交阵 $Q$，做法是分别正交对角化：$Q_1^{\mathsf T}AQ_1=\Lambda_1$、$Q_2^{\mathsf T}BQ_2=\Lambda_2$，**只有 $\Lambda_1=\Lambda_2$（两边的列按特征值一一对齐）**才有 $Q=Q_1Q_2^{\mathsf T}$ 满足 $Q^{\mathsf T}AQ=B$（$Q$ 正交）。同组特征向量可换序换号，所以 $Q$ 不唯一。

**详情**：
- 本题 $A=[[1,0,0],[0,2,1],[0,1,2]]$、$B=[[2,0,-1],[0,1,0],[-1,0,2]]$，特征值都是 $1,1,3$。
- 取 $Q_1$ 的列 = $A$ 的 $\lambda=1$ 特征向量 $(1,0,0),(0,1,-1)$ 与 $\lambda=3$ 的 $(0,1,1)$，$Q_2$ 的列 = $B$ 的 $\lambda=1$ 的 $(0,1,0),(1,0,1)$ 与 $\lambda=3$ 的 $(-1,0,1)$，得 $Q=Q_1Q_2^{\mathsf T}=[[0,1,0],[1,0,0],[0,0,-1]]$——按题中 $f$ 与 $g$ 的系数核验 $Q^{\mathsf T}AQ$ 严格等于 $B$，$Q$ 正交。
- 答案卷给的 $[[0,1,0],[0,0,1],[-1,0,0]]$ 满足同一等式，是同一批列的另一种排列，两者都对：**别把答案卷的列序当唯一标准**。

**下次做法**：自检用 $Q^{\mathsf T}AQ=B$（等价 $AQ=QB$）加 $Q^{\mathsf T}Q=I$，不要与答案卷逐元素比对；写 $Q_1$、$Q_2$ 时每列旁边标清对应的特征值，顺序不一致就算错。

---

## 2026-10-11

### Obsidian 渲染层事实：行内 `$$` 的降级边界、裸 `<` 的转义形式

**类别**：best_practice
**优先级**：high
**状态**：pending
**范围**：880 渲染层（`scripts/lib880.py`）/ `.claude/rules/common/obsidian-content.md`

**摘要**：两条「Obsidian 会怎么渲」的实测事实，替代了此前的原理推导：①行内 `$$…$$` **只有当同行另有正文时**才撑破段落（降级为 `$…$`），**整行** `$$x=1$$` 与**独占一行的引用块** `> $$…$$` 是合法独立公式块，不得降级；②公式区外的裸 `<` 用反斜杠转义 `\<`，**不能用 HTML 实体 `&lt;`**。

**详情**：
- **行内 `$$` 边界**：夹在句中的 `$$…$$` 渲成 `display:block` 数学块，把所在段落撑破（「设 $$f$$，求 $$g$$」裂成四段）。判据是「该行除 `$$…$$` 外是否还有别的正文」——`lib880.normalize_math_delimiters` 只降级「同行另有正文」的 `$$…$$`，整行公式保留。**误判代价**：`lint` 判据若写「含 `$$` 即残留」，会把合法整行公式（含用户手写内容）判成错，按此「修」等于改坏用户排版。
- **裸 `<` 的转义形式**：`<` 紧跟 ASCII 字母/`/`、同行无 `>` 收尾时，Live Preview 当成 HTML 标签/块起点，从该行起到文末整段裸露成原始 Markdown。minimal-repro 实测：`A. M&lt;N&lt;P` 正文里仍是**字面 `&lt;`**（预览不解码实体），而 `A. M\<N\<P` 正常渲成 `M<N<P` 且后续不再裸露。故正确写法是 `\<`。

**下次做法**：任何「Obsidian 会怎么渲 X」的结论，先写最小复现文件在**实时预览**里实测（`dev:dom` / 截图）再落进规则、生成器或判据；原理推导、别处经验、摘要转述都不算。生成器侧归一函数就用 `lib880` 的 `normalize_math_delimiters` / `escape_bare_angle_brackets`，判据与渲染共用一份。

---

### 验证「Obsidian 会怎么渲染」的三件套

**类别**：best_practice
**优先级**：high
**状态**：pending
**范围**：Obsidian 操作 / 880 渲染层验证

**摘要**：不用截图也能**精确**判定渲染结果——`require("obsidian").MarkdownRenderer.render(app, md, el, "", component)` 把一段 markdown 渲成 HTML，读 `el.innerHTML` 即可断言（`mjx-container[display=true]` = 独立公式块、`math-inline` = 行内）。要验**实时预览**则必须**先显式**把 leaf 设成实时预览：`view.setState({mode:"source", source:false})`。

**详情**：
- `obsidian vault="880-exam" eval code='(async () => { const {MarkdownRenderer} = require("obsidian"); const el = document.createElement("div"); await MarkdownRenderer.render(app, "> [!info] A\n> $$x=1$$", el, "", null); return el.innerHTML; })()'` —— `require("obsidian")` 在 eval 里可用（`MarkdownRenderer` / `renderMath` 等都在），`return` 必须包在 IIFE 里（裸 `return` 报 `Illegal return statement`）。
- 这条 oracle 直接判定「`> $$…$$` 在 callout 里是不是独立公式块」，比截图快、比原理推导可信；本次就是靠它确认了保留 `> $$…$$` 的决定，再用实时预览截图复核。
- **陷阱**：`view.getMode()` 返回 `"source"` 对「源码模式」和「实时预览」**都成立**（实时预览也是 source，只是 `source:false`）。拿它当「我截的是实时预览」的凭据会得出错误结论（本次差点把源码模式的截图当成「渲染失败」）。截图前一律 `setState({mode:"source", source:false})`。
- 截图还有个坑：`dev:screenshot path=` 是**输出**文件路径（不是要截的笔记），写错会覆盖源文件。

**下次做法**：判定渲染优先用 `MarkdownRenderer` oracle（可断言 HTML 结构）；要人眼看实时预览时，先 `setState({mode:"source", source:false})` 再 `dev:screenshot path=<输出.png>`，输出路径一律指到 `workspace/` 之外的 `/tmp`。

---

### 渲染层归一化：覆盖同族全部输出点，别只改被点名那一处

**类别**：best_practice
**优先级**：high
**状态**：pending
**范围**：880 渲染层（`scripts/wrong_book.py` 等）

**摘要**：给一类文本（题干 / 答案 / 解析）加写入前归一时，必须 `grep` 出**该字段的全部拼接位置**一次改全。同一产物常有多条渲染路径（错题本的「待复习」与「已掌握归档」就是两条），只改一条会留下同源缺陷和口径分叉。

**详情**：
- 本次实例：`wrong_book.py` 的**已掌握归档**条目题干走 `prepare_stem_text(effective_text(q, text_overrides))`（裸 `<` 转义、行内 `$$` 降级、字面 `\n` 解码、图片 wikilink 改写、题干覆盖生效），而**待复习**条目仍拼 `{q['text']}` 原文。后果有两层：①同一问在不同状态下渲染口径不同；②待复习条目的 `text-overrides` 覆盖被静默忽略（而规则文档说覆盖对错题本生效）。
- **当时 lint 全绿**，因为这个漏洞是**潜在**的——要等某道待复习题的题干真的含 `<` / `$$` / 字面 `\n` 才显形。量过：全库 929 题里 36 题题干会被归一改动，其中在错题本内的 4 题**全在已掌握归档**（那条路径本就归了），所以待复习路径暂时没暴露。
- 判据：`grep -n "q\['text'\]\|q\[\"text\"\]" scripts/*.py` 列出全部输出点，逐个确认走的是同一层准备函数。

**下次做法**：加/改渲染层准备函数（`prepare_stem_text` / `prepare_solution_text` / `prepare_inline_text`）时，先 `grep` 字段名找齐所有拼接点；两条同类路径必须共用同一调用，禁止一处归一、一处原文。

---

## 历史记录
旧记录已归档至 `.learnings/archive/`：`LEARNINGS-2026-08-11-pre-digest.md`、`LEARNINGS-2026-08-12-pre-compress.md`、`LEARNINGS-2026-09-13-pre-compress.md`（2026-09-03 / 09-09 / 09-11 / 09-13）、`LEARNINGS-2026-09-15-pre-compress.md`、`LEARNINGS-2026-09-15-pre-digest.md`（两条 best_practice 内核已进 RULES）；`880-wrongbook` 公式渲染防线 3 条（2026-09-12 / 09-13）见 `.learnings/archive/2026-09-13-maintenance.md`；09-24 归档的两条（用户供稿先验算、公共前缀/后缀定位，内核均已进 RULES）见 `.learnings/archive/2026-09-24-maintenance.md`。
