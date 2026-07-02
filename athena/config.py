"""Central configuration for Athena.

Everything is overridable through environment variables so you never have to
edit code to tweak behaviour. Copy .env.example to .env and adjust.
"""

import os
from dataclasses import dataclass, field


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    # Identity
    assistant_name: str = os.getenv("ATHENA_NAME", "Athena")
    owner_name: str = os.getenv("ATHENA_OWNER", "Saro")
    wake_word: str = os.getenv("ATHENA_WAKE_WORD", "athena").lower()

    # Voice (speaking) — macOS ships "Samantha", a natural female voice.
    voice_name: str = os.getenv("ATHENA_VOICE", "Samantha")
    speech_rate: int = int(os.getenv("ATHENA_SPEECH_RATE", "180"))

    # Listening (speech-to-text) — cloud Google recogniser via SpeechRecognition.
    energy_threshold: int = int(os.getenv("ATHENA_ENERGY_THRESHOLD", "300"))
    pause_threshold: float = float(os.getenv("ATHENA_PAUSE_THRESHOLD", "0.8"))
    # Seconds to keep listening for a follow-up before needing the wake word again.
    follow_up_timeout: int = int(os.getenv("ATHENA_FOLLOW_UP_TIMEOUT", "7"))

    # Brain — the Claude model used for open-ended questions.
    # Only used when ANTHROPIC_API_KEY is set; otherwise Athena stays rule-based.
    model: str = os.getenv("ATHENA_MODEL", "claude-opus-4-8")
    use_llm: bool = field(default_factory=lambda: _env_bool("ATHENA_USE_LLM", True))

    @property
    def llm_available(self) -> bool:
        """True when we have both the flag on and an API key present."""
        return self.use_llm and bool(os.getenv("ANTHROPIC_API_KEY"))
