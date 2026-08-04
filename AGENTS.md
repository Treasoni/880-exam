# 880 考研数学习题系统

面向考研数学（高数）刷题的 Obsidian 习题系统：从 `880/` 原始题库构建题目索引，支持拼卷、判分、错题本与进度总览的完整做题闭环。

## 核心工作流（通过 skill 触发）

| 操作 | Skill | 触发词 |
|------|-------|--------|
| 入库 / 重建索引 | `880-build-index` | 入库、重建索引、初始化题库 |
| 拼卷 | `880-paper` | 拼卷、出卷、生成卷子、来张卷 |
| 判分 | `880-grade` | 判分、改卷、对答案 |
| 错题本 | `880-wrongbook` | 错题本、看错题、重练 |
| 进度总览 | `880-progress` | 预览、进度、进度总览 |

完整技能表见 `.codex/rules/common/skill-invocation.md`。涉及拼卷/判分/错题本/预览/入库的操作，先读 `.codex/rules/workflow-routing.md` 匹配 `880-exam` 工作流。

## 数据模型与关键路径

- `880/` — 原始题库（做题本 / 解析册，只读源，不修改）
- `workspace/question-index.json` — 题目索引（由 `scripts/build-question-index.py` 重建）
- `workspace/records/attempts.json` — 判分记录
- `workspace/records/papers.json` — 卷子记录
- `workspace/papers/paper-XX/` — 每卷一个文件夹：`卷子-XX.md`、`卷子-XX-答案.md`、`判分卡-XX.md`
- `workspace/wrong-book/错题本.md` — 错题本
- `workspace/preview/进度总览.md` — 进度总览

## 常用命令

```bash
# 重建题目索引
python3 scripts/build-question-index.py

# 拼一张模拟卷（默认：选10×5分 + 填6×5分 + 解6题 = 150分 / 180分钟）
python3 scripts/make_paper.py [--n N] [--seed SEED] [--ignore-extension] [--no-weakness]

# 判分（推荐：读取判分卡勾选，paper_id 自动从卡片 frontmatter 获取）
python3 scripts/grade.py --sheet workspace/papers/paper-01/判分卡-01.md [--redo]
# 判分（兜底：--grading-file 传 JSON，避免 shell 引号问题）
python3 scripts/grade.py --paper <paper_id> --grading-file <UTF-8 判分文件> [--redo]
```

Windows 下用 `py -3` 替代 `python3`。

<!-- env-template:codex:begin -->
## Environment Variables

- Follow `.codex/rules/common/env.md` whenever creating, updating, migrating, or auditing `.env`, `.env.example`, or environment-variable documentation.
- Keep committed env templates minimal, project-specific, and free of real secrets or machine-local absolute paths.
- After env template changes, run `.codex/scripts/check-env-template.sh`. Use `--strict` when you want unused documented variables to fail the check.
<!-- env-template:codex:end -->

<!-- prompt-cache-bootstrap:codex:begin -->
## Prompt Cache

- Follow `.codex/rules/common/prompt-cache.md` for high-frequency prompt design.
- Keep stable instructions and output formats before dynamic user input, file excerpts, dates, IDs, and runtime state.
- Reuse canonical templates and load long context only when needed.
<!-- prompt-cache-bootstrap:codex:end -->

<!-- workflow-todo-state:start -->
## Workflow Todo State

Named workflow state files are the source of truth for every routed workflow.

- Workflow definitions live under `.codex/workflows/{workflow-id}/`.
- Workflow state files live under `workspace/workflow-runs/` and should be named after the task, for example `payment-refactor.workflow.md`.
- Before any action that changes project files, runs project commands, or calls external services, read `.codex/rules/workflow-routing.md` and match the user's original request against its triggers and exclusions.
- When a `Required: yes` workflow matches, read its `workflow.md`, create or resume its state file, and start the current phase before doing the work. Do not take the ordinary execution path instead.
- If the route is ambiguous, ask the user before acting.
- Read the active workflow state file before starting any phase; do not skip prerequisite phases.
- Change phase state only through `.codex/scripts/todo-state.sh`.
- Use one unique phase status line per phase, for example `> [P0] ⬜ 未开始`.
- On resume after interruption, inspect the YAML frontmatter and current phase before acting.
- Each workflow directory must contain a `routing.yaml`. After creating, changing, renaming, or deleting a workflow, run `.codex/scripts/sync-workflow-routing.sh`; the update is incomplete until `.codex/scripts/sync-workflow-routing.sh --check` passes.
<!-- workflow-todo-state:end -->

<!-- obsidian-content:codex:begin -->
## Obsidian 内容规范

- 生成任何 Markdown 内容（880 产物的卷子/答案卷/错题本/进度总览，以及文档、ADR、笔记、报告）时，遵循 `.codex/rules/common/obsidian-content.md`。
- 每个生成文件必须带 YAML frontmatter（`type` + `date`/`updated` + `tags`）；站内引用用 `[[wikilink]]`；高亮用 `> [!callout]`；表格只用 Markdown；公式用 LaTeX。
- 修改 880 产物格式时：先改规则文件，再同步改 `scripts/` 生成脚本与对应 skill（`880-paper`/`880-grade`/`880-wrongbook`/`880-progress`）。
<!-- obsidian-content:codex:end -->

## 跨平台（Linux / macOS / Windows）

- 880 脚本统一用 Python 3 + `pathlib`，命令写 `python3`；Windows 用 `py -3` 替代，或 `make <target> PYTHON='py -3'`。
- 判分优先用 `grade.py --sheet <判分卡>` 读取勾选；JSON 兜底用 `--grading-file <UTF-8 文件>`，避免 shell 引号问题。
- `.codex/scripts/*.sh` 与 hooks 是 bash 脚本，Windows 下需要 Git Bash / WSL 运行。
- 文本换行由 `.gitattributes` 强制 LF，防止 Windows `autocrlf` 破坏脚本。
