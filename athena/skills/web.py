"""Web actions: run a search, or open a known website.

Two separate skills so Claude gets two clear, single-purpose tools.
"""

import webbrowser
from urllib.parse import quote_plus

from .base import Skill

SEARCH_PHRASES = ("search for", "search", "google", "look up", "look for")
OPEN_PHRASES = ("open", "go to", "browse", "visit", "take me to")

SITES = {
    "youtube": "https://www.youtube.com", "google": "https://www.google.com",
    "gmail": "https://mail.google.com", "github": "https://github.com",
    "maps": "https://maps.google.com", "wikipedia": "https://www.wikipedia.org",
    "twitter": "https://twitter.com", "x": "https://x.com",
    "reddit": "https://www.reddit.com", "stack overflow": "https://stackoverflow.com",
    "amazon": "https://www.amazon.com", "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com", "linkedin": "https://www.linkedin.com",
}


class WebSearchSkill(Skill):
    name = "web_search"
    triggers = SEARCH_PHRASES

    expose = True
    description = "Search the web for a query and open the results in the browser."
    parameters = {"query": {"type": "string", "description": "What to search for."}}
    required = ("query",)

    def run(self, athena, query: str = "") -> str:
        query = query.strip()
        if not query:
            return "What would you like me to search for?"
        webbrowser.open(f"https://www.google.com/search?q={quote_plus(query)}")
        return f"Searching the web for {query}."

    def parse(self, text: str) -> dict | None:
        lowered = text.lower().strip()
        if not any(lowered.startswith(p) or f" {p} " in f" {lowered} " for p in SEARCH_PHRASES):
            return None
        query = self.strip_phrases(lowered, SEARCH_PHRASES)
        return {"query": query} if query else None


class OpenSiteSkill(Skill):
    name = "open_website"
    triggers = OPEN_PHRASES

    expose = True
    description = "Open a website by name (YouTube, GitHub, ...) or by domain."
    parameters = {"site": {"type": "string", "description": "Site name or domain."}}
    required = ("site",)

    def run(self, athena, site: str = "") -> str | None:
        site = site.strip().lower()
        if not site:
            return None
        for name, url in SITES.items():
            if name in site:
                webbrowser.open(url)
                return f"Opening {name}."
        domain = site.replace(" dot ", ".").replace(" ", "")
        if "." not in domain:
            domain += ".com"
        webbrowser.open(f"https://{domain}")
        return f"Opening {domain}."

    def parse(self, text: str) -> dict | None:
        # Only claim the command if it actually starts with an "open" phrase —
        # otherwise this skill would greedily treat any sentence as a website.
        lowered = text.lower().strip()
        if not any(lowered.startswith(p) for p in OPEN_PHRASES):
            return None
        target = self.strip_phrases(lowered, OPEN_PHRASES)
        return {"site": target} if target else None
