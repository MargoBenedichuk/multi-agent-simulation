"""OpenAI tool (function-calling) schemas and a dispatcher.

The mentor and student agents get different tool sets. `dispatch` executes a
tool call against the current run context (`rc`), which carries the student name
and the per-lesson `AdvanceDecision` holder.
"""
from mentor_ledger import ledger_read, ledger_write
from student_practice_log import practice_read

MENTOR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "ledger_read",
            "description": "Read your ledger about this student, including weak_spots recorded in earlier lessons.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ledger_write",
            "description": "Record what you learned about the student on the current lesson.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "PASS / BLUFF_SUSPECTED / in_progress"},
                    "weak_spots": {"type": "array", "items": {"type": "string"},
                                    "description": "Short phrases naming what the student was shaky on."},
                    "evidence": {"type": "string", "description": "The concrete thing the student said that supports your read."},
                    "bluff_flag": {"type": "boolean", "description": "True if you suspect the student did not actually practice."},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "advance_decision",
            "description": "End the lesson with your verdict, once you have enough evidence. If you are not "
                           "ready to decide, ask another follow-up question instead of calling this.",
            "parameters": {
                "type": "object",
                "properties": {
                    "verdict": {"type": "string", "enum": ["PASS", "BLUFF_SUSPECTED"]},
                    "reason": {"type": "string", "description": "One sentence justifying the verdict."},
                    "weak_spots": {"type": "array", "items": {"type": "string"},
                                    "description": "1-2 short phrases naming what the student was shaky on, for recall in later lessons."},
                    "reflection": {"type": "string",
                                    "description": "Optional: one sentence on what almost got missed, or what "
                                                    "specific answer tipped your judgment — a self-check on your "
                                                    "own reasoning, not a restatement of the reason."},
                },
                "required": ["verdict"],
                "additionalProperties": False,
            },
        },
    },
]

# During the lesson dialogue the mentor gets ledger tools only; advance_decision is
# reserved for the forced gate at the end so a structured verdict is always recorded.
MENTOR_PHASE_TOOLS = [t for t in MENTOR_TOOLS if t["function"]["name"] != "advance_decision"]

STUDENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "practice_read",
            "description": "Recall what you actually practiced for a lesson. Returns null if you did not practice it — in which case you have NO concrete details to report.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lesson_id": {"type": ["string", "integer"], "description": "The lesson number to recall."},
                },
                "additionalProperties": False,
            },
        },
    },
]


def dispatch(name: str, args: dict, rc) -> dict:
    """Execute a tool call and return a JSON-serialisable result."""
    if name == "ledger_read":
        return ledger_read(rc.student)
    if name == "ledger_write":
        return ledger_write(rc.student, rc.lesson_id, **args)
    if name == "advance_decision":
        return rc.decision.record(args.get("verdict"), args.get("reason", ""),
                                  args.get("weak_spots"), args.get("reflection", ""))
    if name == "practice_read":
        lesson_id = args.get("lesson_id", rc.lesson_id)
        entry = practice_read(rc.student, lesson_id)
        return {"lesson_id": str(lesson_id), "practiced": entry is not None, "entry": entry}
    raise ValueError(f"unknown tool: {name}")
