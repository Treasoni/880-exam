
## 2026-09-11

### Obsidian 独立公式块错位（已修复并归档）

**来源**：本次线代答案卷 Q4 前多出一个 `$$`，导致后续内容存在数学环境错位；原有内容校验未发现。

**根因**：仅依赖“定界符数量为偶数”不足以发现错位公式块；`scripts/lint_content.py` 没有检查公式块上下文。

**修复路径**：
- `scripts/lint_content.py` 新增 `lint_math()`：检查控制字符、未闭合 `$$`、公式块吞入 Markdown 题号/标题，以及误用 `\[...\]`。
- `.codex/rules/common/obsidian-content.md`、`.agents/skills/880-paper/SKILL.md`、`.agents/skills/obsidian-markdown/SKILL.md` 增加“生成/编辑后必须运行 lint”的硬性步骤。
- 修正答案卷中的多余 `$$` 和被空格拆开的 `12`、`-14`。

**验证**：
- `python3 scripts/lint_content.py`：全部通过。
- 回归测试：构造“多余 `$$` + `**4.**`”样例，校验器成功报错。
- `python3 -m py_compile scripts/lint_content.py`：通过。

**处理结果**：保留新的可执行规则，归档本次错误及重复的旧公式定界符记录。

---
