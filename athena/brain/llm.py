"""Claude fallback — Athena's reasoning brain for open-ended questions.

Anything the built-in skills can't handle (general knowledge, explanations,
advice, chit-chat) is sent to Claude. Responses are kept short because they are
meant to be spoken aloud. Conversation history is retained so follow-up
questions ("and what about tomorrow?") keep their context.

Uses the official Anthropic SDK. The API key is read from the ANTHROPIC_API_KEY
environment variable by the SDK itself — never hard-code it.
"""

try:
    import anthropic
except ImportError:  # pragma: no cover - optional at runtime
    anthropic = None


SYSTEM_PROMPT = (
    "You are Athena, a voice assistant named after the Greek goddess of wisdom, "
    "war and strategy. You are speaking out loud, so keep answers to one to three "
    "short sentences. Be warm, direct and helpful. Do not use markdown, bullet "
    "points, emoji or code blocks unless the user explicitly asks for them — the "
    "text is read aloud by a speech engine."
)

# Keep the last N messages (user + assistant) so context stays but the request
# doesn't grow without bound during a long session.
MAX_HISTORY = 20


class LLM:
    def __init__(self, model: str, system: str = SYSTEM_PROMPT):
        if anthropic is None:
            raise RuntimeError(
                "The 'anthropic' package isn't installed. Run `pip install anthropic`."
            )
        self.client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        self.model = model
        self.system = system
        self.history: list[dict] = []

    def ask(self, text: str) -> str:
        self.history.append({"role": "user", "content": text})
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=self.system,
                messages=self.history,
            )
        except anthropic.APIError as exc:
            # Roll back the un-answered user turn so history stays consistent.
            self.history.pop()
            return f"I had trouble reaching my brain right now: {exc}"

        reply = next((b.text for b in response.content if b.type == "text"), "")
        self.history.append({"role": "assistant", "content": reply})
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]
        return reply or "I'm not sure how to answer that."
