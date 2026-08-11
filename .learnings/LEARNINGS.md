# 学习心得

---

_最后更新：2026-08-11_

## 2026-08-11

### 答案卷格式：题目原文 + 答案 + 解析

**类别**：correction | best_practice
**优先级**：medium
**状态**：pending
**范围**：880-paper / make_paper.py / obsidian-content.md

**摘要**：用户偏好答案卷每题带题目原文（「以后生成卷子都这样」），已走完整链路改规则+脚本+skill 并重建 paper-01 答案卷。

**详情**：
- 事实：答案卷原本每题只有「答案 + 解析」，对照题目要翻回卷子，不方便；用户要求把题目原文也放进答案卷。
- 根因：`render_answers()` 只输出 `q['answer']` 与 `q['solution']`，没输出 `q['text']`；`q['text']` 字段在索引里本来就存在（部分含换行，渲染时需按原样输出）。
- 下次做法：改 880 产物格式走「规则文件 → scripts 生成脚本 → 对应 skill → 重建产物」链路；重建已有卷产物时从 `papers.json` 读同一批题，不重新抽题，避免换掉用户正在做的卷子。

---

### 判分卡格式：任务清单复选框（可点击勾选）

**类别**：correction | best_practice
**优先级**：high
**状态**：pending
**范围**：880-paper / 880-grade / make_paper.py / grade.py / obsidian-content.md

**摘要**：判分卡状态从「表格 `[ ]`」改为「任务清单复选框」（`- [ ] 对` 等，阅读视图可点击），用户明确「以后都这样」；已走完整链路改规则+脚本+skill+重建 paper-01 判分卡，并给 `make_paper.py` 加了 `--rebuild` 重建入口。

**详情**：
- 事实：表格单元格里的 `[ ]` 在 Obsidian 阅读视图不可点击，只能在编辑视图手改 `x`；用户要求勾选形式方便改分。
- 根因：Obsidian 只对任务清单项（`- [ ]`）提供点击切换；表格内的 `[ ]` 是纯文本。
- 下次做法：需要点击勾选的 880 产物（如判分卡状态）一律用任务清单项；改格式走「规则文件 → 脚本 → skill → 重建产物」链路；重建已有卷产物用 `python3 scripts/make_paper.py --rebuild <paper_id>`（从 `papers.json` 读同一批题，判分卡总是重建，卷子/答案仅在未判分时重建）。

---

### 跨库双链：symlink 接入外部 vault，wikilink 才能跨库解析

**类别**：knowledge_gap | best_practice
**优先级**：high
**状态**：pending
**范围**：880-wrongbook / wrong_book.py / external-links.json / obsidian-content.md

**摘要**：把外部错题本（`/Users/zhqznc/Documents/考研复习/考研数学`，另一 vault）用 symlink 挂进 880 vault，再用真实 `[[wikilink#锚点]]` 关联同类型错题，无需手打外部链接。

**详情**：
- 事实：Obsidian 的 `[[…]]` 只在本 vault 索引内解析；跨 vault 笔记无法直接引用。
- 根因：vault 边界由 Obsidian 索引决定，其他库的笔记不在当前索引里。
- 下次做法：把外部目录 symlink 进 vault 根（`external-notes/考研数学 → 外部绝对路径`，加入 .gitignore），引用写 `[[external-notes/考研数学/…/错题本#锚点|显示名]]`；锚点必须是目标文件 `## 标题` 的精确文本（全角标点、`——`、空格都要一致），从源文件提取而非手打。

---

### 生成产物不手改：映射存数据文件，脚本渲染

**类别**：workflow | best_practice
**优先级**：high
**状态**：pending
**范围**：880-wrongbook / wrong_book.py / external-links.json

**摘要**：错题本每次判分会被 `wrong_book.py` 整体重建，手加的关联会被清掉；把「题目 → 外部错题」映射存 `workspace/records/external-links.json`，由脚本渲染 `*相关笔记：[[…]]*`。

**详情**：
- 事实：最初倾向直接编辑错题本加链接，但判分流程会重建整个错题本，手改必然丢失。
- 根因：产物是生成物（generated artifact），源是数据（attempts / index / mappings）；生成物不应成为唯一事实来源。
- 下次做法：凡是会被脚本重建的 880 产物，任何配置/映射都落到 `workspace/records/*.json`，脚本读数据渲染；用户以后新增关联只改 JSON 再重跑 `python3 scripts/wrong_book.py`。

---

### wikilink 锚点先校验：生成前逐条确认存在

**类别**：best_practice
**优先级**：medium
**状态**：pending
**范围**：通用 Obsidian 产物

**摘要**：给 12 条 `*相关笔记：[[…#锚点|…]]*` 全量回读目标文件验证锚点存在后再交付，杜绝断链。

**详情**：
- 事实：锚点文本含全角冒号、`——`、`（经典真题）` 等特殊字符，手打极易偏差；生成后不校验无法发现断链。
- 根因：Obsidian 锚点匹配要求与标题精确一致。
- 下次做法：批量生成带 `#锚点` 的 wikilink 后，写一次性校验脚本，对每条 link 读取目标 `.md` 确认 `## 锚点` 存在，全部通过才算完成。

---

### 任务收尾做 digest 自我学习（用户要求「以后都这样」）

**类别**：workflow
**优先级**：medium
**状态**：pending
**范围**：digest / 会话流程

**摘要**：用户明确要求每次任务后按 `/digest` 流程做自我学习，记录真实学习点与错误，以后都这样做。

**详情**：
- 事实：本会话完成跨库双链功能后，用户以「自我学习以后都这样」触发 digest。
- 根因：希望把每次改格式/脚本/规则的经验沉淀下来，避免重复踩坑。
- 下次做法：任务收尾（尤其涉及改 880 产物格式、脚本、规则、skill 时）主动走 digest：压缩阈值检查 → 回顾本次任务 → 写 LEARNINGS/ERRORS → 提炼 RULES → 验证无空条目。

---

### 外部错题关联：先盘点源容量，用一对多结构

**类别**：correction | best_practice
**优先级**：high
**状态**：pending
**范围**：880-wrongbook / external-links.json / wrong_book.py / obsidian-content.md

**摘要**：用户指出「能关联的就这几道吗？不应该吧？」——初始一对一映射覆盖不足；外部错题本实际有 316 条，扩展为每题 3–4 条、共 46 条后满足需求。

**详情**：
- 事实：外部错题本共 316 条（函数极限与连续 20 / 一元微分学 88 / 一元函数积分学 102 / 多元函数微分学 35 / 二重积分 18 / 数列极限 21 / 微分方程 32），我最初只给 12 道 880 错题各配了 1 条关联。
- 根因：设计映射时只求「每道错题找一条最像的」，没先盘点源库存量与主题覆盖，默认了一对一结构。
- 下次做法：做「题目→外部资源」映射/关联前，先统计源库存量与主题覆盖，判断能否/应该一对多；映射数据结构用 `qid → [多条]` 数组；锚点用 `^## {前缀}` 正则从源文件精确提取，并跳过含 `#` 的标题（会与 wikilink 锚点分隔符冲突）。

---

## 2026-08-11

### lint 校验路径型 wikilink：拆锚点 + 跟随 symlink

**类别**：correction | best_practice
**优先级**：medium
**状态**：pending
**范围**：scripts/lint_content.py

**摘要**：lint_content.py 只收集 workspace/ 下文件 stem，对 `[[external-notes/考研数学/…/错题本#错题1]]` 这类路径型、带锚点的跨库 wikilink 误报「指向不存在的文件」；修复为拆 `#锚点`、路径型按 vault 根 `Path.exists()`（跟随 symlink）解析。

**详情**：
- 事实：lint 重建后报「存在问题」，全是 external-notes 链接；实际文件经 `find -L` 验证存在。
- 根因：`WORKSPACE_FILES` 是 workspace 下 `.md` 的 stem 集合；而外部链接目标含 `/` 和 `#锚点`，与 stem 集合永远对不上。`Path.exists()` 会跟随 `external-notes/` symlink，但 lint 从没用它解析路径型链接。
- 下次做法：wikilink 校验分两类——裸名 `[[note]]` 按 workspace stem 匹配；路径型 `[[a/b/c#锚点]]` 先 `split('#')[0]` 再按 vault 根相对补 `.md` 后 `exists()`。

---

### 工作流状态模板与 todo-state.sh 的机器 token 必须同步

**类别**：correction
**优先级**：medium
**状态**：pending
**范围**：.claude/workflows/880-exam/state-template.md / todo-state.sh

**摘要**：state-template.md 的阶段行缺 `{not_started}` 机器 token，导致 todo-state.sh 的状态机判据（`previous_open_phase_before`/`next_pending_phase_after` 匹配行尾 `{token}`）失效，`complete` 时把字面量 `{complete}` 写进行内。

**详情**：
- 事实：跑 `todo-state.sh complete P0` 后状态行变成 `> [P0] ✅ 已完成 {complete}`，`{complete}` 泄漏；连续 complete 报「previous phase is not complete」。
- 根因：模板用 `> [P0] ⬜ 未开始 — 入库` 纯文本，而脚本全部状态判据都要求行尾带 `{not_started}`/`{in_progress}`/`{complete}`/`{skipped}` token；首行 P0 被替换成带 token 格式后，`next_pending_phase_after` 找不到 `{not_started}` 的 P1，直接跳到 done。
- 下次做法：工作流状态模板的每行阶段必须带机器 token（`> [P0] ⬜ 未开始 {not_started} — 说明`）；改状态机脚本或模板任一侧后，用空状态文件重放一遍 start→complete 全链路验证。

---
