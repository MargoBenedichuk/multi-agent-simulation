"""Pytest bootstrap: put the orchestration modules on the path and redirect the
students/ directory to a tmp dir so tests never touch real memory files.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # orchestration/

import pytest  # noqa: E402

import config  # noqa: E402


@pytest.fixture
def student_home(tmp_path, monkeypatch):
    """Point STUDENTS_DIR at a throwaway dir for the duration of a test."""
    home = tmp_path / "students"
    monkeypatch.setattr(config, "STUDENTS_DIR", home)
    return home
