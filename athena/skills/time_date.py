"""Current time, date and day of the week.

Exposed to Claude because the model has no idea what the real current time is —
it must call this tool rather than guess.
"""

import re
from datetime import datetime

from .base import Skill


class TimeDateSkill(Skill):
    name = "get_datetime"
    triggers = ("time", "date", "day", "today")

    expose = True
    description = "Get the current local time, today's date, or the day of the week."
    parameters = {
        "what": {
            "type": "string",
            "enum": ["time", "date", "day"],
            "description": "Which piece of information to return.",
        }
    }

    def run(self, athena, what: str = "date") -> str:
        now = datetime.now()
        if what == "time":
            return f"It's {now.strftime('%I:%M %p').lstrip('0')}."
        if what == "day":
            return f"Today is {now.strftime('%A')}."
        return f"Today is {now.strftime('%A, %B %d, %Y')}."

    def parse(self, text: str) -> dict | None:
        # Whole-word matching so "times" / "timer" don't look like "time".
        text = text.lower()
        if re.search(r"\btime\b", text):
            return {"what": "time"}
        if re.search(r"\bday\b", text) and not re.search(r"\bdate\b", text):
            return {"what": "day"}
        if re.search(r"\bdate\b", text) or re.search(r"\btoday\b", text):
            return {"what": "date"}
        return None
