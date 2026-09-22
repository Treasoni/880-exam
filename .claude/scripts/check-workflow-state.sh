#!/usr/bin/env bash
# check-workflow-state.sh — 校验工作流状态文件是否符合状态机契约
#
# 校验对象：
#   .claude/workflows/*/state-template.md     模板（新建运行文件时被复制）
#   workspace/workflow-runs/*.workflow.md     运行文件（含历史）
#
# 契约来自 `.claude/scripts/todo-state.sh`：
#   1. 阶段行 token 必须在**行尾**。三条判据 `phase_has_status` /
#      `previous_open_phase_before` / `next_pending_phase_after` 都按
#      `\{token\}$` 匹配；行尾带后缀（如 `— 入库`）的行对状态机不可见，
#      会导致 complete/skip 后 `next_pending_phase_after` 返回空、
#      frontmatter 被提前置为 done/complete（跳档）。
#   2. 文件必须含 `## 异常记录` 表，否则 `todo-state.sh skip|block`
#      以 `exception table not found` 失败。
#   3. 运行文件的 frontmatter 必须有 `current_phase` / `current_status`
#      （由 `set_recovery_state` 维护；模板由第一条状态变更时补齐）。
#
# 用法：.claude/scripts/check-workflow-state.sh
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

shopt -s nullglob
files=(.claude/workflows/*/state-template.md workspace/workflow-runs/*.workflow.md)

if [ ${#files[@]} -eq 0 ]; then
  echo "check-workflow-state: no state files found" >&2
  exit 1
fi

TOKENS='^> \[P[0-9]+\] .* \{(not_started|in_progress|complete|skipped|blocked)\}$'
fail=0

for f in "${files[@]}"; do
  problems=()

  # 1. 阶段行 token 必须在行尾
  while IFS= read -r line; do
    if ! printf '%s\n' "$line" | grep -qE "$TOKENS"; then
      problems+=("阶段行 token 不在行尾: $line")
    fi
  done < <(grep -E '^> \[P[0-9]+\]' "$f" || true)

  if ! grep -qE '^> \[P[0-9]+\]' "$f"; then
    problems+=("缺少阶段行（形如 > [P0] ⬜ 未开始 {not_started}）")
  fi

  # 2. 异常记录表
  if ! grep -qF "## 异常记录" "$f"; then
    problems+=("缺 ## 异常记录 表（skip/block 会失败）")
  fi

  # 3. 运行文件的 frontmatter 键
  case "$f" in
    workspace/workflow-runs/*)
      for key in current_phase current_status; do
        grep -qE "^$key:" "$f" || problems+=("frontmatter 缺 $key")
      done
      ;;
  esac

  if [ ${#problems[@]} -eq 0 ]; then
    echo "✓ $f"
  else
    fail=1
    echo "✗ $f"
    for p in "${problems[@]}"; do
      echo "    - $p"
    done
  fi
done

if [ "$fail" -ne 0 ]; then
  echo "check-workflow-state: 状态文件不符合状态机契约（见上）" >&2
  exit 1
fi

echo "check-workflow-state: all state files OK"
