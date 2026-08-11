# 学习心得

---

_最后更新：2026-08-11_

## 2026-08-11

### 880 产物格式变更必须走完整生成链路

**类别**：best_practice
**优先级**：high
**状态**：pending
**范围**：880-paper / 880-wrongbook / scripts / docs

**摘要**：答案卷、判分卡、错题本等 880 生成产物不能只改单个 Markdown；应修改事实源/生成脚本/规则/skill，再重建受影响产物。

**详情**：
- 事实：此前沉淀了答案卷需包含题目原文、判分卡用 Obsidian 可点击任务清单、错题本由数据文件与脚本渲染、功能变更同步用户指南等经验。
- 根因：880 产物是 generated artifacts，单独改某个输出文件容易在下一次重建时丢失，或导致答案卷/错题本/索引之间不一致。
- 下次做法：涉及 880 产物内容或格式时，先判断事实源（如 `workspace/question-index.json`、`workspace/records/*.json`、脚本模板），再同步规则/skill/docs，最后运行对应重建脚本并核验输出。

---

### Obsidian wikilink 与外部错题关联要程序化校验

**类别**：best_practice
**优先级**：medium
**状态**：pending
**范围**：Obsidian / wrong_book.py / lint_content.py

**摘要**：跨库关联通过 symlink 进入 vault 后再写路径型 wikilink；路径与锚点必须由脚本校验，lint 也要区分裸名和路径型链接。

**详情**：
- 事实：外部错题本关联从一对一扩展到一对多，并修正了 lint 对 `[[external-notes/...#锚点]]` 的误报。
- 根因：Obsidian 只解析 vault 内链接，锚点精确匹配；手写路径、锚点或只按 stem 校验都容易断链/误报。
- 下次做法：生成外部关联前先盘点源容量，使用 `qid → [links]` 数组；链接生成后读取目标文件确认标题锚点存在；lint 路径型 wikilink 时拆 `#锚点` 并按 vault 根 `Path.exists()` 判断。

---

### 工作流状态模板与状态机脚本必须端到端验证

**类别**：correction
**优先级**：medium
**状态**：pending
**范围**：workflow-todo-state / todo-state.sh

**摘要**：工作流模板阶段行必须带机器 token，并用空状态文件重放 start→complete 全链路，避免状态机跳档或泄漏字面 token。

**详情**：
- 事实：模板缺 `{not_started}` 时，`todo-state.sh` 曾把 `{complete}` 字面量写进行内并导致阶段判据失效。
- 根因：脚本按行尾机器 token 匹配阶段状态，模板与脚本约定不一致。
- 下次做法：修改工作流模板或脚本后，必须用全新状态文件跑完整生命周期验证。

---

### 答案卷解析补充要同步错题本事实源

**类别**：correction
**优先级**：high
**状态**：pending
**范围**：880-wrongbook / question-index / answer notes

**摘要**：用户要求补充答案卷中“积分中值定理”说明后，又指出错题本没有同步；正确做法是把解析补充写入错题本的事实源并重生成错题本。

**详情**：
- 事实：我先只补充了 `workspace/papers/paper-01/卷子-01-答案.md`，随后用户提醒“错题本那里不加？”。修复时将同样内容写入 `workspace/question-index.json` 对应题目解析，并运行 `python3 scripts/wrong_book.py`，错题本才同步出现 callout。
- 根因：错题本不是从答案卷实时读取，而是由 `workspace/question-index.json` 与判分记录生成；只改答案卷不会传播到错题本。
- 下次做法：用户要求“补充解析/笔记且该题在错题本中”时，同步更新 `question-index` 中该题解析或其他脚本事实源，再重生成错题本；交付前 grep 核验错题本对应题目确实包含新增内容。

---
