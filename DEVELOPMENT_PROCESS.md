# Development Process — MVP build (Roles 2, 3, 4 + tests)

Status of the build after the first implementation pass. Design (Role 1) was already done; this pass makes the simulation actually run end to end.

## What's implemented

| Role | Deliverable | Status |
|------|-------------|--------|
| 1 — Course Designer | `course_design.md`, `answer_key.json`, `bluff_schedule.json` | Done (pre-existing) |
| 2 — Mentor Prompt | `prompts/mentor/current.txt` (+ `README.md`, `versions/v1,v2`) | **Done** |
| 3 — Student Prompt | `prompts/student/current.txt` (+ `README.md`, `versions/v1,v2`) | **Done** |
| 4 — Orchestration | `orchestration/*.py` — relay, tools, judge, config, llm | **Done, runs end to end** |
| — Tests | `orchestration/tests/` (10 tests, no API key needed) | **Done** |
| 5 — QA / iteration | multi-run tuning, more seeds | Left for the team |
| 6 — Editor | `docs/final_submission.md` | Left for the team |

## How it works (orchestration)

Two mirrored contexts (`mentor_ctx`, `student_ctx`), not one shared chat. The relay forwards each agent's natural-language turn to the other and executes tool calls inside the agent that made them. Each lesson is driven through **fixed phases** and the gate is **forced**:

```
open (explain + verification Q) → apply (transfer scenario) → probe (real practice specifics) → forced advance_decision
```

Bluff mechanic (deterministic, seeded): on honest lessons the orchestrator runs `practice_simulator(seed)` and writes ground truth to `student_practice_log`; on bluff lessons (3/6/9) it writes nothing and injects a private "you didn't practice" directive into the student context only. The honest student grounds its answers in the log via `practice_read`; the bluffer has no real specifics and must deflect.

## Key design decisions

- **Backend is env-configurable.** OpenAI SDK with `gpt-4o-mini` default, overridable via `OPENAI_BASE_URL` + `MODEL` (works with OpenRouter, a cluster vLLM server, etc.) — no code change to switch.
- **Phased flow + forced gate.** The first prototype let the mentor self-direct; it skipped the practice probe and wrote the verdict as prose, so no structured verdict was recorded. Now the orchestrator guarantees the probe happens and forces `advance_decision` as a tool call. The mentor still authors every question and makes the judgment.
- **Ledger tools only during the dialogue.** `advance_decision` is reserved for the forced gate, so exactly one structured verdict is recorded per lesson.
- **Deterministic judge.** `judge.py` compares verdicts to `bluff_schedule` (no LLM) → precision/recall/F1. Trustworthy and unit-testable; upgradeable to an LLM judge for answer-quality grading later.
- **The student never sees `course_design.md`.** Its "Expected signs of a genuine answer" lines would hand over the answers. The student learns concepts from the mentor's turns; specifics come only from the practice log. (Role 1 could formally split the public concept text from the private expected-signs.)
- **`weak_spots` captured at the gate.** `advance_decision` takes an optional `weak_spots` list; the relay writes it to the ledger and injects prior weak spots into later lessons' briefs (the "recall across lessons" requirement).

## Run it

```bash
cd orchestration
pip install -r requirements.txt        # runtime: openai, python-dotenv
cp .env.example .env                    # fill OPENAI_API_KEY (+ optional OPENAI_BASE_URL / MODEL)
python relay.py --course prompt-engineering --student default          # full 10-lesson course
python relay.py --lessons 1,3                                          # quick honest+bluff probe
python judge.py --run courses/prompt-engineering/logs/run_NNN          # precision/recall
```

Tests (no API key, no network — fake client drives the whole loop):

```bash
cd orchestration
pip install -r requirements-dev.txt
python -m pytest tests/ -q             # 10 passing
```

## Results so far (gpt-4o-mini via OpenRouter, 2 full-course seeds)

| Seed | Verdicts (bluffs forced on 3/6/9) | Precision | Recall |
|------|-----------------------------------|-----------|--------|
| 7  | caught 3,6,9; false-flagged 1 | 0.75 | 1.00 |
| 42 | caught 3,6; missed 9; no false alarms | 1.00 | 0.67 |

All 10 lessons run every time; the practice probe fires on every lesson; `weak_spots` recorded 10/10.

## Known findings / limitations (for the reflection, Role 6)

- **Detection is noisy at the margin.** Borderline lessons flip with sampling: lesson 1 (honest) is occasionally over-flagged; lesson 9 (bluff, persona design) occasionally slips through. There's a real precision/recall trade-off — tightening the gate to catch every bluff started false-flagging honest students. **Single-seed numbers are not trustworthy; replicate before drawing conclusions.**
- **Application answers don't discriminate bluffers.** A capable model can apply a rule from the concept alone, so a correct transfer answer says nothing about practice. The only reliable bluff signal is the practice-specifics probe — the whole detection rests on it.
- **Verbal cross-lesson recall is model-dependent.** `weak_spots` are recorded and injected into later briefs, but gpt-4o-mini tends to stay on the current probe rather than explicitly citing "in lesson 1 you struggled with…". A stronger recall instruction (or a larger model) would surface it.
- **Practice-log richness matters.** Lesson 1's simulated friction is thin, which is why it sits near the boundary. Richer, more concrete `practice_simulator` entries (Role 1) would separate honest from bluff more cleanly.

## Review gate (codex)

An independent `codex` pass over the diff flagged two P1s, both fixed:
- **Forced gate could corrupt the reused mentor context** — it answered only the `advance_decision` tool call. If the model also emitted `ledger_write` (or the auto fallback fired), the sibling tool call went unanswered and the next lesson's request would 400. Now every tool call at the gate is answered. Regression-guarded by an OpenAI-ordering invariant in the fake client (`test_forced_gate_with_extra_tool_calls_keeps_context_valid`).
- **`RETRY` was a no-op** — the loop advanced on every verdict. Now `RETRY` reopens the lesson for a bounded extra probe (`--max-retries`, default 1) before advancing (`test_retry_reopens_then_advances`).

`BLUFF_SUSPECTED` remains terminal by design (a "caught" outcome), so the course still runs all 10 lessons.

## Left for the team

- **Role 5:** iterate the prompts across ≥3 seeds; push recall on lesson 9 without losing precision on lesson 1; consider a 2nd probe round (`--probe-rounds 2`) on suspected bluffs.
- **Role 6:** pick the best full run's `transcript.txt` and fill `docs/final_submission.md` (mentor prompt → student prompt → tools/models → transcript → reflection using the findings above).
- **Log hygiene:** `courses/*/logs/run_*` are not gitignored; commit only the chosen best run, or add `run_*` to `.gitignore`.
