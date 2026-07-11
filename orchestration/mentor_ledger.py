"""Mentor ledger — the mentor's persistent memory about one student.

Stored at `students/<student>/mentor_ledger.json`:

    {
      "student": "default",
      "lessons": {
        "1": {"status": "PASS",
               "weak_spots": ["shaky on why ordering matters"],
               "bluff_flag": false,
               "evidence": "split the email into 3 single-verb prompts",
               "reflection": "almost passed on the first pass alone; the redo detail is what convinced me"}
      }
    }

Two layers of memory live here, both in the same small file:
  - episodic — `lessons[n]` is one dated record of a single lesson's outcome (status,
    evidence, reflection): what happened, tied to that specific episode.
  - semantic — `weak_spots_summary()` distills the episodic records into a general,
    lesson-agnostic fact ("shaky on ordering") that gets re-injected into later lessons'
    briefs, independent of which lesson it was first observed in.

By default this ledger persists across separate `relay.run()` invocations for the same
student (call with `reset_memory=True` for a clean slate) — a student re-taking the
course should have their weak spots recalled, not start from zero every run.

Exposed to the mentor agent as the tools `ledger_read` / `ledger_write`.
"""
from config import load_json, mentor_ledger_path, save_json


def _empty(student: str) -> dict:
    return {"student": student, "lessons": {}}


def ledger_read(student: str) -> dict:
    """Return the full ledger for `student` (empty skeleton if none yet)."""
    data = load_json(mentor_ledger_path(student), _empty(student))
    data.setdefault("student", student)
    data.setdefault("lessons", {})
    return data


def ledger_write(student, lesson_id, status=None, weak_spots=None,
                 evidence=None, bluff_flag=None, reflection=None) -> dict:
    """Update the current lesson's episodic record and persist. Returns the lesson entry."""
    data = ledger_read(student)
    lid = str(lesson_id)
    entry = data["lessons"].get(lid, {})
    if status is not None:
        entry["status"] = status
    if weak_spots is not None:
        entry["weak_spots"] = weak_spots
    if evidence is not None:
        entry["evidence"] = evidence
    if bluff_flag is not None:
        entry["bluff_flag"] = bool(bluff_flag)
    if reflection is not None:
        entry["reflection"] = reflection
    data["lessons"][lid] = entry
    save_json(mentor_ledger_path(student), data)
    return entry


def weak_spots_summary(student: str) -> str:
    """Semantic distillation: one-line recap of weak spots recorded across earlier
    episodic lesson records, for injection into later lessons' prompt recall."""
    data = ledger_read(student)
    bits = []
    for lid in sorted(data["lessons"], key=lambda x: int(x)):
        spots = data["lessons"][lid].get("weak_spots") or []
        if spots:
            bits.append(f"L{lid}: " + "; ".join(spots))
    return " | ".join(bits) if bits else "(none recorded yet)"


def reset(student: str) -> None:
    """Wipe the ledger to an empty skeleton (used at the start of a fresh run)."""
    save_json(mentor_ledger_path(student), _empty(student))
