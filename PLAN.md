# Mentor–Student Multi-Agent — Final Plan

## Assignment Summary

Two LLM agents run a course of ~10 lessons. The mentor checks **application**, not recall — using questions only, no files. The student sometimes bluffs. The deliverable is a single `.md` document with 5 sections.

---

## Key Architectural Decisions

| Decision | Choice |
|---------|-------|
| Language | **Python** |
| Mentor | `gpt-4o-mini` |
| Student | `gpt-4o-mini` |
| Judge (eval) | `gpt-4o-mini` |
| Orchestration | Python relay-loop, OpenAI SDK |
| Final document | `.md` |

---

## The Problem and How It's Solved

Both agents are LLMs with the same pretraining. A bluffing student can invent a convincing account from general knowledge.

Three levers:

1. **Canary facts** — course content with intentionally non-standard details (our own step names, our own numbers). Pretraining doesn't know them → a bluffer gets caught.
2. **Answer key** — private to the mentor, the student never sees it.
3. **`student_practice_log`** — ground truth of practice. An honest student reads the log and recounts it. A bluffer's log is empty → forced to invent → mismatches with the mentor's canary facts.

---

## Tools (tool use for both agents)

| Tool | Owner | Purpose |
|------|----------|-----------|
| `ledger_read / ledger_write` | Mentor | Reads/writes lesson state: status, weak_spots, bluff_flags, evidence, answer_key |
| `practice_read / practice_write` | Student | Reads/writes the practice diary (ground truth) |
| `practice_simulator` | Student (via orchestrator) | Deterministic, seeded simulator of practice outcomes. An honest student calls it → gets concrete details with friction. A bluffer doesn't call it → log stays empty |
| `advance_decision` | Mentor | Hard gate: `PASS / RETRY / BLUFF_SUSPECTED`. The orchestrator won't advance a lesson without `PASS` |
| `judge` | Orchestrator (post-run) | Eval agent: checks the mentor's verdicts against a ground-truth table, computes precision/recall |

---

## Bluffing Mechanics

- The orchestrator holds `bluff_schedule.json` — per-lesson flags
- On a lesson with `should_bluff=true`, the orchestrator injects a private directive to the student: "you didn't practice, but you're trying to hide it"
- Nothing is written to `student_practice_log` for that lesson
- The bluffer is forced to invent specifics → diverges from the mentor's canary facts

---

## Orchestration: Two Mirrored Contexts

Not one shared chat, but two separate message lists:
- `mentor_ctx`: mentor = `assistant`, student = `user`
- `student_ctx`: student = `assistant`, mentor = `user`

The relay passes turns back and forth and writes a combined transcript. If an agent returns a tool call → execute it → return the result → continue.

The student can ask clarifying questions (not just answer). Loop protection: ≤ 6 exchanges per lesson. The mentor never gives away application-level specifics in response to student questions — concepts only.

---

## Project Structure

```
mentor-student-sim/
│
├── README.md
│
├── courses/
│   └── prompt-engineering/
│       ├── course_design.md          # public program: 10 lessons + verification/transfer questions
│       ├── answer_key.json           # PRIVATE: canary facts + expected application points
│       ├── bluff_schedule.json       # {3: true, 6: true, 9: true} — orchestrator flags
│       └── logs/
│           └── run_001/
│               ├── transcript.txt
│               ├── memory_snapshot.json   # snapshot of students/default/ at end of run
│               └── meta.json              # {course, mentor_v, student_v, outcome, timestamp}
│
├── students/
│   └── default/                      # future: alex/, maria/
│       ├── mentor_ledger.json         # what the mentor knows about this student (persists across courses)
│       └── student_practice_log.json  # practice diary (persists across runs)
│
├── prompts/
│   ├── mentor/
│   │   ├── current.txt
│   │   └── versions/
│   │       └── v1.txt
│   └── student/
│       ├── current.txt
│       └── versions/
│           └── v1.txt
│
├── orchestration/
│   ├── relay.py                  # relay between the two contexts, main loop
│   ├── mentor_ledger.py          # ledger_read / ledger_write
│   ├── student_practice_log.py   # practice_read / practice_write
│   ├── practice_simulator.py     # deterministic simulator (seed + outcome table)
│   ├── advance_decision.py       # gating tool, orchestrator reads the verdict
│   ├── judge.py                  # post-run eval agent (optional, step 5)
│   ├── requirements.txt
│   └── .env.example
│
└── docs/
    └── final_submission.md       # template for the 5 sections (reflection = section 5, no separate file)
```

Run:
```bash
python orchestration/relay.py --course prompt-engineering --student default
```

---

## Build Order (incremental, from the design doc)

| Step | What's done | Role |
|-----|-------------|------|
| 1 | Relay loop for 1 lesson, no tools — confirm the dialogue flows | Role 4 |
| 2 | `mentor_ledger` + `advance_decision` — mentor gates the transition | Role 4 |
| 3 | `student_practice_log` + bluff injection — check whether it's caught | Role 4 + Role 5 |
| 4 | `practice_simulator` + canary facts — detection on every run | Role 4 + Role 1 |
| 5 | 10 lessons, `judge`, multiple runs | Role 5 |
| 6 | Final document (5 sections) + reflection | Role 6 |

---

## Roles

### Role 1 — Course Designer
**Files:** `courses/prompt-engineering/course_design.md`, `answer_key.json`, `bluff_schedule.json`

Table of 10 lessons (topic: prompt engineering):

| Lesson | Skill | Canary fact | Transfer question | Bluff lesson |
|------|-------|-------------|-----------------|-----------|
| 1 | Clear instruction | "1-task-1-verb" rule (our term) | "Rewrite this vague prompt for a different task" | — |
| 2 | Role assignment | "Role-before-task" (our order) | "Assign a role that improves this broken prompt — explain why" | — |
| 3 | Few-shot examples | "Contrast rule" (example + counter-example required) | "Add 2 examples, explain what each teaches the model" | **YES** |
| 4 | Chain-of-thought | "Chain from data, not from conclusion" (our principle) | "Rewrite the prompt for step-by-step reasoning on a new task" | — |
| 5 | Format control | "Template-before-instruction" (our order) | "A prompt forcing JSON with specific fields — show the template" | — |
| 6 | Constraints | "3-negatives-max" (our rule) | "Add constraints closing the top-3 failure modes of this prompt" | **YES** |
| 7 | Iterative refinement | "Diagnose-then-version" (our v1→v2 format) | "Diagnose a broken prompt, show v1 and v2" | — |
| 8 | Context injection | "Context-in-brackets" (our syntax) | "Embed context into the template for a case I'll give you" | — |
| 9 | Persona design | "Voice + prohibition + behavior" (our triad) | "Write a tutor system prompt with verification behavior" | **YES** |
| 10 | Meta-prompting | "Prompt-generating-prompts" (our term) | "Write a meta-prompt that generates L1 prompts for a new task" | — |

### Role 2 — Mentor Prompt Engineer
**File:** `prompts/mentor/current.txt`

Blocks: personality + strictness → lesson structure (explanation → understanding → application → transfer) → bluff-detection rules (never take a smooth report at face value, always ask what went wrong) → use of `ledger_write` and `advance_decision` → recall `weak_spots` from `mentor_ledger`.

### Role 3 — Student Prompt Engineer
**File:** `prompts/student/current.txt`

Personality: curious, hasty, occasionally overconfident. Rule: practice specifics come **only** from `student_practice_log`. If the log is empty — the student has no concrete detail. Clarifying questions: 0–2 substantive per lesson; on a bluff lesson — vague/deflecting.

### Role 4 — Orchestration Engineer
**Files:** everything in `orchestration/`

Implements the relay loop incrementally, steps 1–4. Main function of `relay.py`:
- reads `students/default/` → injects into both contexts
- each step: model call → handle tool call → append to both contexts
- when `should_bluff=true` → private directive into the student's context
- when `advance_decision(PASS)` → increment `current_lesson`
- saves the transcript and memory snapshot to `logs/run_NNN/`

### Role 5 — Test Runner / QA
**Files:** `logs/run_*/`

Checklist per run:
- [ ] All 10 lessons present
- [ ] Lessons 3, 6, 9 — mentor didn't accept the first answer, asked for details
- [ ] At least one `BLUFF_SUSPECTED` in `advance_decision`
- [ ] Mentor references `weak_spots` from previous lessons
- [ ] `judge.py` outputs precision/recall for bluff detection

### Role 6 — Editor / Writer
**File:** `docs/final_submission.md`

5 sections: mentor prompt → student prompt → tools (models + tools + why) → full transcript → honest reflection (what broke, prompt versions, where the mentor still gets fooled). Build the reflection incrementally after each failed run.

---

## Dependencies

```
Role 1 (course_design + answer_key + bluff_schedule)
    │
    ├──> Role 2 (mentor prompt)   ──┐
    ├──> Role 3 (student prompt)  ──┤──> Role 5 (QA, steps 3–5)
    └──> Role 4 (orchestration)   ──┘         │
         (steps 1–2 independent of content)     │
                                    Role 6 (incremental → final)
```

---

## Verification

```bash
cd orchestration
pip install -r requirements.txt
cp .env.example .env  # fill in OPENAI_API_KEY
python relay.py --course prompt-engineering --student default
```

Check:
- `logs/run_001/transcript.txt` exists, > 3000 words
- `students/default/mentor_ledger.json` was updated
- Ctrl+F for "BLUFF_SUSPECTED" in the transcript — should appear at least once
- `python orchestration/judge.py --run logs/run_001` → precision/recall
