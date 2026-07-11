# Mentor prompt — rationale

`current.txt` is the live system prompt loaded by `relay.py`. Snapshots live in `versions/`.

Why each block exists:

- **Application, not recall (opening).** The assignment checks whether the student can *apply* a skill to a new case. Anchoring the mentor's whole identity on this stops it from rewarding fluent definitions.
- **Read the ledger / recall weak_spots.** Satisfies the "mentor references weak_spots from previous lessons" requirement and makes the ledger load-bearing rather than decorative.
- **5-step lesson flow.** Explanation → verification → application → *probe practice* → gate. The practice probe (step 4) is where bluffs surface, so it's explicit, not implied.
- **Bluff-detection hard rules.** The single most important block. "Never accept the first smooth answer" + "always ask what went wrong" + "cross-check specifics against the canary fact" is the concrete behaviour that turns the private answer key into detection power. Real practice has friction; invented practice thins out under a concrete follow-up.
- **Never reveal application specifics.** Without this the mentor leaks the answer when the student fishes, defeating the whole test.
- **Verdict definitions.** Ties PASS/RETRY/BLUFF_SUSPECTED to observable criteria so `advance_decision` is used consistently (and so `judge.py` measures something real).

Per lesson, `relay.py` injects a PRIVATE block into the mentor context: the lesson's concept + questions, the answer-key entry (canary fact, expected application points, bluff watch-out), and the recalled weak_spots. The student never sees any of it.

Iteration rule: before editing `current.txt`, copy it to `versions/vN.txt`.
