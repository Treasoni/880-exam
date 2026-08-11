---
name: 880-analysis
description: 对话式过程归因——用户贴做题过程，定位出错环节并给出建议，写入 analysis.json 并由错题本渲染。触发词：分析、错因、归因、这题我哪里错了、看我做题过程、我这样做的。
---

# 错因分析（过程归因）

对**已判分**的题做过程归因：读用户贴的解题过程 → 对照正确答案与解析 → 定位第一个出错步骤 → 归类错因 → 写 `analysis.json` → 重建错题本渲染「错因分析」callout。

**前置条件**：题目必须已判分（在 `workspace/records/attempts.json` 里，通常已在错题本）。未判分的题先引导走 `880-grade` 判分，再回来分析。

## 步骤

1. **定位题目**：从用户说的卷子+题号（如「卷子01 三2」）定位：
   - 卷子号 → `paper-XX`；
   - 从 `workspace/records/papers.json` 该卷 `questions` 里按 `paper_no`（`一1`/`二3`/`三2`）反查 `qid`。
2. **读上下文**：从题目索引（`workspace/question-index.json`）或 `卷子-XX-答案.md` 读题干、答案、解析；从 `attempts.json` 读该题判分态（对/错/不会/半会/粗心）。
3. **对照分析**：把用户贴的解题过程与正确解析逐步对照，找出**第一个出错的具体步骤**（从哪一步开始偏离），不要只报「答案不对」。
4. **归类并建议**：从 `schema.analysis.cause_labels`（审题失误 / 方法选择错误 / 概念定理错误 / 计算代数错误 / 步骤逻辑遗漏 / 粗心）选一个标签；写一句具体、可执行的建议。
5. **落库**：写入 `workspace/records/analysis.json`：

   ```json
   {
     "items": {
       "<qid>": {
         "paper_id": "paper-01",
         "cause": "方法选择错误",
         "step": "第 2 步把 $\\sqrt[n]{n}$ 当 $1$ 处理，丢了高阶项",
         "advice": "含 n 次根号的差先提公因式、用等价无穷小定阶再取极限",
         "date": "YYYY-MM-DD"
       }
     }
   }
   ```

   用 `lib880.load_analysis()` 读、`save_analysis()` 写——**保留已有条目**（同题覆盖，异题追加）。
6. **重生成**：`python3 scripts/wrong_book.py`，错题本该题条目末尾自动渲染「错因分析」callout。
7. **报告**：向用户展示 callout 内容（错因/出错环节/建议），说明已写入错题本。

## 触发词判断

- 用户贴出做题过程 + 「哪错了 / 为什么错 / 帮我看看」→ **880-analysis**；
- 用户只说「这题对 / 错 / 半会」等判分信息 → **880-grade**；
- 用户问「这道错题怎么复习」→ **880-wrongbook**。

## 禁止

- **不批量分析**：只有用户主动要求才分析，不要对每道错题自动生成；
- **不猜测过程**：用户没贴解题过程的题，不臆测错因；
- **不手改错题本**：callout 由 `wrong_book.py` 渲染，映射数据只写 `analysis.json`；
- **不改判分**：`analysis.json` 不触碰 `attempts.json`；判分变更走 `880-grade`。

## 内容规范

- 错题本条目「错因分析」callout 格式遵循 `.claude/rules/common/obsidian-content.md` 的「错题本」一节；
- 错因标签只用 `schema.analysis.cause_labels` 六类，不新增自由文本分类；
- 日期一律 ISO `YYYY-MM-DD`。
