#!/usr/bin/env python3
"""Point agent sessions to the relevant project learnings on demand."""

from __future__ import annotations

import argparse
from pathlib import Path


def default_project_root() -> Path:
    # Expected install shape: <project>/<agent-dir>/hooks/read_learnings.py
    return Path(__file__).resolve().parents[2]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def tail_lines(text: str, count: int) -> str:
    lines = text.splitlines()
    return "\n".join(lines[-count:])


def print_section(title: str, body: str) -> None:
    if not body:
        return
    print(f"## {title}")
    print("")
    print(body.rstrip())
    print("")
    print("---")
    print("")


STARTUP_REMINDER = """# 项目经验索引

先按 CLAUDE.md 确认工作流；写盘或运行项目命令前，检查 Git 状态和同库会话，不覆盖他人改动。原始题库只读；需要更新生成产物时，先改事实源，再按对应 skill 重建。

开展相关工作前，先定位并读 `.learnings/RULES.md` 对应章节，不要凭记忆替代规则：
- 题目、判分、错题、渲染：查「880 产物格式」「改动核验」；真题另查「工作流」。要原题先核对原文，记录作答前先逐题核验。
- 写盘或验证：查「写盘前提与并发」「改动核验」。配图、双链或状态机查同名章节。
- 复发问题再查 `.learnings/ERRORS.md`；解题经验再查 `.learnings/LEARNINGS.md`。只读取与任务有关的条目。"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=None, help="Project root for excerpts. Defaults to two directories above this hook.")
    parser.add_argument("--tail-lines", type=int, help="Opt in to printing this many recent lines per learnings file.")
    args = parser.parse_args()

    if args.tail_lines is not None and args.tail_lines < 1:
        parser.error("--tail-lines must be positive")
    print("<system-reminder>")
    print(STARTUP_REMINDER)
    if args.tail_lines is not None:
        project_root = Path(args.project_root).resolve() if args.project_root else default_project_root()
        learnings_dir = project_root / ".learnings"
        print()
        for filename, title in (
            ("RULES.md", "Rules (highest priority)"),
            ("ERRORS.md", "Error Log (avoid repeating)"),
            ("LEARNINGS.md", "Recent Learnings"),
        ):
            print_section(title, tail_lines(read_text(learnings_dir / filename), args.tail_lines))
    print("</system-reminder>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
