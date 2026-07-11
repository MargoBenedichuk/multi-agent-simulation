"""Student practice log — the ground truth of what the student actually practiced.

Stored at `students/<student>/student_practice_log.json`, keyed by lesson id:

    {"1": {"lesson": "1", "attempted": "...", "concrete_detail": "...",
            "friction": "...", "outcome": "..."}}

The honest student quotes this via the `practice_read` tool. On a bluff lesson
the orchestrator writes *nothing* here, so `practice_read` returns None and the
student genuinely has no concrete detail to report — the seam a bluffer must
paper over by inventing (and get caught).
"""
from config import load_json, practice_log_path, save_json


def practice_read(student: str, lesson_id=None):
    """Read the practice log. With `lesson_id`, return that lesson's entry or None."""
    data = load_json(practice_log_path(student), {})
    if lesson_id is not None:
        return data.get(str(lesson_id))
    return data


def practice_write(student: str, lesson_id, entry: dict) -> dict:
    """Append/overwrite the practice entry for a lesson and persist."""
    data = load_json(practice_log_path(student), {})
    data[str(lesson_id)] = entry
    save_json(practice_log_path(student), data)
    return entry


def reset(student: str) -> None:
    """Wipe the log (used at the start of a fresh run so bluff lessons stay empty)."""
    save_json(practice_log_path(student), {})
