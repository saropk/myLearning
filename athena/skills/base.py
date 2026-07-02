"""Base class shared by every skill — now with a unified, two-path interface.

A skill can be reached two ways:

  * Tool-use path (when Claude is the brain): Claude reads `tool_spec()` and
    calls `run(athena, **params)` with structured arguments it extracted.
  * Keyword path (offline / no API key): `parse(text)` pulls arguments out of
    the raw transcript, then the same `run()` executes them.

Both paths funnel into `run()`, so the actual behaviour lives in exactly one
place. `run()` returns the sentence Athena should say (or None to decline).

Set `expose = True` (plus `description`/`parameters`) to make a skill callable
by Claude. Skills that Claude can already do itself (chit-chat, general facts,
mental math) stay `expose = False` and only serve the offline keyword path.
"""


class Skill:
    name: str = "skill"
    triggers: tuple[str, ...] = ()

    # Tool-use metadata (only used when expose is True)
    expose: bool = False
    description: str = ""
    parameters: dict = {}          # JSON-schema "properties"
    required: tuple[str, ...] = ()

    # ---- tool-use path ----------------------------------------------------
    def tool_spec(self) -> dict | None:
        """Anthropic tool definition, or None to hide this skill from Claude."""
        if not self.expose:
            return None
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": self.parameters,
                "required": list(self.required),
            },
        }

    # ---- keyword path -----------------------------------------------------
    def parse(self, text: str) -> dict | None:
        """Extract run() kwargs from raw text, or None if this isn't my command.

        Default: match on `triggers` and pass no arguments. Skills that need
        arguments (a location, an expression, ...) override this.
        """
        if self.can_handle(text):
            return {}
        return None

    def can_handle(self, text: str) -> bool:
        text = text.lower()
        return any(trigger in text for trigger in self.triggers)

    # ---- shared behaviour -------------------------------------------------
    def run(self, athena, **params) -> str | None:
        raise NotImplementedError

    # ---- helpers ----------------------------------------------------------
    @staticmethod
    def strip_phrases(text: str, phrases) -> str:
        cleaned = text.lower().strip()
        for phrase in sorted(phrases, key=len, reverse=True):
            if cleaned.startswith(phrase):
                return cleaned[len(phrase):].strip()
        return cleaned
