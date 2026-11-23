"""Offline regression tests; all hook inputs and collector outputs are temporary."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "read_learnings.py"
COLLECTOR = ROOT / ".claude" / "scripts" / "collect_llm_usage.py"
TIMESTAMP = "2026-01-01T00:00:00+00:00"


def run(script, *args):
    return subprocess.run([sys.executable, str(script), *map(str, args)], check=True,
                          capture_output=True).stdout


def line(record):
    return (json.dumps(record, ensure_ascii=False) + "\n").encode()


def assistant(message_id, **usage):
    return {"type": "assistant", "timestamp": TIMESTAMP, "message": {
        "id": message_id, "model": "fixture-model", "usage": usage,
    }}


class StartupContextTests(unittest.TestCase):
    def test_default_context_stays_stable_without_importing_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = run(HOOK, "--project-root", root)
            files = root / ".learnings"
            files.mkdir()
            for filename in ("RULES.md", "ERRORS.md", "LEARNINGS.md"):
                (files / filename).write_text("fixture-history\n" * 500, encoding="utf-8")
            after = run(HOOK, "--project-root", root)
            self.assertEqual(before, after)
            self.assertLess(len(after), 1500)
            for filename in ("RULES.md", "ERRORS.md", "LEARNINGS.md"):
                self.assertIn(filename, after.decode())
            self.assertEqual(run(HOOK, "--project-root", root, "--tail-lines", "1").count(
                b"fixture-history"), 3)


class UsageCollectorTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.transcripts = self.root / "transcripts"
        self.transcripts.mkdir()
        self.session = self.transcripts / "session.jsonl"
        self.output = self.root / "events.jsonl"
        self.state = self.root / "collector-state.json"

    def collect(self, *args):
        run(COLLECTOR, "--project-root", self.root, "--transcript-dir", self.transcripts,
            "--output", self.output, "--state-file", self.state, *args)
        return [json.loads(row) for row in self.output.read_text().splitlines()] if self.output.exists() else []

    def append(self, data):
        with self.session.open("ab") as fh:
            fh.write(data)

    def test_read_larger_than_uncached_input_and_missing_fields(self):
        self.append(line(assistant("one", input_tokens=12, output_tokens=5,
                                   cache_read_input_tokens=800, cache_creation_input_tokens=90)))
        self.append(line(assistant("two", input_tokens=20, output_tokens=2,
                                   cache_read_input_tokens=0, cache_creation_input_tokens=-1)))
        first, second = self.collect("--cache-semantics", "anthropic")
        self.assertEqual((first["input_tokens"], first["cache_read_tokens"], first["cache_write_tokens"]),
                         (12, 800, 90))
        self.assertEqual(first["metadata"]["cache_semantics"], "anthropic")
        self.assertEqual(first["metadata"]["collector_version"], 2)
        self.assertEqual(second["cache_read_tokens"], 0)
        self.assertNotIn("cache_write_tokens", second)
        self.assertEqual(second["metadata"]["cache_semantics"], "unknown")

    def test_incremental_partial_record_and_duplicate_usage(self):
        self.append(line({"type": "user", "isMeta": True, "message": {"content": "拼卷"}}))
        self.assertEqual(self.collect(), [])
        self.assertTrue(self.state.exists())
        user = {"type": "user", "timestamp": TIMESTAMP, "message": {"content": "判分"}}
        response = line(assistant("one", input_tokens=25, output_tokens=9,
                                  cache_read_input_tokens=200, cache_creation_input_tokens=0))
        # Leave a complete bad line in the middle and an unfinished record at EOF.
        self.append(line(user) + b"{bad record}\n" + response[:-1])
        self.assertEqual(self.collect(), [])
        self.append(b"\n")
        self.assertEqual(self.collect("--dry-run"), [])
        events = self.collect()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["request_type"], "grade")
        self.assertEqual(events[0]["cache_read_tokens"], 200)
        self.assertEqual(events[0]["metadata"]["cache_semantics"], "unknown")
        synthetic = assistant("skip", input_tokens=0, output_tokens=0)
        synthetic["message"]["model"] = "<synthetic>"
        self.append(line(synthetic) + response)
        self.assertEqual(self.collect(), events)
        self.append(line(assistant("two", input_tokens=25, output_tokens=9)))
        self.assertEqual(len(self.collect()), 2)


if __name__ == "__main__":
    unittest.main()
