"""Built-in skills.

`build_skills()` returns them in priority order — which matters for the offline
keyword brain (first match wins). The Claude brain ignores order and picks tools
by their descriptions.
"""

from .smalltalk import SmallTalkSkill
from .time_date import TimeDateSkill
from .weather import WeatherSkill
from .news import NewsSkill
from .timer import TimerSkill
from .memory import MemorySkill
from .calculator import CalculatorSkill
from .music import MusicSkill
from .volume import VolumeSkill
from .open_app import OpenAppSkill
from .web import WebSearchSkill, OpenSiteSkill
from .wikipedia_skill import WikipediaSkill
from .fun import FunSkill


def build_skills():
    return [
        SmallTalkSkill(),    # greetings, identity, jokes
        TimeDateSkill(),     # time / date / day
        WeatherSkill(),      # live weather
        NewsSkill(),         # live headlines
        TimerSkill(),        # countdown timers
        MemorySkill(),       # remember / recall facts
        CalculatorSkill(),   # arithmetic (before wikipedia's "what is")
        MusicSkill(),        # play / control music
        VolumeSkill(),       # system volume
        OpenAppSkill(),      # launch apps (before opening sites)
        WebSearchSkill(),    # web search
        OpenSiteSkill(),     # open websites
        WikipediaSkill(),    # factual lookups
        FunSkill(),          # coin flip / dice / random
    ]
