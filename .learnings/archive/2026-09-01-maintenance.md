# 2026-09-01 经验库维护归档

## 触发原因

审计发现本次答案卷编辑产生的 obsidian-markdown 记录集中出现，另有历史 880-wrongbook 记录已具备源头修复，适合在验证后清理活跃区。

## 源头修复

- 修改 .agents/skills/obsidian-markdown/SKILL.md：新增现有笔记编辑流程，要求使用“章节标题 + 完整题干”唯一锚点，限定替换范围，检查题号结构，并统一使用 $...$ / $$...$$ 公式定界符。
- .agents/skills/880-wrongbook/SKILL.md 已包含事实源更新、错题本重建和「已掌握」归档规则；scripts/wrong_book.py 已按复习状态保留归档题。

## 验证

- 两个相关 skill 的 YAML 元数据校验通过。
- python3 -m unittest discover -s tests -p 'test_*.py'：15 tests，全部通过。
- 线代答案卷结构校验通过：选择题、填空题、解答题章节各一份，目标题干唯一，显示公式定界符成对。
- 归档前的每条记录均能对应到上述 skill 步骤或已有脚本测试。

## 归档内容

### LEARNINGS.md

- 880 错题本补充解析走事实源
- 880 错题本保留已掌握题
- 重复题号笔记的定点编辑
- Obsidian 显示公式定界符

### ERRORS.md

- 880-wrongbook：直接编辑生成产物
- 880-wrongbook：重做正确后隐藏已掌握题
- obsidian-markdown：使用非唯一题号锚点改写答案卷
- obsidian-markdown：新增独立公式未沿用笔记定界符

