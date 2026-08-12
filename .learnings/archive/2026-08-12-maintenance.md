# 2026-08-12 经验库维护归档

## 触发原因
`.learnings/LEARNINGS.md` 与 `.learnings/ERRORS.md` 超过 100 行；审计显示 `880-wrongbook` 重复出现“直接修改生成产物/未同步事实源”。

## 源头修复
- 修改 `.agents/skills/880-wrongbook/SKILL.md`：补充解析必须写入 `workspace/question-index.json`，运行 `python3 scripts/wrong_book.py`，并 grep 核验。
- 本次两道题的讲解已写入 `workspace/question-index.json` 并成功重生成错题本。
- 验证：`880-wrongbook skill verification passed`；错题本中两个 callout 均存在。

## 归档内容
- 归档维护前 `.learnings/LEARNINGS.md` 全量记录（含 2026-08-12 新增条目）。
- 归档维护前 `.learnings/ERRORS.md` 全量记录（含 2026-08-12 新增条目）。
