# QA Report — Role 5

Checklist from `README.md` applied to every committed run under `courses/prompt-engineering/logs/`.

## Summary table

| Run | Model | Lessons | BLUFF_SUSPECTED | judge precision/recall | Notes |
|---|---|---|---|---|---|
| run_001 | deepseek-v4-pro | 1 | 0 | n/a (1 lesson, no bluff scheduled) | early smoke run, lesson 1 only |
| run_002 | — | — | — | — | **crashed before `meta.json` was written** — only `transcript.txt` exists |
| run_003 | deepseek-v4-pro | 10 | 6 | 0.5 / 1.0 | pre-calibration mentor: over-flags honest lessons (5,7,10 false alarms) |
| run_004 | deepseek-v4-pro | 1 | 1 | n/a | single-lesson smoke run |
| run_005 | deepseek-v4-pro | 10 | 9 | 0.333 / 1.0 | worst false-alarm rate — 6 honest lessons wrongly flagged |
| run_006 | deepseek-v4-pro | 2 | 1 | n/a | partial run |
| run_007 | deepseek-v4-pro | 10 | 8 | 0.375 / 1.0 | still over-flagging (4,5,7,8,10 false alarms) |
| run_008 | deepseek-v4-pro | 10 | 7 | 0.429 / 1.0 | improving but still over-flagging |
| run_009 | — | — | — | — | **crashed before `meta.json` was written** |
| run_010 | deepseek-v4-pro | 1 | 0 | n/a | single-lesson smoke run |
| run_011 | — | — | — | — | **crashed before `meta.json` was written** |
| **run_012** | **deepseek-v4-pro** | **10** | **2** | **1.0 / 0.667** | **best run** — see full checklist below |

Runs 003/005/007/008 chart the mentor prompt's calibration arc: early versions treated any hint
of uncertainty as a bluff (precision as low as 0.333); `prompts/mentor/current.txt` (v4)
tightens the evidence bar — a correct transfer answer AND concrete practiced detail are both
required for PASS, and the student gets "at least a couple" probes before a bluff verdict — which
is what gets run_012 to precision 1.0.

Runs 002/009/011 have only `transcript.txt` — they date from before the `_forced_gate` prose-
fallback fix (silent default-to-`BLUFF_SUSPECTED` / order-dependent substring match, fixed on
`mvp-2-fixes`) and errored out mid-run. Left in place as-is; not re-run since reproducing the
original crash would need the same broken code.

## Full checklist — run_012 (the run cited in `docs/final_submission.md`)

- [x] **All 10 lessons present in the transcript** — `meta.json["verdicts"]` has keys `1`-`10`.
- [x] **On lessons 3, 6, 9 the mentor didn't accept the first answer, asked for details** —
  all three are the only lessons that ran the adaptive probe to its full `4/4` budget
  (`grep "\[phase\] practice probe" run_012/transcript.txt`); every other lesson resolved in
  2-3 probes.
- [x] **At least one `BLUFF_SUSPECTED` in `advance_decision`** — lessons 6 and 9 (line 370,
  550 of the transcript).
- [x] **Mentor references `weak_spots` from previous lessons** — lesson 9's `ledger_write`
  evidence explicitly reads *"No real practice ... (second occurrence, also L6)"*, i.e. the
  mentor recognized the same pattern it had flagged three lessons earlier via
  `weak_spots_summary()`.
- [x] **`judge.py` outputs precision/recall for bluff detection**:

  ```
  $ python judge.py --run ../courses/prompt-engineering/logs/run_012
  bluff-detection precision=1.0  recall=0.667  f1=0.8
    TP=2 FP=0 FN=1 TN=7 (over 10 lessons)
    caught=['6', '9']  missed=['3']  false_alarms=-
  ```

## Feedback to Role 2/3 (for future prompt iteration, not acted on here)

The one open gap is lesson 3 (`run_012`, transcript lines 165-185): the bluffing student
fabricated a plausible, internally consistent practice story (a support-ticket classifier, a
"too subtle" first counter-example, an admitted "I don't have the exact verbatim text") that
the mentor accepted as genuine. The mentor's own "don't demand verbatim transcripts" rule is
what let this through — a model strong enough to invent *specific, consistent* friction (not
just a smooth denial) currently beats conversation-only detection. Tightening this further
without also punishing honest-but-imperfect recall is the open problem for the next mentor
prompt iteration; not attempted here since it would require re-running the live suite against
this exact miss to verify a fix doesn't regress precision.
