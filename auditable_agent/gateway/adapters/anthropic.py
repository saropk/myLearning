"""Real provider adapter — Anthropic Messages API.

This is the ONLY place in the codebase that touches the network. It uses the
standard library (urllib) so the project has zero runtime dependencies; urllib
honours HTTPS_PROXY/HTTP_PROXY from the environment automatically.

No provider exception escapes: failures come back as Response(stop="refusal")
with the error text, so the loop above stays provider-agnostic (§3a step 4).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from ...contracts import Message, Request, Response, ToolCall, Usage

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"

# USD per million tokens. A config table, not logic — cheap to change (§4).
_PRICE = {
    "input": 3.0 / 1_000_000,
    "output": 15.0 / 1_000_000,
}


class AnthropicAdapter:
    name = "anthropic"

    def complete(self, req: Request) -> Response:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            return Response(
                text="ANTHROPIC_API_KEY is not set.",
                tool_calls=[],
                usage=Usage(),
                stop="refusal",
            )

        body = {
            "model": req.model or "claude-sonnet-5",
            "max_tokens": req.max_tokens,
            "messages": [self._msg(m) for m in req.messages],
            "tools": [self._tool(t) for t in req.tools],
        }
        data = json.dumps(body).encode()
        http_req = urllib.request.Request(
            _API_URL,
            data=data,
            headers={
                "content-type": "application/json",
                "x-api-key": key,
                "anthropic-version": _API_VERSION,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(http_req, timeout=120) as resp:
                parsed = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            return Response(
                text=f"provider HTTP {e.code}: {detail}",
                tool_calls=[],
                usage=Usage(),
                stop="refusal",
            )
        except (urllib.error.URLError, TimeoutError) as e:
            return Response(
                text=f"provider unreachable: {e}",
                tool_calls=[],
                usage=Usage(),
                stop="refusal",
            )

        return self._to_response(parsed)

    # --- provider format translation (private to this adapter) -------------

    @staticmethod
    def _msg(m: Message) -> dict:
        if m.role == "tool":
            # tool result -> a user turn carrying a tool_result block
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": getattr(m, "tool_use_id", "call_1"),
                        "content": json.dumps(m.content),
                    }
                ],
            }
        return {"role": m.role, "content": m.content}

    @staticmethod
    def _tool(t) -> dict:
        return {"name": t.name, "description": t.description, "input_schema": t.params}

    @staticmethod
    def _to_response(parsed: dict) -> Response:
        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for block in parsed.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                calls.append(
                    ToolCall(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        args=block.get("input", {}) or {},
                    )
                )

        u = parsed.get("usage", {})
        input_tok = u.get("input_tokens", 0)
        output_tok = u.get("output_tokens", 0)
        usage = Usage(
            input=input_tok,
            output=output_tok,
            cost=input_tok * _PRICE["input"] + output_tok * _PRICE["output"],
        )

        raw_stop = parsed.get("stop_reason", "end_turn")
        stop = {
            "end_turn": "end",
            "tool_use": "tool_use",
            "max_tokens": "max_tokens",
        }.get(raw_stop, "end")
        return Response(text="".join(text_parts), tool_calls=calls, usage=usage, stop=stop)
