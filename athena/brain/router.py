"""The router — Athena's decision layer.

For every command it walks the list of skills in order and lets the first one
that claims the command handle it. Skills are fast, deterministic and free.
If no skill matches (or a skill declines by returning None), the command is
handed to Claude for an open-ended answer.
"""


class Brain:
    def __init__(self, skills, llm=None):
        self.skills = skills
        self.llm = llm

    def respond(self, text: str, athena) -> str:
        text = (text or "").strip()
        if not text:
            return "I didn't catch that. Could you say it again?"

        for skill in self.skills:
            try:
                if skill.can_handle(text):
                    reply = skill.handle(text, athena)
                    if reply is not None:
                        return reply
            except Exception as exc:  # one broken skill shouldn't take Athena down
                print(f"[brain] Skill '{skill.name}' error: {exc}")

        if self.llm is not None:
            return self.llm.ask(text)

        return (
            "I don't have a skill for that yet, and my Claude brain is offline. "
            "Set ANTHROPIC_API_KEY to let me answer open-ended questions."
        )
