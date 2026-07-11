# Changelog

## Live-validation pass

Baseline ran only on a scripted fake client — never against real LLMs. This is the
first live run (OpenRouter) plus fixes for what it exposed.

- **Per-role models** — was one model for both roles; now separate `MENTOR_MODEL` /
  `STUDENT_MODEL` (recorded in `meta.json`).
- **Empty-response guard** — the reasoning student returned an empty reply ~3/10 turns;
  the old code scored that silence as a bluff (wrong — the student had practised). Now:
  detect and re-ask, plus run the student with reasoning disabled to kill blank-outs at
  the source.
- **Richer practice log** — practice now uses the student's *own* example (not the
  lecture's) with new `snippet` / `surprise` fields and 2 variants per lesson.
- **Adaptive probing** — mentor keeps asking until confident (cap `MAX_EXCHANGES`) instead
  of one fixed round; `PASS` after ≥1 probe, `BLUFF` only after ≥2. `RETRY` removed.
- **Per-lesson context isolation + course canon** — was one growing context that made the
  mentor conflate lessons (judging L5 by L3's bluff admission); now a fresh context per
  lesson, memory via `mentor_ledger` / `practice_log`, and all canary terms given to the
  mentor so cross-lesson references aren't mistaken for fabrication.
- **Prompt calibration** — mentor judges episodic specifics, not verbatim transcripts;
  student grounds answers in the real log, no placeholders. Old versions snapshotted.
- **Tests** — updated + new coverage; 17 passing.

**Result** (10 lessons, both `deepseek-v4-pro`, student reasoning off): precision **1.0**
(0 false accusations; was 0.33), recall **0.667** (bluffs 6, 9 caught; 3 slipped — the
strong student fabricated despite its directive, the honest limit of conversation-only
detection). No blank-outs.
