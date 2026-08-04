# Obsidian 内容规范

---
paths:
  - ".codebuddy/rules/common/obsidian-content.md"
---

本规则规范本仓库内 **agent 生成的所有 Markdown 内容**：既包括 880 习题系统的产物（卷子、答案卷、错题本、进度总览），也包括以后生成的文档、ADR、笔记、报告。目标：内容 **Obsidian 原生**（属性、标签、wikilink、callout 全部有效），机器可校验、人工可浏览。

## 适用范围

- 适用：agent 通过脚本或直接写入仓库的任何 `.md` 文件。
- 不适用：`880/` 下的原始题库文件（做题本/解析册，只读源，不改）；`question-index.json`、`attempts.json`、`papers.json` 等机器数据（非浏览内容）。

## 通用规范（所有生成内容）

### 1. YAML frontmatter 必填

每个生成文件头部必须有 `---` 包裹的 YAML 属性：

```yaml
---
type: <枚举值>
date: 2026-08-04        # 创建日，ISO YYYY-MM-DD
updated: 2026-08-04     # 最近更新日，ISO YYYY-MM-DD
tags: [高数, 880, <分类>]
---
```

- `type` 枚举：`卷子` / `答案卷` / `错题本` / `进度总览` / `文档` / `记录`。
- `tags` 用数组（Obsidian 属性格式），至少含项目标签与分类标签。
- 创建与更新同日时两者都写；只读/一次性内容可省略 `updated`。

### 2. 日期

- 一律 ISO `YYYY-MM-DD`（如 `2026-08-04`），不用 `2026/08/04` 或 `08-04`。

### 3. 链接

- 站内引用一律 `[[wikilink]]`；Obsidian 自动跟踪重命名。
- 带显示文本：`[[卷子-01|第 1 套]]`。
- 仅外部 URL 用 `[text](https://...)`。

### 4. 高亮用 callout

```markdown
> [!info] 卷头
> 内容……

> [!warning] 注意
> 内容……

> [!tip] 技巧
> 内容……
```

### 5. 表格与公式

- 只用 Markdown 表格（`| a | b |`），禁止 HTML `<table>`。
- 数学公式用 LaTeX：行内 `$...$`、独立 `$$...$$`；禁止转成 HTML 或图片。

### 6. 标题层级

- `#` 文档标题（每文件仅一个）→ `##` 章节 → `###` 小节 → `####` 条目，禁止跳级。

### 7. 文件命名

- 小写短横线或中文语义名；880 产物按 `卷子-01.md`、`错题本.md`、`进度总览.md` 约定。

---

## 880 产物规范

### 统一基线

```yaml
type: <卷子|答案卷|错题本|进度总览>
date: 2026-08-04
updated: 2026-08-04
tags: [高数, 880, <卷子|答案|错题|进度>]
```

### 卷子（`workspace/papers/卷子-01.md`）

frontmatter：

```yaml
type: 卷子
paper_id: paper-01
paper_no: "01"          # 补零，引号包裹防被当数字
date: 2026-08-04
updated: 2026-08-04
subject: 高数
duration_minutes: 180
total_score: 150
status: created          # created | graded
tags: [高数, 880, 卷子]
aliases: [第 1 套]
```

结构（顺序固定）：

1. `# 880 高数模拟卷 · 第 01 套`
2. `> [!info] 卷头`（满分/限时/构成）
3. `## 一、选择题` / `## 二、填空题` / `## 三、解答题`
4. `## 答题卡`（Markdown 表格）
5. `## 判分表`（Markdown 表格，判分态 对/错/不会/半会/粗心）
6. `## 关联`：

```markdown
## 关联

- 答案：[[卷子-01-答案]]
- 错题本：[[错题本]]
- 进度：[[进度总览]]
```

判分后由判分流程将 `status` 更新为 `graded`。

### 答案卷（`workspace/papers/卷子-01-答案.md`）

frontmatter：

```yaml
type: 答案卷
paper_id: paper-01
date: 2026-08-04
updated: 2026-08-04
subject: 高数
tags: [高数, 880, 答案]
```

结构：

1. `# 卷子-01 答案与解析`
2. 卷头 callout（含 `对应卷子：[[卷子-01]]`）
3. `## 一、选择题` / `## 二、填空题` / `## 三、解答题`（每题：答案加粗 + 解析）
4. `## 关联`：`- 对应卷子：[[卷子-01]]`

### 错题本（`workspace/wrong-book/错题本.md`）

frontmatter：

```yaml
type: 错题本
updated: 2026-08-04
tags: [高数, 880, 错题本]
total: 12            # 错题总数
focus_count: 7       # 重点（不会/半会）
mastered_count: 0    # 已掌握
```

结构：

1. `# 880 错题本`
2. 摘要行（含重点/已掌握计数）
3. `## 第X章 …`（每章一节）
   - 章节索引表（`# | 题型 | 难度 | 判分 | 优先级 | 复习状态`）
   - `### 题目与解析`
   - `#### 第X章 选择题 第N题 · 判分：xx · 优先级：xx · 状态：xx`
     - `**题干：**` + `**答案：**` + `**解析：**` + `*来源卷子：[[卷子-XX]]*`
4. `## 关联`：`- 进度：[[进度总览]]`

### 进度总览（`workspace/preview/进度总览.md`）

frontmatter：

```yaml
type: 进度总览
updated: 2026-08-04
tags: [高数, 880, 进度]
total: 618
graded: 22
pending: 0
undone: 596
wrong: 12
```

结构：

1. `# 880 进度总览`
2. `## 汇总`（Markdown 表格：总题数/已判/欠账/未做/非对）
3. `## 章节弱点排行`（Markdown 表格）
4. `## 章节进度`（每章一个 `### 第X章 …（n/m 题）`，表格：`# | 题型 | 难度 | 状态`）
5. `## 关联`：`- 错题本：[[错题本]]` + 已有卷子链接列表

---

## 校验与落地

- 生成产物的脚本（`scripts/make_paper.py`、`wrong_book.py`、`progress.py`）按本规范输出。
- 修改产物格式时：先改本规则，再同步改脚本与对应 skill（`880-paper`/`880-grade`/`880-wrongbook`/`880-progress`）。
- 可选用 `scripts/lint_content.py` 校验生成文件是否符合本规范（键齐全、wikilink 指向存在）。
