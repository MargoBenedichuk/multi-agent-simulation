"""Thin factory for an OpenAI-compatible client.

Uses the official `openai` SDK, so pointing at any OpenAI-compatible endpoint
(OpenAI itself, OpenRouter, a cluster vLLM server, a local model) is just a
matter of `OPENAI_API_KEY` + `OPENAI_BASE_URL` + `MODEL` in the environment.
Kept separate from `relay.py` so the loop can be driven by a fake client in
tests without importing the SDK.
"""
import os

from config import OPENAI_BASE_URL


def make_client():
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "The `openai` package is required for live runs. "
            "Install it with `pip install -r requirements.txt`."
        ) from exc

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy orchestration/.env.example to "
            "orchestration/.env and fill it in."
        )

    kwargs = {"api_key": api_key}
    if OPENAI_BASE_URL:
        kwargs["base_url"] = OPENAI_BASE_URL
    return OpenAI(**kwargs)
