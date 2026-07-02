"""Athena's brain: turns a command into a spoken reply.

`build_brain` picks the smartest brain available:
  * Claude tool-use brain when an API key is present (understands natural
    language, chains actions), with the keyword brain as an automatic fallback
    if the API errors out.
  * Keyword brain otherwise (fully offline, deterministic).
"""

from .keyword import KeywordBrain


def build_brain(config, skills):
    keyword = KeywordBrain(skills)
    if not config.llm_available:
        print("[brain] No ANTHROPIC_API_KEY — using the offline keyword brain.")
        return keyword
    try:
        from .llm import LLMBrain
        print(f"[brain] Claude brain online ({config.model}).")
        return LLMBrain(config, skills, fallback=keyword)
    except Exception as exc:
        print(f"[brain] Could not start Claude brain ({exc}); using keyword brain.")
        return keyword
