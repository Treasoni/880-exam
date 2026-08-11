# 铁律

从 `LEARNINGS.md` 和 `ERRORS.md` 提炼出的最高优先级规则。

---

_最后更新：2026-08-11_

## 880 产物格式

- **格式修改链路**：改 880 产物格式必须先改 `.claude/rules/common/obsidian-content.md`，再同步 `scripts/` 生成脚本与对应 skill（880-paper / 880-grade / 880-wrongbook / 880-progress），最后重建受影响产物。
- **重建不换题**：重建已有卷子的产物（如答案卷）时，从 `workspace/records/papers.json` 读取同一批题目重建，禁止重新抽题覆盖用户正在做的卷子。
- **重建入口 --rebuild**：重建已有卷产物用 `python3 scripts/make_paper.py --rebuild <paper_id>`（从 papers.json 读同一批题；判分卡总是重建，卷子/答案仅在未判分时重建）。
- **答案卷内容**：答案卷每题包含「题目原文 + 答案 + 解析」（用户明确偏好，以后生成卷子都这样）。
- **判分卡勾选**：判分卡状态用任务清单复选框（`- [ ] 对` 等，阅读视图可点击），不用表格内 `[ ]`；每题只勾一个状态，多勾判分报错（用户明确偏好，以后都这样）。
- **可点击勾选用任务清单**：Obsidian 需要点击切换的复选框必须写 `- [ ]` 列表项；Markdown 表格里的 `[ ]` 在阅读视图不可点击。

## Obsidian 双链

- **跨库引用用 symlink**：wikilink 只在本 vault 内解析；引用外部库笔记时，把外部目录 symlink 进 vault（如 `external-notes/`，加入 .gitignore），再用真实 `[[external-notes/…]]`。
- **生成产物不手改**：会被脚本重建的产物（错题本等），映射/配置存 `workspace/records/*.json`，由脚本渲染，禁止手改产物。
- **wikilink 锚点先校验**：生成带 `#锚点` 的 wikilink 前，程序化确认锚点与目标文件标题精确一致（全角标点、空格都要对）。

## 工作流

- **任务收尾做 digest**：用户要求每次任务后按 `/digest` 做自我学习，沉淀真实学习点与错误（以后都这样）。
