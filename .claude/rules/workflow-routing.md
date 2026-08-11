# Workflow Routing

Use this rule file to decide which named workflow to use and where to find active run state.

## Workflow Directory Layout

```text
.claude/workflows/{workflow-id}/workflow.md        # workflow definition
.claude/workflows/{workflow-id}/state-template.md # state file template
workspace/workflow-runs/*.workflow.md                   # active or historical run state
```

## Available Workflows

<!-- workflow-routing:generated:start -->
| Workflow ID | Required | When To Use | Positive Triggers | Excludes | Definition | State File Pattern |
| --- | --- | --- | --- | --- | --- | --- |
| `880-exam` | no | 用户使用 880 习题系统（拼卷/判分/错因分析/错题本/预览/入库），或需要恢复进行中的做题流程时。 | 拼卷、拼张卷、判分、改卷、错因、归因、分析、错题本、预览、进度、补弱、重练、880、模拟卷、做题 | 与 880 习题系统无关的通用开发任务 | `.claude/workflows/880-exam/workflow.md` | `workspace/workflow-runs/880-exam.workflow.md` |
<!-- workflow-routing:generated:end -->

## Routing Rules

- Before any action that changes project files, runs project commands, or calls external services, choose the matching `workflow_id` from the table.
- Match the user's original request against positive triggers and exclusions. A matching `Required: yes` workflow cannot use the ordinary execution path.
- If multiple workflows match, choose the more specific workflow; if the route remains ambiguous, ask the user before acting.
- If a matching run already exists under `workspace/workflow-runs/`, resume it instead of creating a duplicate.
- If no run exists, create a named state file from the workflow's `state-template.md`.
- Name state files after the task or feature, not `todo.md`, unless the project has exactly one workflow.
- Every phase must read the active state file before acting.
- Phase state must be changed only through `.claude/scripts/todo-state.sh`.
- Each workflow directory must have a `routing.yaml`; it is the source of truth for the generated table above.
- After creating, changing, renaming, or deleting a workflow, run `.claude/scripts/sync-workflow-routing.sh`. Use `.claude/scripts/sync-workflow-routing.sh --check` in pre-commit or CI.

## Active Runs

| State File | Workflow ID | Task | Current Phase | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| | | | | | |
