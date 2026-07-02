"""Latest headlines via the Google News RSS feed (no API key needed).

Fetches the feed, parses the XML with the standard library, and reads out the
top few titles. An optional topic switches to a targeted search feed.
"""

import re
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

from .base import Skill
from ..util import http

TOP_FEED = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
SEARCH_FEED = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


class NewsSkill(Skill):
    name = "get_news"
    triggers = ("news", "headlines", "what's happening", "whats happening")

    expose = True
    description = "Read the latest news headlines, optionally about a topic."
    parameters = {
        "topic": {"type": "string", "description": "Optional subject, e.g. 'technology'."}
    }

    def run(self, athena, topic: str | None = None, count: int = 4) -> str:
        topic = (topic or "").strip()
        url = SEARCH_FEED.format(q=quote_plus(topic)) if topic else TOP_FEED

        body = http.get_text(url)
        if not body:
            return "I couldn't reach the news service right now."
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            return "The news feed came back in a format I couldn't read."

        titles = [
            self._clean(item.findtext("title", ""))
            for item in root.iter("item")
        ]
        titles = [t for t in titles if t][:count]
        if not titles:
            subject = f" about {topic}" if topic else ""
            return f"I didn't find any headlines{subject}."

        subject = f" on {topic}" if topic else ""
        lead = f"Here are the top headlines{subject}: "
        return lead + " ... ".join(titles) + "."

    @staticmethod
    def _clean(title: str) -> str:
        # Google News appends " - Source"; drop it for smoother speech.
        return re.sub(r"\s+-\s+[^-]+$", "", title).strip()

    def parse(self, text: str) -> dict | None:
        if not self.can_handle(text):
            return None
        match = re.search(r"\b(?:about|on)\s+(.+)$", text.lower())
        topic = match.group(1).strip(" ?.") if match else ""
        return {"topic": topic}
