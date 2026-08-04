---
name: 880-build-index
description: 从做题本+解析册重建题目索引（首次入库或源文件更新后用）。触发词：入库、重建索引、初始化题库。
---

# 入库

把 `880/` 下的做题本与解析册 Markdown 解析、按内容对齐，生成 `workspace/question-index.json`。

## 步骤

1. **切分小节**（若源文件有变化）：
   ```
   python3 scripts/prepare_sections.py
   ```
   生成 `workspace/.build/sections/{id}.wb.md` 与 `.ans.md` 原文对。
2. **逐节提取**：运行提取 Workflow（`workspace/.build/extract_workflow.js`），完成后得到 journal。
3. **合并索引**：
   ```
   python3 scripts/merge_extraction.py --journal <journal.jsonl 路径>
   ```
4. 校验：
   - 总题数应约 606（做题本全部题目）；
   - 缺答案数应极少（解析册确实缺失的题会被标记 `answer_status: missing`，不会进入拼卷池）。

## 说明

- 答案全部来自解析册，禁止 AI 生成答案（见 docs/adr/0001）；
- 提取采用 LLM 按内容对齐，因为两个源文件都有 OCR 标记丢失/合并问题。

## 禁止

- 不要手动编辑 `question-index.json`（应重跑流程）；
- 不要改动 `880/` 源文件。
