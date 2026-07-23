"""End-to-end spine: read a file and answer a question, with a verbatim audit
line written before the (offline) model call. Plus gateway scope enforcement.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from auditable_agent.audit import AuditLog
from auditable_agent.config import Config
from auditable_agent.contracts import (
    Message,
    Request,
    ScopeLevel,
    ToolDef,
)
from auditable_agent.gateway import Gateway, ScopeViolation
from auditable_agent.cli import build_loop


class SpineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "greet.py").write_text(
            "print('hello world')\n", encoding="utf-8"
        )
        self.config = Config(
            adapter="echo",
            root=self.root,
            audit_path=self.root / ".agent" / "audit.jsonl",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_read_and_answer_offline(self):
        loop = build_loop(self.config)
        result = loop.run("What is in greet.py?")
        self.assertIn("greet.py", result.text)
        self.assertEqual(result.files_read, ["greet.py"])
        self.assertEqual(result.stop, "end")

    def test_audit_line_written_verbatim(self):
        loop = build_loop(self.config)
        loop.run("Tell me about greet.py")
        lines = self.config.audit_path.read_text().strip().splitlines()
        self.assertTrue(lines)
        entry = json.loads(lines[0])
        self.assertIn("payload", entry)
        self.assertIn("messages", entry["payload"])
        self.assertTrue(entry["payload_hash"].startswith("sha256:"))
        self.assertEqual(entry["scope"], int(ScopeLevel.REPO))

    def test_scope_filters_tool_list(self):
        # A Level-1 (SCOPED) tool must not be advertised at Level 0 (SEALED).
        loop = build_loop(self.config)
        registry = loop._tools
        self.assertEqual(registry.available(ScopeLevel.SEALED), [])
        self.assertTrue(registry.available(ScopeLevel.SCOPED))

    def test_gateway_blocks_tool_above_request_scope(self):
        gw = Gateway(self.config, AuditLog(self.config.audit_path))
        high = ToolDef(
            name="danger",
            description="needs open scope",
            params={"type": "object"},
            scope=ScopeLevel.OPEN,
            mutating=True,
        )
        req = Request(
            messages=[Message(role="user", content="hi")],
            tools=[high],
            scope=ScopeLevel.REPO,
            max_tokens=64,
        )
        with self.assertRaises(ScopeViolation):
            gw.send(req)

    def test_gateway_blocks_exfiltrable_path(self):
        gw = Gateway(self.config, AuditLog(self.config.audit_path))
        req = Request(
            messages=[Message(role="user", content="hi")],
            tools=[],
            scope=ScopeLevel.REPO,
            max_tokens=64,
            files_included=["config/.env"],
        )
        with self.assertRaises(ScopeViolation):
            gw.send(req)


if __name__ == "__main__":
    unittest.main()
