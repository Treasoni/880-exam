---
name: 880-wrongbook
description: 查看/重生成错题本，更新复习状态（未复习/已重做/已掌握）。触发词：错题本、看错题、重练、复习错题。
---

# 错题本

错题本按章节组织，`不会/半会` 为重点，`错/粗心` 为轻标记；每条带复习状态。

## 步骤

1. **查看状态清单**：
   ```
   python3 scripts/wrong_book.py --list-states
   ```
   或直接读 `workspace/wrong-book/错题本.md`。
2. **重生成错题本**：
   ```
   python3 scripts/wrong_book.py
   ```
3. **更新复习状态**：
   ```
   python3 scripts/wrong_book.py --mark gs-c01-basic-choice-003=已掌握
   ```
   状态可选：未复习 / 已重做 / 已掌握。

## 重练流程（对话式）

用户报"重练了某题，会了"时：
- 若该题在**某张卷子**里：走 `880-grade` 技能 `--redo`，直接记判分并联动状态；
- 若不在卷子里：先确认题号（qid），用 `wrong_book.py --mark <qid>=已掌握`。

## 禁止

- 不要随意把题从错题本删除（除非用户明确要求）；
- 复习状态由用户报告更新，不要自行推断。
