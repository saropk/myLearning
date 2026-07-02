"""Time and date."""

from datetime import datetime

from .base import Skill


class TimeDateSkill(Skill):
    name = "time_date"
    triggers = ("time", "date", "day", "today")

    def handle(self, text: str, athena) -> str | None:
        now = datetime.now()
        if "time" in text:
            return f"It's {now.strftime('%I:%M %p').lstrip('0')}."
        if "day" in text and "today" in text or text.strip() in {"what day is it", "day"}:
            return f"Today is {now.strftime('%A')}."
        if "date" in text or "today" in text or "day" in text:
            return f"Today is {now.strftime('%A, %B %d, %Y')}."
        return None
