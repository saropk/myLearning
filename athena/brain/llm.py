"""The Claude brain — natural-language understanding plus the ability to act.

Instead of matching keywords, this brain hands Claude the transcript along with
Athena's skills exposed as tools. Claude decides whether to answer directly
(chit-chat, general knowledge) or call one or more tools (get the weather, set a
timer, open an app). Tool results are fed back so Claude can give one natural,
spoken summary — e.g. "Sure, I've muted the volume, and it's 18 degrees and
cloudy in Paris."

Runs a standard manual tool-use loop (see the Anthropic tool-use docs). Uses the
official SDK; the API key comes from ANTHROPIC_API_KEY via the SDK.
"""

import anthropic

from ..util import store

SYSTEM_PROMPT = (
    "You are Athena, a voice assistant named after the Greek goddess of wisdom, "
    "war and strategy. You are speaking out loud, so keep replies to one or two "
    "short, natural sentences. No markdown, lists, emoji or code unless asked. "
    "Use the provided tools to take real actions or fetch live data (time, "
    "weather, news, timers, music, volume, apps, web); for everything else, just "
    "answer directly. When you take an action, confirm it briefly."
)

MAX_TOOL_ITERATIONS = 6   # safety cap on the tool-use loop
MAX_HISTORY = 24          # trim old turns to bound request size


class LLMBrain:
    def __init__(self, config, skills, fallback=None):
        self.config = config
        self.client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
        self.skills = skills
        self.fallback = fallback
        self.history: list[dict] = []
        # Map exposed tool name -> skill, and cache the tool definitions.
        self.tools = []
        self.by_name = {}
        for skill in skills:
            spec = skill.tool_spec()
            if spec:
                self.tools.append(spec)
                self.by_name[spec["name"]] = skill

    def _system(self) -> str:
        """System prompt, augmented with anything the user asked Athena to remember."""
        notes = store.all_notes()
        if not notes:
            return SYSTEM_PROMPT
        remembered = "\n".join(f"- {n}" for n in notes[-20:])
        return f"{SYSTEM_PROMPT}\n\nThings the user asked you to remember:\n{remembered}"

    def respond(self, text: str, athena) -> str:
        text = (text or "").strip()
        if not text:
            return "I didn't catch that. Could you say it again?"

        self.history.append({"role": "user", "content": text})
        try:
            reply = self._run_tool_loop(athena)
        except anthropic.APIError as exc:
            print(f"[llm] API error: {exc}")
            self.history.pop()  # drop the un-answered turn
            if self.fallback is not None:
                return self.fallback.respond(text, athena)
            return f"I had trouble reaching my brain: {exc}"

        self._trim_history()
        return reply

    def _run_tool_loop(self, athena) -> str:
        for _ in range(MAX_TOOL_ITERATIONS):
            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=1024,
                system=self._system(),
                tools=self.tools or anthropic.NOT_GIVEN,
                messages=self.history,
            )
            self.history.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                text = next((b.text for b in response.content if b.type == "text"), "")
                return text or "Done."

            # Execute every tool Claude asked for and return all results together.
            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                skill = self.by_name.get(block.name)
                if skill is None:
                    output = f"Unknown tool: {block.name}"
                else:
                    output = skill.run(athena, **block.input) or "Done."
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output,
                })
            self.history.append({"role": "user", "content": results})

        return "That took more steps than I expected — let's try again."

    def _trim_history(self) -> None:
        if len(self.history) <= MAX_HISTORY:
            return
        # Never start the trimmed history on an assistant/tool_result turn, or the
        # API rejects it. Walk forward to the next user text turn.
        trimmed = self.history[-MAX_HISTORY:]
        while trimmed and not _is_user_text(trimmed[0]):
            trimmed.pop(0)
        self.history = trimmed


def _is_user_text(message: dict) -> bool:
    return message.get("role") == "user" and isinstance(message.get("content"), str)
