"""Built-in skills — the fast, rule-based commands Athena handles directly.

`build_skills()` returns them in priority order (first match wins in the router).
"""

from .smalltalk import SmallTalkSkill
from .time_date import TimeDateSkill
from .music import MusicSkill
from .system import SystemSkill
from .web import WebSkill
from .wikipedia_skill import WikipediaSkill


def build_skills():
    return [
        SmallTalkSkill(),   # greetings, identity, jokes, goodbye
        TimeDateSkill(),    # time / date / day
        MusicSkill(),       # play songs, pause, next
        SystemSkill(),      # open apps, control volume (macOS)
        WebSkill(),         # open sites, web search
        WikipediaSkill(),   # quick factual lookups ("who is ...")
    ]
