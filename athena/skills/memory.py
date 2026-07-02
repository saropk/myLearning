"""Persistent memory: things Athena should remember between sessions.

Stored in ~/.athena/memory.json. Also surfaced to the Claude brain (see
brain/llm.py) so it can use remembered facts when answering.
"""

import re

from .base import Skill
from ..util import store


class MemorySkill(Skill):
    name = "remember"
    triggers = ("remember", "note that", "don't forget", "what do you remember",
                "what did i ask you to remember")

    expose = True
    description = (
        "Save a fact to long-term memory, or recall previously saved facts."
    )
    parameters = {
        "action": {"type": "string", "enum": ["save", "recall"]},
        "text": {"type": "string", "description": "The fact to save (for 'save')."},
    }
    required = ("action",)

    def run(self, athena, action: str = "save", text: str | None = None) -> str:
        if action == "recall":
            notes = store.all_notes()
            if not notes:
                return "You haven't asked me to remember anything yet."
            return "Here's what I remember: " + "; ".join(notes[-10:]) + "."

        text = (text or "").strip()
        if not text:
            return "What would you like me to remember?"
        store.add_note(text)
        return "Got it, I'll remember that."

    def parse(self, text: str) -> dict | None:
        lowered = text.lower().strip()
        if "what do you remember" in lowered or "what did i ask you to remember" in lowered:
            return {"action": "recall"}
        match = re.match(r"(?:remember|note)(?:\s+that)?\s+(.+)$", lowered)
        if match:
            return {"action": "save", "text": match.group(1).strip(" .?")}
        if "don't forget" in lowered:
            fact = lowered.split("don't forget", 1)[1].lstrip(" that").strip(" .?")
            return {"action": "save", "text": fact} if fact else None
        return None
