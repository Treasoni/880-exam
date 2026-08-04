# 生成内容采用 Obsidian 原生规范

本仓库 agent 生成的所有 Markdown（880 产物的卷子/答案卷/错题本/进度总览，以及文档、ADR、笔记）遵循 `.claude/rules/common/obsidian-content.md`：统一 YAML frontmatter（type/date/updated/tags）、站内 `[[wikilink]]`、`> [!callout]` 高亮、Markdown 表格、LaTeX 公式。880 各产物另有专属属性与固定结构（见规则文件）。

**Why**：ADR-0002 已确定 Obsidian 是本系统的查看层。生成内容若不统一为 Obsidian 原生，用户无法在 Obsidian 里按属性过滤、按标签浏览、用图视图看到卷子↔答案卷↔错题本↔进度之间的链接。规则文件是"格式即契约"：脚本、skill、人工生成都遵守同一份 schema，lint 可校验。

**Consequences**：修改产物格式必须先改规则文件，再同步改 `scripts/` 与对应 skill；`scripts/lint_content.py` 可校验产物是否符合规范。Obsidian Bases（`.base` 数据库视图）留作后续增强，暂不纳入。
