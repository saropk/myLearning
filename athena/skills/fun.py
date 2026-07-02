"""Coin flips, dice rolls and random numbers. Offline keyword brain only."""

import random
import re

from .base import Skill


class FunSkill(Skill):
    name = "fun"
    triggers = ("flip a coin", "coin toss", "roll a dice", "roll a die",
                "roll the dice", "random number")

    def run(self, athena, **params) -> str | None:
        text = params.get("_text", "").lower()
        if "coin" in text:
            return f"It's {random.choice(['heads', 'tails'])}."
        if "dice" in text or "die" in text:
            return f"You rolled a {random.randint(1, 6)}."
        if "random number" in text:
            lo, hi = 1, 100
            nums = re.findall(r"\d+", text)
            if len(nums) >= 2:
                lo, hi = int(nums[0]), int(nums[1])
                if lo > hi:
                    lo, hi = hi, lo
            return f"Your number is {random.randint(lo, hi)}."
        return None

    def parse(self, text: str) -> dict | None:
        if self.can_handle(text):
            return {"_text": text}
        return None
