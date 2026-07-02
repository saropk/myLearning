"""Entry point so you can run Athena with `python -m athena`.

    python -m athena          # voice mode (needs a microphone)
    python -m athena --text   # keyboard mode (great for testing)
"""

import argparse

from .assistant import Athena


def main() -> None:
    parser = argparse.ArgumentParser(description="Athena — a voice assistant.")
    parser.add_argument(
        "--text",
        action="store_true",
        help="Type commands instead of speaking (no microphone needed).",
    )
    args = parser.parse_args()

    athena = Athena(text_mode=args.text)
    if args.text:
        athena.run_text()
    else:
        athena.run_voice()


if __name__ == "__main__":
    main()
