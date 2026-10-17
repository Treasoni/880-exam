# 学习心得

---

_最后更新：2026-10-17_

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

## 2026-10-17

### 两个索引的题目主键字段名不同：高数用 `qid`、线代用 `id`

**类别**：knowledge_gap
**优先级**：medium
**状态**：pending
**范围**：数据模型 / `workspace/question-index.json`、`workspace/linear-algebra-question-index.json`、`workspace/records/papers.json`

**摘要**：高数索引 `question-index.json` 的题目主键字段是 `qid`，线代索引 `linear-algebra-question-index.json` 的同一字段叫 `id`；`papers.json` 的 `questions[].qid` 两科同名。按 `qid` 去线代索引里查题会**静默返回 0 条**（每条都没有 `qid` 字段），容易被误判成「题库里没有这道题」。

**详情**：
- 事实：`question-index.json` 每条 = `{qid, subject, chapter, ..., text, answer, solution}`（`subject: 高数`，618 条）；`linear-algebra-question-index.json` 每条 = `{id, subject, chapter_no, chapter_title, difficulty, type, q_num, text, answer, solution, ...}`（`subject: 线性代数`，311 条）。
- 根因：两科索引由不同构建脚本产出，字段命名未统一；只有 `papers.json` 的记录层用了统一的 `qid` 键，遮蔽了下游索引层的分叉。
- 连带事实：渲染层 `lib880.effective_solution` / `effective_text` 取的是 `q.get("id")`——说明流进生成器的题目对象来自**线代索引**那种 `id` 形态；查高数题时若也按 `id` 取则会取空。
- 下次做法：查题目条目先按科目选索引——高数 `question-index.json` 匹配 `qid`，线代 `linear-algebra-question-index.json` 匹配 `id`；拿不准就用 `papers.json` 的 `paper_no → qid` 反查（见 RULES「取事实源条目从卷面反查」）确认字段名，再回索引取 `text`/`answer`/`solution`。

### 列表项里的公式用行内 `$...$`，别用独立 `$$...$$`

**类别**：best_practice
**优先级**：medium
**状态**：pending
**范围**：880 产物渲染 / `lib880` 准备函数 / 答案卷·错题本·解析

**摘要**：在 Markdown 列表项（`- …`）里写公式要用行内 `$...$`；一旦在列表项之后顶格写独立公式 `$$...$$`，**列表会被终止**——该 `$$` 块与后续段落从列表里“掉出来”，后面的条目重新开一个新 `<ul>`。

**详情**：
- 事实（vault 实测，`MarkdownRenderer` oracle）：输入 `- A：… \n\n$$\n…\n$$\n\n又 …\n\n- B：…`，渲染结果的顶层子节点是 `UL` → `DIV`（公式块）→ `P` → `UL`：列表被切成两段，`li` 里 `display=true` 的容器数为 0。
- 根因：块级元素（顶格 `$$`）会关闭当前列表上下文；即便前后都有空行（满足「块级元素要留空行」的既有规则）也照样断列表——空行规则解决的是“渲染失败”，这条解决的是“结构被切碎”。
- 下次做法：列表项内需要公式时一律用行内 `$...$`；确需独立公式块，就把该点从列表里拿出来、写成独立段落（或整段改成纯正文 + 加粗标签，不用列表）。

---

## 历史记录

旧记录已归档至 `.learnings/archive/`：`LEARNINGS-2026-08-11-pre-digest.md`、`LEARNINGS-2026-08-12-pre-compress.md`、`LEARNINGS-2026-09-13-pre-compress.md`（2026-09-03 / 09-09 / 09-11 / 09-13）、`LEARNINGS-2026-09-15-pre-compress.md`、`LEARNINGS-2026-09-15-pre-digest.md`（两条 best_practice 内核已进 RULES）；`880-wrongbook` 公式渲染防线 3 条（2026-09-12 / 09-13）见 `.learnings/archive/2026-09-13-maintenance.md`；09-24 归档的两条（用户供稿先验算、公共前缀/后缀定位，内核均已进 RULES）见 `.learnings/archive/2026-09-24-maintenance.md`。

2026-10-11 的三条 best_practice（**Obsidian 渲染层事实**、**渲染验证三件套**、**归一化覆盖同族输出点**）内核均已进 `RULES.md`（「公式定界符只认 Obsidian 原生两种」「callout 内的独立公式也算独立块」「渲染判定用 oracle，不用截图反推」「归一化要覆盖同族全部输出点」），归档至 `.learnings/archive/2026-10-11-maintenance.md`。
