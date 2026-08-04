# 数据全部存于 880-exam 仓库，Obsidian 仅作查看层

所有系统数据与产物（题目索引、判分记录、卷子、错题本、进度总览）都存放在本仓库的 `workspace/` 下。生成文件采用 Obsidian 兼容的 Markdown（YAML frontmatter + wikilink），需要时可直接用 Obsidian 打开本仓库浏览。不向外部 vault（考研复习）写入。

**Why**：单一真源、可 git 版本化、无跨库写权限问题。用户有现成的考研复习 Obsidian 体系，但系统产物应自成一体，避免与手工精修笔记混杂。

**Consequences**：用户在工作流内对话式操作，所有状态由仓库内 JSON/Markdown 承载；Obsidian 只是阅读工具，不做回写。
