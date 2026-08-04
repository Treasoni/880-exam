#!/usr/bin/env python3
"""Collect LLM usage events from Claude Code session transcripts for this project.

Automatic pipeline:
  Claude Code writes one append-only JSONL transcript per session under
  ~/.claude/projects/<sanitized-project-path>/; every assistant record carries a
  provider `usage` block (input/output/cache tokens). This script parses those
  transcripts, maps each request to a request_type/template_id, and appends
  schema-conformant events (see .llm/prompt-cache/llm-usage-event.schema.json)
  to .llm/prompt-cache/usage-events.jsonl (gitignored local file).

Documented approximations (.llm/prompt-cache/README.md):
  - request_type/template_id are classified per session from the first user message.
  - latency_ms = time between an assistant record and the previous record in the file.
  - cache_read/write tokens are recorded only when the provider supplies them.

Usage:
  python3 .claude/scripts/collect_llm_usage.py [--dry-run] [--recursive]
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

TEMPLATE_VERSION = "1"
GENERAL = "general-dev"
SESSION_TEMPLATE = "claude-code/session"

# Stable classification table: trigger keywords -> (request_type, template_id).
# Keep the table byte-stable; the collector and regression cases share it.
TRIGGERS: list[tuple[str, str, str]] = [
    (r"拼卷|拼张卷|出卷|生成卷子|来张卷", "paper", "skill/880-paper"),
    (r"判分|改卷|对答案|判分卡", "grade", "skill/880-grade"),
    (r"错题本|看错题|重练|复习错题", "wrongbook", "skill/880-wrongbook"),
    (r"进度|预览", "progress", "skill/880-progress"),
    (r"入库|重建索引|初始化题库", "build-index", "skill/880-build-index"),
    (r"同步技能|注册表|sync skill registry", "sync-skill-registry", "skill/sync-skill-registry"),
    (r"review since", "code-review", "skill/code-review"),
    (r"research|调研|查文档|调查", "research", "skill/research"),
]


def project_root_from_script() -> Path:
    # <project>/.claude/scripts/collect_llm_usage.py
    return Path(__file__).resolve().parents[2]


def sanitized_project_dir(project_root: Path) -> str:
    parts = [p for p in project_root.resolve().parts if p not in ("/", "\\")]
    return "-" + "-".join(parts)


def default_transcript_dir(project_root: Path) -> Path:
    return Path.home() / ".claude" / "projects" / sanitized_project_dir(project_root)


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def user_text(record: dict[str, Any]) -> str:
    content = record.get("message", {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return " ".join(parts)
    return ""


def classify_file(path: Path) -> dict[str, str]:
    """Classify one session file from its first user message."""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("type") == "user":
            text = user_text(record)
            for pattern, request_type, template_id in TRIGGERS:
                if re.search(pattern, text):
                    return {"request_type": request_type, "template_id": template_id}
            break
    return {"request_type": GENERAL, "template_id": SESSION_TEMPLATE}


def build_event(record: dict[str, Any], cls: dict[str, str], file_name: str, latency_ms: float) -> dict[str, Any]:
    usage = record["message"]["usage"]
    event: dict[str, Any] = {
        "timestamp": record["timestamp"],
        "request_type": cls["request_type"],
        "template_id": cls["template_id"],
        "template_version": TEMPLATE_VERSION,
        "model": record["message"].get("model") or "unknown",
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "latency_ms": round(latency_ms, 1),
        "input_reference": f"{file_name}:{record.get('uuid', '?')}",
        "status": "success",
        "metadata": {
            "session_id": record.get("sessionId"),
            "git_branch": record.get("gitBranch"),
        },
    }
    # Record cache tokens only when the provider supplies them; never fabricate.
    if "cache_read_input_tokens" in usage:
        event["cache_read_tokens"] = usage["cache_read_input_tokens"]
    if "cache_creation_input_tokens" in usage:
        event["cache_write_tokens"] = usage["cache_creation_input_tokens"]
    return event


def process_file(path: Path, state: dict[str, Any]) -> list[dict[str, Any]]:
    key = str(path.resolve())
    info = state.get(key)
    if info is None:
        info = classify_file(path)
        info["offset"] = 0
        state[key] = info
    size = path.stat().st_size
    if info.get("offset", 0) > size:
        info["offset"] = 0  # transcript rotated
    events: list[dict[str, Any]] = []
    offset = int(info.get("offset", 0))
    prev_ts: datetime | None = None
    with path.open(encoding="utf-8") as fh:
        fh.seek(offset)
        while True:
            line_start = fh.tell()
            line = fh.readline()
            if not line:
                break
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                info["offset"] = line_start  # partial trailing line; retry next run
                break
            ts_value = record.get("timestamp")
            ts = parse_ts(ts_value) if ts_value else None
            if record.get("type") == "assistant" and record.get("message", {}).get("usage"):
                latency = (ts - prev_ts).total_seconds() * 1000.0 if ts and prev_ts else 0.0
                events.append(build_event(record, info, path.name, latency))
            if ts:
                prev_ts = ts
            info["offset"] = fh.tell()
    return events


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=None, help="Project root (default: two dirs above this script).")
    parser.add_argument("--transcript-dir", type=Path, default=None, help="Claude Code project transcript dir (default: ~/.claude/projects/<sanitized root>).")
    parser.add_argument("--output", type=Path, default=None, help="Events JSONL path (default: <root>/.llm/prompt-cache/usage-events.jsonl).")
    parser.add_argument("--state-file", type=Path, default=None, help="Incremental state file (default: <root>/.llm/prompt-cache/collector-state.json).")
    parser.add_argument("--recursive", action="store_true", help="Also collect subagent/workflow transcripts under subdirectories.")
    parser.add_argument("--dry-run", action="store_true", help="Print the summary without appending events.")
    parser.add_argument("--quiet", action="store_true", help="Suppress the summary; used by hooks so per-turn output stays silent.")
    args = parser.parse_args()

    root = args.project_root.resolve() if args.project_root else project_root_from_script()
    transcript_dir = (args.transcript_dir or default_transcript_dir(root)).resolve()
    events_file = args.output or (root / ".llm" / "prompt-cache" / "usage-events.jsonl")
    state_file = args.state_file or (root / ".llm" / "prompt-cache" / "collector-state.json")

    pattern = "**/*.jsonl" if args.recursive else "*.jsonl"
    transcripts = sorted(transcript_dir.glob(pattern)) if transcript_dir.is_dir() else []

    state: dict[str, Any] = {}
    if state_file.is_file():
        state = json.loads(state_file.read_text(encoding="utf-8"))

    new_events: list[dict[str, Any]] = []
    for path in transcripts:
        new_events.extend(process_file(path, state))

    if new_events:
        if not args.dry_run:
            events_file.parent.mkdir(parents=True, exist_ok=True)
            with events_file.open("a", encoding="utf-8") as fh:
                for event in new_events:
                    fh.write(json.dumps(event, ensure_ascii=False) + "\n")
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    # summary
    if not args.quiet:
        counts: dict[str, int] = {}
        totals: dict[str, int] = {}
        for event in new_events:
            rt = event["request_type"]
            counts[rt] = counts.get(rt, 0) + 1
            for key in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"):
                if key in event:
                    totals[key] = totals.get(key, 0) + event[key]
        print(f"transcripts scanned: {len(transcripts)}")
        print(f"new events: {len(new_events)}" + (" (dry-run)" if args.dry_run else ""))
        for rt in sorted(counts):
            print(f"  {rt}: {counts[rt]}")
        if totals:
            print("totals: " + ", ".join(f"{k}={v}" for k, v in sorted(totals.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
