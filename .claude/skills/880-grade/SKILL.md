---
name: 880-grade
description: 判分记录（五态：对/错/不会/半会/粗心），更新判分记录、错题本与进度总览。触发词：判分、改卷、对答案、交判分。
---

# 判分

优先走**勾选式**：拼卷时已随卷子生成 `判分卡-XX.md`，用户对照答案勾选每题状态。判分 = 读取判分卡勾选并落库。口述 JSON 保留作兜底。

## 步骤（勾选式，默认）

1. **确认卷子**：用户说"卷子01"/"第1套" → `paper-01`，判分卡在 `workspace/papers/paper-01/判分卡-01.md`。
2. **确认判分卡已勾选**：打开判分卡文件，确认各题勾选了状态（`- [x] 对` 形式）；未勾选的题跳过即可。
3. 运行：
   ```
   python3 scripts/grade.py --sheet workspace/papers/paper-01/判分卡-01.md [--redo] [--note "备注"]
   ```
   - `--sheet` 会从判分卡 frontmatter 自动读 `paper_id`，无需再传 `--paper`。
   - `--redo`：错题重练模式——判为"对"则该题复习状态→已掌握，否则保持未复习。
   - Windows 把 `python3` 换成 `py -3`。
   - 判分卡里某题勾了多个状态会报错，先让用户修正再跑。
4. 报告：记录条数、卷子状态（`status` 已置 `graded`、判分表已回填）、错题本与进度已刷新。

## 步骤（口述 JSON，兜底）

用户直接口述状态（如「判分：一1对 一2错 二3不会 三1半会」）时：

1. **解析判分**为 `--grading` JSON：`题型(choice/fill/solution) → {题号: 判分}`。
   - 题型对照：一=选择题(choice)、二=填空题(fill)、三=解答题(solution)。
   - 示例：`判分：一1对 一2错 二3不会 三1半会`
     → `{"choice":{"1":"对","2":"错"},"fill":{"3":"不会"},"solution":{"1":"半会"}}`
   - 判分可用中文或英文（对/correct、错/wrong、不会/cannot、半会/half、粗心/careless）。
2. 运行：
   ```
   python3 scripts/grade.py --paper paper-01 --grading '<JSON>' [--redo] [--note "备注"]
   ```
   - JSON 含引号不好传时改用 `--grading-file <UTF-8 文件>`；`--grading` 可带外层单/双引号（已容错）。

## 禁止

- 不要猜测未提到的题目状态（判分卡空行 / 未口述的题保持未判）；
- 不要修改题目索引或卷子内容（卷子文件的 `status`、判分表由判分流程更新）。

## 内容规范

- 判分后刷新的 错题本/进度总览 遵循 `.claude/rules/common/obsidian-content.md` 的「错题本」「进度总览」两节；
- 判分流程需把对应 `卷子-XX.md` 的 frontmatter `status` 更新为 `graded`、`updated` 更新为当日，并把判分态回填到卷子判分表。
