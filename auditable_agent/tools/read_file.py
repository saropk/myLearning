"""L2 — read_file. The only tool in Chunk 1.

Returns shaped data ({path, content, line range, total_lines}), never a raw
string (§3a hard rule). Failures carry an L4 FailureCategory.
"""

from __future__ import annotations

from pathlib import Path

from ..contracts import ScopeLevel, ToolCall, ToolDef, ToolError, ToolResult

read_file_def = ToolDef(
    name="read_file",
    description="Read a UTF-8 text file, optionally a line range. Returns "
    "content plus the line range and total line count.",
    params={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path, relative to repo root."},
            "start_line": {"type": "integer", "description": "1-indexed, inclusive."},
            "end_line": {"type": "integer", "description": "1-indexed, inclusive."},
        },
        "required": ["path"],
    },
    scope=ScopeLevel.SCOPED,   # opening a named file is Level 1+
    mutating=False,
)


def _estimate_tokens(text: str) -> int:
    # Cheap heuristic; a real tokenizer belongs behind the adapter seam.
    return max(1, len(text) // 4)


def run_read_file(call: ToolCall, root: Path) -> ToolResult:
    args = call.args
    rel = args.get("path", "")
    target = (root / rel).resolve()

    # Contain reads to the repo root — no traversal outside it.
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return ToolResult(
            id=call.id,
            ok=False,
            data=None,
            error=ToolError("permission", f"path escapes repo root: {rel!r}"),
        )

    if not target.exists():
        return ToolResult(
            id=call.id,
            ok=False,
            data=None,
            error=ToolError("not_found", f"no such file: {rel!r}"),
        )
    if not target.is_file():
        return ToolResult(
            id=call.id,
            ok=False,
            data=None,
            error=ToolError("not_found", f"not a file: {rel!r}"),
        )

    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return ToolResult(
            id=call.id,
            ok=False,
            data=None,
            error=ToolError("permission", f"cannot read {rel!r}: {e}"),
        )

    lines = text.splitlines()
    total = len(lines)
    start = args.get("start_line")
    end = args.get("end_line")
    if start is not None or end is not None:
        s = max(1, start or 1)
        e = min(total, end or total)
        content = "\n".join(lines[s - 1 : e])
        start_out, end_out = s, e
    else:
        content = "\n".join(lines)
        start_out, end_out = (1 if total else 0), total

    return ToolResult(
        id=call.id,
        ok=True,
        data={
            "path": rel,
            "content": content,
            "start_line": start_out,
            "end_line": end_out,
            "total_lines": total,
        },
        tokens=_estimate_tokens(content),
    )
