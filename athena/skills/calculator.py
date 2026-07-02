"""Arithmetic. Hidden from Claude (it does mental math fine); serves the offline
keyword brain.

Safe: expressions are evaluated by walking a parsed AST, so only arithmetic is
allowed — never arbitrary code via eval().
"""

import ast
import operator
import re

from .base import Skill

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow, ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

WORD_TO_SYMBOL = [
    (r"\bplus\b", "+"), (r"\bminus\b", "-"),
    (r"\btimes\b", "*"), (r"\bmultiplied by\b", "*"),
    (r"\bdivided by\b", "/"), (r"\bover\b", "/"),
    (r"\bto the power of\b", "**"), (r"\bpercent of\b", "*0.01*"),
]


def _safe_eval(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("non-numeric constant")
    if isinstance(node, ast.BinOp):
        return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        return _OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("unsupported expression")


class CalculatorSkill(Skill):
    name = "calculator"
    triggers = ("calculate", "what is", "what's", "how much is", "plus",
                "minus", "times", "divided by")

    def run(self, athena, expression: str = "") -> str | None:
        expression = expression.strip()
        if not expression:
            return None
        try:
            value = _safe_eval(ast.parse(expression, mode="eval").body)
        except Exception:
            return None  # not a real sum — let another skill or Claude try
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        elif isinstance(value, float):
            value = round(value, 4)
        return f"That's {value}."

    def parse(self, text: str) -> dict | None:
        lowered = text.lower()
        expr = self.strip_phrases(lowered, ("calculate", "what is", "what's", "how much is"))
        for pattern, symbol in WORD_TO_SYMBOL:
            expr = re.sub(pattern, symbol, expr)
        expr = expr.replace("^", "**").replace("x", "*")
        expr = re.sub(r"[^0-9+\-*/%.()\s]", "", expr).strip()
        # Only claim it if it actually looks like arithmetic (a digit and an operator).
        if not re.search(r"\d", expr) or not re.search(r"[+\-*/%]", expr):
            return None
        return {"expression": expr}
