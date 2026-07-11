# Mentor–Student Multi-Agent Simulation

Two LLM agents run a course of 10 lessons. The mentor checks **application** of a skill (not recall) using questions only, no files/screenshots. The student sometimes bluffs. The deliverable is a single `.md` document with 5 sections.

Full architecture, rationale, and lesson table live in [`PLAN.md`](PLAN.md). This file is the short version for the team: who does what and where things live.

---

## Order of work

```
Role 1 (course_design + answer_key + bluff_schedule)
    │
    ├──> Role 2 (mentor prompt)   ──┐
    ├──> Role 3 (student prompt)  ──┤──> Role 5 (QA, runs)
    └──> Role 4 (orchestration)   ──┘         │
         (build steps 1–2 don't need content)     │
                                    Role 6 (assembles the final doc incrementally)
```

Role 1 blocks everyone — without `course_design.md` and `answer_key.json` there's nothing to check and nothing to catch bluffing against. Roles 2–4 work in parallel. Role 5 kicks in once 2+3+4 are ready through at least build step 3. Role 6 assembles `final_submission.md` as work progresses, not at the end.

---

## Tasks by role

### Role 1 — Course Designer
**Files:** `courses/prompt-engineering/course_design.md`, `answer_key.json`, `bluff_schedule.json`
**Blocks:** everyone

The table of 10 lessons (topic: prompt engineering) is already agreed and sits in `course_design.md` — that's the starting point, not a blank page. Task:
- Flesh out each lesson: skill explanation → verification question (checks understanding) → transfer scenario (checks application in a new situation)
- Build `answer_key.json` — a private file: canary facts + expected application points per lesson. **The student never sees this file.**
- Confirm/adjust `bluff_schedule.json` — which lessons the orchestrator forces a bluff on (currently: 3, 6, 9)

**Deliverable:** the three files above, ready for Roles 2–5 to use.

---

### Role 2 — Mentor Prompt Engineer
**File:** `prompts/mentor/current.txt`
**Depends on:** Role 1

Writes the mentor's system prompt: personality + strictness → lesson structure (explanation → understanding → application → transfer) → hard bluff-detection rule (never take a smooth report at face value, always ask about difficulties/details) → use of the `ledger_read/ledger_write` and `advance_decision` tools → recalling `weak_spots` from `mentor_ledger` on new lessons.

**Deliverable:** final prompt + a short rationale for each key block (can be in `current.txt` itself or a nearby README).

---

### Role 3 — Student Prompt Engineer
**File:** `prompts/student/current.txt`
**Depends on:** Role 1

Personality: curious, hasty, occasionally overconfident, realistic (don't overact). Hard rule: practice specifics come **only** from `student_practice_log` — if the log is empty, the student genuinely has no concrete detail, and that should show in the answers. Clarifying questions: 0–2 substantive per lesson; on bluff lessons — vague/deflecting questions, off the point.

Coordinate with Role 1 on which lessons (3, 6, 9 per `bluff_schedule.json`) guarantee a bluff makes it into the final run.

**Deliverable:** final student prompt.

---

### Role 4 — Orchestration Engineer
**Files:** everything in `orchestration/`
**Depends on:** Role 1 for content, but build steps 1–2 can start without finished content

Implements the relay loop **incrementally**, following the steps below. Core idea — two mirrored contexts (`mentor_ctx`, `student_ctx`), not one shared chat; the relay forwards turns and writes a combined transcript.

**Deliverable:** a working `python relay.py --course prompt-engineering --student default` that produces `logs/run_NNN/`.

---

### Role 5 — Test Runner / QA
**Files:** `courses/prompt-engineering/logs/run_*/`
**Depends on:** Roles 2, 3, 4 (at least through build step 3)

Checklist per run:
- [ ] All 10 lessons present in the transcript
- [ ] On lessons 3, 6, 9 the mentor didn't accept the first answer, asked for details
- [ ] At least one `BLUFF_SUSPECTED` in `advance_decision`
- [ ] Mentor references `weak_spots` from previous lessons (for run 2+)
- [ ] `judge.py` outputs precision/recall for bluff detection

**Deliverable:** run reports + feedback to Role 2/3 for prompt iteration.

---

### Role 6 — Editor / Writer
**File:** `docs/final_submission.md`
**Depends on:** everyone — assembles incrementally, finalizes last

5 sections: mentor prompt → student prompt → tools (models + tools + why) → full transcript of the best run → reflection (what broke, prompt versions, where the mentor still gets fooled). Collect the reflection after each failed run, not at the end — it's easier to be honest that way.

**Deliverable:** finished `final_submission.md`.

---

## Build order (Role 4, but worth everyone seeing)

| Step | What's done | Role |
|-----|-------------|------|
| 1 | Relay loop for 1 lesson, no tools — confirm the dialogue flows | Role 4 |
| 2 | `mentor_ledger` + `advance_decision` — mentor gates the transition | Role 4 |
| 3 | `student_practice_log` + bluff injection — check whether it's caught | Role 4 + Role 5 |
| 4 | `practice_simulator` + canary facts — detection on every run | Role 4 + Role 1 |
| 5 | 10 lessons, `judge`, multiple runs | Role 5 |
| 6 | Final document (5 sections) + reflection | Role 6 |

---

## Repository structure

```
.
├── README.md                          — this file
├── PLAN.md                            — full architecture and rationale
│
├── courses/
│   └── prompt-engineering/
│       ├── course_design.md           — Role 1: 10 lessons + verification/transfer
│       ├── answer_key.json            — Role 1: PRIVATE, canary facts
│       ├── bluff_schedule.json        — Role 1: bluff-lesson flags
│       └── logs/                      — relay.py writes run_NNN/ here
│
├── students/
│   └── default/
│       ├── mentor_ledger.json         — mentor's live memory of the student
│       └── student_practice_log.json  — student's practice diary (ground truth)
│
├── prompts/
│   ├── mentor/
│   │   ├── current.txt                — Role 2: working version
│   │   └── versions/                  — snapshot before each change (v1.txt, v2.txt, ...)
│   └── student/
│       ├── current.txt                — Role 3: working version
│       └── versions/
│
├── orchestration/
│   ├── relay.py                       — Role 4: main loop, two mirrored contexts
│   ├── mentor_ledger.py               — Role 4: ledger_read / ledger_write
│   ├── student_practice_log.py        — Role 4: practice_read / practice_write
│   ├── practice_simulator.py          — Role 4: deterministic simulator (seed)
│   ├── advance_decision.py            — Role 4: gating tool (PASS/RETRY/BLUFF_SUSPECTED)
│   ├── judge.py                       — Role 4/5: eval agent, precision/recall
│   ├── requirements.txt
│   └── .env.example
│
└── docs/
    └── final_submission.md            — Role 6: final document, 5 sections
```

---

## Running it

```bash
cd orchestration
pip install -r requirements.txt
cp .env.example .env  # fill in OPENAI_API_KEY
python relay.py --course prompt-engineering --student default
```

Prompt versioning rule: before changing `current.txt`, save the current version to `versions/vN.txt`, then edit. Each run's `meta.json` records which versions were used.
