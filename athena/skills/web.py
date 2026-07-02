"""Web browsing: open known sites and run web searches.

Opens the default browser via Python's `webbrowser` module, which works on
macOS out of the box.
"""

import webbrowser
from urllib.parse import quote_plus

from .base import Skill

# Friendly names Athena recognises for "open <site>".
SITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "maps": "https://maps.google.com",
    "wikipedia": "https://www.wikipedia.org",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "reddit": "https://www.reddit.com",
    "stack overflow": "https://stackoverflow.com",
    "amazon": "https://www.amazon.com",
    "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com",
    "linkedin": "https://www.linkedin.com",
}

SEARCH_PHRASES = ("search for", "search", "google", "look up", "look for", "find")
OPEN_PHRASES = ("open", "go to", "browse", "visit", "take me to")


class WebSkill(Skill):
    name = "web"
    triggers = SEARCH_PHRASES + OPEN_PHRASES

    def handle(self, text: str, athena) -> str | None:
        lowered = text.lower().strip()

        # Web search takes priority ("search for the weather in Paris").
        if any(lowered.startswith(p) or f" {p} " in f" {lowered} " for p in SEARCH_PHRASES):
            query = self.strip_phrases(lowered, SEARCH_PHRASES)
            if not query:
                return "What would you like me to search for?"
            webbrowser.open(f"https://www.google.com/search?q={quote_plus(query)}")
            return f"Searching the web for {query}."

        # Otherwise treat it as "open a site".
        target = self.strip_phrases(lowered, OPEN_PHRASES)
        if not target:
            return "Which site should I open?"

        for name, url in SITES.items():
            if name in target:
                webbrowser.open(url)
                return f"Opening {name}."

        # Fall back to treating the argument as a domain (add .com if bare word).
        domain = target.replace(" dot ", ".").replace(" ", "")
        if "." not in domain:
            domain += ".com"
        webbrowser.open(f"https://{domain}")
        return f"Opening {domain}."
