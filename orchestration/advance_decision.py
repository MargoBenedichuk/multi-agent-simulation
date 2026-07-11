"""Advance decision — the mentor's hard gate at the end of a lesson.

The mentor calls the `advance_decision` tool once it has enough evidence, with one of:

    PASS             the student genuinely applied the skill
    BLUFF_SUSPECTED  smooth report but specifics missing, generic, or invented

There is no RETRY verdict: "not yet convinced" is expressed by asking another
follow-up in the adaptive probe, not by a verdict. `relay.py` records the verdict
and advances (a caught bluff still advances so the whole course runs).
"""

VALID_VERDICTS = ("PASS", "BLUFF_SUSPECTED")


def validate(verdict: str) -> str:
    v = str(verdict).strip().upper()
    if v not in VALID_VERDICTS:
        raise ValueError(f"invalid verdict {verdict!r}; expected one of {VALID_VERDICTS}")
    return v


class AdvanceDecision:
    """Per-lesson holder for the mentor's gate verdict."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.verdict = None
        self.reason = ""
        self.weak_spots = []
        self.reflection = ""

    def record(self, verdict: str, reason: str = "", weak_spots=None, reflection: str = "") -> dict:
        self.verdict = validate(verdict)
        self.reason = reason or ""
        self.weak_spots = list(weak_spots) if weak_spots else []
        self.reflection = reflection or ""
        return {"ok": True, "verdict": self.verdict, "reason": self.reason,
                "weak_spots": self.weak_spots, "reflection": self.reflection}
