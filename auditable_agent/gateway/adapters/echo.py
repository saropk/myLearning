"""Offline adapter — no network. Level 0 in spirit; the spine's test double.

Deterministic behaviour so the whole loop runs end-to-end without API keys:

  * If the conversation already contains a tool result, answer in plain text
    using that result and stop.
  * Otherwise, if the latest user message references a file path and a
    read_file tool is offered, emit a read_file tool call.
  * Otherwise, echo.

This is enough to satisfy Chunk 1's "read a file and answer a question about
it" offline, and to exercise the gateway/audit/loop plumbing in tests.
"""

from __future__ import annotations

import re

from ...contracts import Message, Request, Response, ToolCall, Usage

_PATH_RE = re.compile(r"[\w./\-]+\.[A-Za-z0-9]+")


class EchoAdapter:
    name = "echo"

    def complete(self, req: Request) -> Response:
        tool_names = {t.name for t in req.tools}
        has_tool_result = any(m.role == "tool" for m in req.messages)

        if has_tool_result:
            summary = self._summarize(req.messages)
            return Response(text=summary, tool_calls=[], usage=Usage(), stop="end")

        last_user = next(
            (m for m in reversed(req.messages) if m.role == "user"), None
        )
        if last_user and "read_file" in tool_names:
            text = last_user.content if isinstance(last_user.content, str) else ""
            match = _PATH_RE.search(text)
            if match:
                call = ToolCall(
                    id="call_1",
                    name="read_file",
                    args={"path": match.group(0)},
                )
                return Response(text="", tool_calls=[call], usage=Usage(), stop="tool_use")

        content = last_user.content if last_user else ""
        return Response(text=f"(echo) {content}", tool_calls=[], usage=Usage(), stop="end")

    @staticmethod
    def _summarize(messages: list[Message]) -> str:
        tool_msg = next((m for m in reversed(messages) if m.role == "tool"), None)
        data = getattr(tool_msg, "content", None)
        if isinstance(data, dict) and "content" in data:
            total = data.get("total_lines", "?")
            path = data.get("path", "the file")
            first = (data["content"].splitlines() or [""])[0]
            return (
                f"{path} has {total} lines. Its first line is: {first!r}. "
                f"(Answered offline by the echo adapter.)"
            )
        return "Read the file, but its result was not in the expected shape."
