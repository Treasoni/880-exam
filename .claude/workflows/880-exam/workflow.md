# Workflow: 880-exam

880 考研数学习题系统的操作工作流。`required: no`——单步命令（拼卷/判分/错题本/预览）直接用对应 skill 执行；本工作流用于跟踪一个完整做题流程的状态（拼了哪张卷、是否已判分、有哪些欠账），支持跨会话恢复。

## 相关 skills

| 命令 | Skill | 脚本 |
| --- | --- | --- |
| 拼卷 | `880-paper` | `scripts/make_paper.py` |
| 判分 | `880-grade` | `scripts/grade.py` |
| 错题本 | `880-wrongbook` | `scripts/wrong_book.py` |
| 预览/进度 | `880-progress` | `scripts/progress.py` |
| 入库 | `880-build-index` | `scripts/prepare_sections.py` + 提取 Workflow + `scripts/merge_extraction.py` |

## 阶段

> [P0] ⬜ 入库：确保 `workspace/question-index.json` 存在且完整（约 606 题）。
> [P1] ⬜ 拼卷：`make_paper.py` 生成卷子与答案卷，更新 `workspace/records/papers.json`。
> [P2] ⬜ 判分：用户做完后，`grade.py` 记录五态判分，刷新错题本与进度总览。
> [P3] ⬜ 错题/补弱：错题本复习状态更新；弱点分影响下一张卷配额。
> [P4] ⬜ 预览：`progress.py` 刷新 `workspace/preview/进度总览.md`。

## 状态文件

`workspace/workflow-runs/880-exam.workflow.md`，用 `.claude/scripts/todo-state.sh` 更新阶段状态。

## 数据流

```
question-index.json  ←  解析册+做题本（入库）
        ↓ 抽题
papers/paper-XX/（卷子-XX.md + 卷子-XX-答案.md + 判分卡-XX.md）  →  papers.json（快照）
        ↓ 判分（读判分卡勾选）
records/attempts.json  →  错题本.md / 进度总览.md / 弱点分 → 下一张卷配额
```
