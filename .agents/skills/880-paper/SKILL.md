---
name: 880-paper
description: 拼一张 880 高数或线代模拟卷（真题模式：选10×5分+填6×5分+解6题=150分/180分钟），生成卷子、答案卷与判分卡。触发词：拼卷、拼张卷、出卷、生成卷子、来张卷、线代卷。
---

# 拼卷

按真题模式从指定科目的题库加权抽题（含本学科补弱配额浮动），生成卷子与独立答案卷。用户未指定科目时默认高数；明确提到「线代」「线性代数」时生成线代独立卷。

## 步骤

1. 按用户指定科目运行：
   ```
   # 高数（默认）
   python3 scripts/make_paper.py [--seed N] [--ignore-extension] [--no-weakness]

   # 线性代数
   python3 scripts/make_paper.py --subject linear-algebra [--seed N] [--ignore-extension] [--no-weakness]
   ```
   - 默认自动取该科目的下一卷号；`--seed` 可复现同一张卷；`--ignore-extension` 不用拓展题；`--no-weakness` 忽略本学科弱点浮动。
   - Windows 把 `python3` 换成 `py -3`（或 `make paper PYTHON='py -3'`）。
2. 向用户报告：
   - 高数：`workspace/papers/paper-XX/`，含 `卷子-XX.md`、`卷子-XX-答案.md`、`判分卡-XX.md`；
   - 线代：`workspace/papers/la-paper-XX/`，含 `线代卷子-XX.md`、`线代卷子-XX-答案.md`、`线代判分卡-XX.md`；
   - 卷子规格（选择/填空/解答数量）；
   - 当前科目的弱点章节排行（脚本会打印）。

## 提示用户

- 做题时只看卷子，不看答案卷；
- 做完后打开对应判分卡，对照答案勾选状态，然后说「判分卡填好了」交给判分流程；`grade.py --sheet` 会从卡片 frontmatter 识别科目和卷子。

## 禁止

- 不要手动挑选题目或改动抽题结果；
- 不要把答案写进卷子（答案在独立答案卷，判分卡内嵌答案供判分用）。

## 内容规范

- 卷子、答案卷、判分卡的 frontmatter、结构、`## 关联` wikilink 遵循 `.codex/rules/common/obsidian-content.md` 的「卷子」「答案卷」「判分卡」三节（含 `paper-XX/` 归档布局）。
- 脚本已按规范输出；若需调整格式，先改规则文件，再改 `scripts/make_paper.py`。
