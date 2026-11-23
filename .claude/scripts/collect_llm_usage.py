#!/usr/bin/env python3
"""Collect LLM usage events from Claude Code session transcripts for this project.

Automatic pipeline:
  Claude Code writes one append-only JSONL transcript per session under
  ~/.claude/projects/<sanitized-project-path>/. Assistant records can carry a
  provider `usage` block (input/output/cache tokens), repeated across multiple
  blocks of one message. This script maps observed usage to session labels and appends
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
COLLECTOR_VERSION = 2
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


def classify_text(text: str) -> dict[str, str]:
    for pattern, request_type, template_id in TRIGGERS:
        if re.search(pattern, text):
            return {"request_type": request_type, "template_id": template_id}
    return {"request_type": GENERAL, "template_id": SESSION_TEMPLATE}


def valid_token_count(value: Any) -> bool:
    return type(value) is int and value >= 0


def build_event(
    record: dict[str, Any], cls: dict[str, Any], file_name: str, latency_ms: float,
    cache_semantics: str,
) -> dict[str, Any]:
    usage = record["message"]["usage"]
    event: dict[str, Any] = {
        "timestamp": record["timestamp"],
        "request_type": cls.get("request_type", GENERAL),
        "template_id": cls.get("template_id", SESSION_TEMPLATE),
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
            "collector_version": COLLECTOR_VERSION,
            "cache_semantics": "unknown",
        },
    }
    for source, target in (
        ("cache_read_input_tokens", "cache_read_tokens"),
        ("cache_creation_input_tokens", "cache_write_tokens"),
    ):
        value = usage.get(source)
        if valid_token_count(value):
            event[target] = value
    # Native Anthropic input_tokens excludes both cache buckets. Gateways can
    # expose the same field names with different meanings: never infer semantics
    # from token magnitudes or the model name.
    if "cache_read_tokens" in event and "cache_write_tokens" in event:
        event["metadata"]["cache_semantics"] = cache_semantics
    return event


def process_file(path: Path, state: dict[str, Any], cache_semantics: str) -> list[dict[str, Any]]:
    key = str(path.resolve())
    size = path.stat().st_size
    info = state.get(key)
    if info is None or info.get("offset", 0) > size:
        info = {"offset": 0}
        state[key] = info
    offset = int(info["offset"])
    if offset == size:
        return []
    events: list[dict[str, Any]] = []
    prev_ts = parse_ts(info["last_timestamp"]) if "last_timestamp" in info else None
    with path.open("rb") as fh:
        fh.seek(offset)
        while line := fh.readline():
            if not line.endswith(b"\n"):
                break  # incomplete trailing record; retry next run
            info["offset"] = fh.tell()
            try:
                record = json.loads(line)
                ts_value = record.get("timestamp")
                ts = parse_ts(ts_value) if ts_value else None
            except (AttributeError, TypeError, ValueError):
                continue  # a bad complete record must not block future collection
            if record.get("type") == "user" and "template_id" not in info and not record.get("isMeta"):
                text = user_text(record)
                if text.strip():
                    info.update(classify_text(text))
            if record.get("type") == "assistant" and ts:
                message = record.get("message") or {}
                usage = message.get("usage") or {}
                message_id = message.get("id")
                if (message.get("model") != "<synthetic>"
                        and valid_token_count(usage.get("input_tokens"))
                        and valid_token_count(usage.get("output_tokens"))
                        and (not message_id or message_id != info.get("last_usage_message_id"))):
                    latency = (ts - prev_ts).total_seconds() * 1000.0 if prev_ts else 0.0
                    events.append(build_event(record, info, path.name, max(0.0, latency), cache_semantics))
                    if message_id:
                        info["last_usage_message_id"] = message_id
            if ts:
                prev_ts = ts
                info["last_timestamp"] = ts_value
    return events


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=None, help="Project root (default: two dirs above this script).")
    parser.add_argument("--transcript-dir", type=Path, default=None, help="Claude Code project transcript dir (default: ~/.claude/projects/<sanitized root>).")
    parser.add_argument("--output", type=Path, default=None, help="Events JSONL path (default: <root>/.llm/prompt-cache/usage-events.jsonl).")
    parser.add_argument("--state-file", type=Path, default=None, help="Incremental state file (default: <root>/.llm/prompt-cache/collector-state.json).")
    parser.add_argument("--recursive", action="store_true", help="Also collect subagent/workflow transcripts under subdirectories.")
    parser.add_argument("--cache-semantics", choices=("unknown", "anthropic"), default="unknown",
                        help="Declare native Anthropic token semantics only for a verified, homogeneous source.")
    parser.add_argument("--dry-run", action="store_true", help="Print the summary without appending events.")
    parser.add_argument("--quiet", action="store_true", help="Suppress the summary; used by hooks so per-turn output stays silent.")
    args = parser.parse_args()

    root = args.project_root.resolve() if args.project_root else project_root_from_script()
    transcript_dir = (args.transcript_dir or default_transcript_dir(root)).resolve()
    events_file = args.output or (root / ".llm" / "prompt-cache" / "usage-events.jsonl")
    state_file = args.state_file or (root / ".llm" / "prompt-cache" / "collector-state.json")

    pattern = "**/*.jsonl" if args.recursive else "*.jsonl"
    transcripts = sorted(transcript_dir.glob(pattern)) if transcript_dir.is_dir() else []

    saved_state = state_file.read_text(encoding="utf-8") if state_file.is_file() else "{}"
    state: dict[str, Any] = json.loads(saved_state)

    new_events: list[dict[str, Any]] = []
    for path in transcripts:
        new_events.extend(process_file(path, state, args.cache_semantics))

    if not args.dry_run:
        if new_events:
            events_file.parent.mkdir(parents=True, exist_ok=True)
            with events_file.open("a", encoding="utf-8") as fh:
                for event in new_events:
                    fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        updated_state = json.dumps(state, ensure_ascii=False, indent=2)
        if updated_state != saved_state:
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(updated_state, encoding="utf-8")

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
