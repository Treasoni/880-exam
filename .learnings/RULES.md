# 铁律

从 `LEARNINGS.md` 和 `ERRORS.md` 提炼出的最高优先级规则。

---

_最后更新：2026-08-11_

## 880 产物格式

- **格式修改链路**：改 880 产物格式必须先改 `.claude/rules/common/obsidian-content.md`，再同步 `scripts/` 生成脚本与对应 skill（880-paper / 880-grade / 880-wrongbook / 880-progress），最后重建受影响产物。
- **重建不换题**：重建已有卷子的产物（如答案卷）时，从 `workspace/records/papers.json` 读取同一批题目重建，禁止重新抽题覆盖用户正在做的卷子。
- **答案卷内容**：答案卷每题包含「题目原文 + 答案 + 解析」（用户明确偏好，以后生成卷子都这样）。
