"""Shared configuration and path resolution for the mentor-student simulation.

Everything is resolved relative to the repository root (the parent of this
`orchestration/` directory) so the tools work the same whether you run
`python relay.py` from inside `orchestration/` or `python orchestration/relay.py`
from the repo root.
"""
import json
import os
from pathlib import Path

try:  # best-effort .env loading; tools still import fine without python-dotenv
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / "orchestration" / ".env")
    load_dotenv()  # also honour a .env in the current working directory
except Exception:  # pragma: no cover - dotenv is optional
    pass

# --- paths ---------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
COURSES_DIR = REPO_ROOT / "courses"
STUDENTS_DIR = REPO_ROOT / "students"
PROMPTS_DIR = REPO_ROOT / "prompts"

# --- model / run defaults (env-overridable) ------------------------------
# MODEL lets a teammate point at any OpenAI-compatible endpoint (a cluster
# vLLM server, a local model, ...) together with OPENAI_BASE_URL, without
# touching the code.
DEFAULT_MODEL = os.environ.get("MODEL", "gpt-4o-mini")
# Mentor and student can run on different models (e.g. a strong prober for the
# mentor, a cheaper/more-stable model for the student). Each falls back to MODEL.
DEFAULT_MENTOR_MODEL = os.environ.get("MENTOR_MODEL") or DEFAULT_MODEL
DEFAULT_STUDENT_MODEL = os.environ.get("STUDENT_MODEL") or DEFAULT_MODEL
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL") or None
DEFAULT_MAX_EXCHANGES = int(os.environ.get("MAX_EXCHANGES", "6"))
DEFAULT_SEED = int(os.environ.get("SEED", "7"))


def course_dir(course: str) -> Path:
    return COURSES_DIR / course


def student_dir(student: str) -> Path:
    return STUDENTS_DIR / student


def mentor_ledger_path(student: str) -> Path:
    return student_dir(student) / "mentor_ledger.json"


def practice_log_path(student: str) -> Path:
    return student_dir(student) / "student_practice_log.json"


def course_design_path(course: str) -> Path:
    return course_dir(course) / "course_design.md"


def answer_key_path(course: str) -> Path:
    return course_dir(course) / "answer_key.json"


def bluff_schedule_path(course: str) -> Path:
    return course_dir(course) / "bluff_schedule.json"


def logs_dir(course: str) -> Path:
    return course_dir(course) / "logs"


# --- shared JSON persistence ----------------------------------------------
def load_json(path: Path, default: dict) -> dict:
    """Read a JSON file, or return `default` if it doesn't exist yet / is empty."""
    if not path.exists():
        return dict(default)
    raw = path.read_text(encoding="utf-8").strip()
    return json.loads(raw) if raw else dict(default)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
