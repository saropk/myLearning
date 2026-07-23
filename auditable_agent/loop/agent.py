"""L1 — Agent loop.

Send context -> receive tool calls -> execute -> feed results back -> repeat.
Turn budget, cost ceiling, explicit stop condition. Deliberately boring.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config import Config
from ..contracts import Message, Request, ScopeLevel
from ..gateway import Gateway
from ..tools import ToolRegistry


@dataclass
class LoopResult:
    text: str
    turns: int
    cost: float
    stop: str                       # why the loop ended
    files_read: list[str] = field(default_factory=list)


class AgentLoop:
    def __init__(self, gateway: Gateway, tools: ToolRegistry, config: Config):
        self._gateway = gateway
        self._tools = tools
        self._config = config

    def run(self, prompt: str, scope: ScopeLevel | None = None) -> LoopResult:
        scope = scope if scope is not None else self._config.scope
        messages: list[Message] = [Message(role="user", content=prompt)]
        files_read: list[str] = []
        total_cost = 0.0

        for turn in range(1, self._config.max_turns + 1):
            if total_cost >= self._config.max_cost:
                return LoopResult(
                    text="stopped: cost ceiling reached",
                    turns=turn - 1,
                    cost=total_cost,
                    stop="max_cost",
                    files_read=files_read,
                )

            req = Request(
                messages=messages,
                tools=self._tools.available(scope),
                scope=scope,
                max_tokens=self._config.max_tokens,
                model=self._config.model,
                files_included=list(files_read),
            )
            resp = self._gateway.send(req)
            total_cost += resp.usage.cost

            if resp.stop != "tool_use" or not resp.tool_calls:
                return LoopResult(
                    text=resp.text,
                    turns=turn,
                    cost=total_cost,
                    stop=resp.stop,
                    files_read=files_read,
                )

            # Record the assistant's tool-call turn, then execute and feed back.
            messages.append(Message(role="assistant", content=resp.text or "(tool use)"))
            for call in resp.tool_calls:
                result = self._tools.dispatch(call)
                if call.name == "read_file" and result.ok:
                    path = result.data.get("path")
                    if path and path not in files_read:
                        files_read.append(path)
                messages.append(self._tool_message(call, result))

        return LoopResult(
            text="stopped: turn budget exhausted",
            turns=self._config.max_turns,
            cost=total_cost,
            stop="max_turns",
            files_read=files_read,
        )

    @staticmethod
    def _tool_message(call, result) -> Message:
        content = result.data if result.ok else {
            "error": result.error.category if result.error else "unknown",
            "message": result.error.message if result.error else "",
        }
        msg = Message(role="tool", content=content)
        # carry the tool_use id so the adapter can pair result to call
        setattr(msg, "tool_use_id", call.id)
        return msg
