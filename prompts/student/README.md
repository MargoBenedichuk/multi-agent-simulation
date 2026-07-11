# Student prompt — rationale

`current.txt` is the live system prompt loaded by `relay.py`. Snapshots live in `versions/`.

Why each block exists:

- **Personality (curious, hasty, mildly overconfident, realistic).** Gives the mentor something to catch — an overconfident student reports smoothly even when it didn't practice — without caricature that would make bluffs trivially obvious.
- **The one hard rule: specifics come only from `practice_read`.** This is the mechanism that makes the whole simulation honest. The student cannot truthfully produce concrete detail it didn't practice, because its only source of specifics is the practice log. An empty log ⇒ genuinely no specifics.
- **"When you didn't practice" behaviour.** Defines a *realistic* bluff: stay general, deflect, ask an off-point question — but **do not fabricate** concrete steps/numbers, and don't confess unprompted. This keeps the bluff catchable through vagueness rather than through an obvious lie or an obvious confession.
- **Clarifying questions 0–2, vaguer when bluffing.** Matches the assignment's constraint and gives the mentor a second signal (question quality) beyond answer content.

Per lesson, `relay.py` injects a PRIVATE directive: on honest lessons "you practiced, call practice_read and ground yourself in it"; on bluff lessons (3/6/9) "you did not practice, don't fabricate, don't confess." The mentor never sees these directives.

Iteration rule: before editing `current.txt`, copy it to `versions/vN.txt`.
