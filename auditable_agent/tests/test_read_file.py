"""read_file returns shaped data and typed failures."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from auditable_agent.contracts import ToolCall
from auditable_agent.tools import run_read_file


class ReadFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "hello.txt").write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def _call(self, **args):
        return run_read_file(ToolCall(id="c1", name="read_file", args=args), self.root)

    def test_reads_whole_file_shaped(self):
        r = self._call(path="hello.txt")
        self.assertTrue(r.ok)
        self.assertEqual(r.data["total_lines"], 3)
        self.assertEqual(r.data["content"], "alpha\nbeta\ngamma")
        self.assertIsInstance(r.data, dict)          # shaped, never a raw string
        self.assertGreater(r.tokens, 0)

    def test_line_range(self):
        r = self._call(path="hello.txt", start_line=2, end_line=2)
        self.assertTrue(r.ok)
        self.assertEqual(r.data["content"], "beta")
        self.assertEqual((r.data["start_line"], r.data["end_line"]), (2, 2))

    def test_missing_file_is_typed_not_found(self):
        r = self._call(path="nope.txt")
        self.assertFalse(r.ok)
        self.assertEqual(r.error.category, "not_found")

    def test_traversal_blocked(self):
        r = self._call(path="../escape.txt")
        self.assertFalse(r.ok)
        self.assertEqual(r.error.category, "permission")


if __name__ == "__main__":
    unittest.main()
