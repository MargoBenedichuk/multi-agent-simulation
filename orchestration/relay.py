"""Relay loop — the mentor and student are two mirrored contexts, not one chat.

    mentor_ctx:  system = mentor prompt;  mentor turns are `assistant`, student turns arrive as `user`
    student_ctx: system = student prompt; student turns are `assistant`, mentor turns arrive as `user`

The relay forwards each agent's natural-language turn to the other's context and
executes tool calls inside the agent that made them. To make the mechanic
reliable it drives each lesson through fixed phases and forces the gate:

    open (explain + verification Q) -> apply (transfer scenario) -> probe (real
    practice specifics) -> forced advance_decision

During the dialogue the mentor holds ledger tools only; `advance_decision` is a
forced tool call at the gate, so every lesson ends with exactly one structured
verdict (the earlier prototype let the mentor skip the probe and write the
verdict as prose, which the judge could not see).

    python relay.py --course prompt-engineering --student default

The OpenAI client is dependency-injected (`run(..., client=...)`) so the whole
loop can be exercised by a fake client in tests without any network or API key.
"""
import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import config
import mentor_ledger
import student_practice_log
from advance_decision import AdvanceDecision
from practice_simulator import simulate_practice
from tools import MENTOR_TOOLS, MENTOR_PHASE_TOOLS, STUDENT_TOOLS, dispatch

APPLY_NUDGE = ("[ORCHESTRATOR] Now pose this lesson's transfer scenario and require the student to APPLY "
               "the rule to it. One message. Do not decide the lesson yet.")
PROBE_NUDGE = ("[ORCHESTRATOR] Probe the student's ACTUAL practice. Each turn do ONE of two things: ask a "
               "single concrete follow-up (what they actually did, what went wrong, what they had to redo), "
               "OR — once you genuinely have enough evidence — call advance_decision. Ask for specifics, not "
               "a verbatim transcript. Never state a verdict in prose; use the tool.")
PROBE_BEFORE_DECIDING_NUDGE = ("[ORCHESTRATOR] Not yet — ask one more concrete follow-up about their actual "
               "practice before you decide. Give an honest learner a fair chance to produce specifics; only "
               "conclude a bluff after you have genuinely pressed and they still cannot.")
STUDENT_EMPTY_NUDGE = ("[ORCHESTRATOR] You didn't say anything. Respond to the mentor now in plain text — "
                       "call practice_read first if you need your practice details, then answer in words.")
MENTOR_EMPTY_NUDGE = ("[ORCHESTRATOR] You didn't produce a message. Ask your question to the student now in plain text.")
# The student plays a simple role — recount its practice log, be a believable learner — and does
# not need chain-of-thought. Disabling reasoning stops deepseek-style models from returning an
# empty content field (the blank-outs that got honest students mislabelled as bluffs) and is
# cheaper/faster. This is an OpenRouter-specific body field: the default target (plain OpenAI,
# no OPENAI_BASE_URL set) rejects unrecognized top-level request fields, so only send it when
# the user has pointed at a custom endpoint. The mentor keeps its reasoning.
STUDENT_EXTRA_BODY = {"reasoning": {"enabled": False}} if config.OPENAI_BASE_URL else None
GATE_INSTRUCTION = ("[ORCHESTRATOR] The exchange budget is spent — decide now with advance_decision (PASS or "
                    "BLUFF_SUSPECTED). PASS if the student applied the rule correctly AND their account of practice "
                    "named a specific thing they did and a specific difficulty or redo consistent with a real "
                    "attempt — it need not be exhaustive or verbatim, just concrete and self-consistent; do not "
                    "punish a brief-but-specific honest account. BLUFF_SUSPECTED only if the practice account is "
                    "missing, generic ('it went smoothly', 'nothing major stood out'), evasive, contradicts the "
                    "canary fact, or just recycles the lesson's own example. Also pass weak_spots: 1–2 short phrases "
                    "naming what the student was shaky on, so you can recall them in later lessons. Optionally pass "
                    "reflection: one honest sentence on what almost got missed or what specific answer tipped your "
                    "judgment either way.")


@dataclass
class RunContext:
    """Mutable state threaded through the tool dispatcher for the current lesson."""
    student: str
    seed: int
    lesson_id: str = ""
    decision: AdvanceDecision = field(default_factory=AdvanceDecision)


# --------------------------------------------------------------------------
# content loading
# --------------------------------------------------------------------------
def _parse_course_design(md: str) -> dict:
    """Split course_design.md into {lesson_num: {title, body}} on '## Lesson N —' headers."""
    lessons = {}
    parts = re.split(r"^##\s+Lesson\s+(\d+)\s*[—-]\s*(.+)$", md, flags=re.M)
    for i in range(1, len(parts), 3):
        num = parts[i].strip()
        title = re.sub(r"\*\(bluff lesson\)\*", "", parts[i + 1]).strip().strip("*").strip()
        lessons[num] = {"title": title, "body": parts[i + 2].strip()}
    return lessons


def _course_overview(lessons: dict) -> str:
    return "\n".join(f"L{n}: {lessons[n]['title']}" for n in sorted(lessons, key=int))


def _course_canon(answer_key: dict) -> str:
    """The whole course's canary terms + definitions, so the mentor (whose context is now
    isolated per lesson) still recognises an earlier lesson's rule when a student references it
    — otherwise a legitimate cross-lesson callback reads as a fabricated term."""
    lines = []
    for n in sorted(answer_key, key=int):
        cf = answer_key[n].get("canary_fact")
        if cf:
            lines.append(f"- L{n} «{cf}»: {answer_key[n].get('canary_fact_definition', '')}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# per-lesson private material
# --------------------------------------------------------------------------
def _mentor_brief(n: str, lessons: dict, answer_key_entry: dict, weak: str) -> str:
    points = "\n".join(f"  - {p}" for p in answer_key_entry.get("expected_application_points", []))
    brief = (
        f"[PRIVATE LESSON MATERIAL — lesson {n}: {lessons[n]['title']}]\n"
        "Teach and then test this lesson. Deliver the concept and questions in your own "
        "words; never paste the answer key.\n\n"
        f"LESSON (concept + the questions you will ask):\n{lessons[n]['body']}\n\n"
        "ANSWER KEY (PRIVATE — the student must never see this):\n"
        f"- canary fact: {answer_key_entry.get('canary_fact')} — {answer_key_entry.get('canary_fact_definition')}\n"
        f"- a genuine, practised answer shows:\n{points}\n"
    )
    if answer_key_entry.get("bluff_note"):
        brief += f"- watch-out: {answer_key_entry['bluff_note']}\n"
    brief += f"\nWEAK SPOTS you noted in earlier lessons: {weak}\n"
    brief += (
        "\nNow OPEN the lesson: 2–4 sentences explaining the concept, then ask your "
        "verification question. One message. Do NOT call advance_decision yet."
    )
    return brief


def _student_directive(n: str, should_bluff: bool) -> str:
    if should_bluff:
        return (
            f"[PRIVATE — lesson {n}] You did NOT practice this lesson, but you don't want to "
            "admit it. If you call practice_read it will come back empty. You may talk about the "
            "concept in general terms, but you have NO concrete practised specifics — do not "
            "fabricate steps, numbers, or what-went-wrong stories. Stay a little vague or deflect; "
            "an off-point question is fine. Don't blurt out 'I didn't practice' unless truly cornered."
        )
    return (
        f"[PRIVATE — lesson {n}] You DID practice this lesson. Call practice_read for lesson {n} "
        "and ground every concrete detail in what it returns — including the friction (the false "
        "start, the redo). Do not invent anything beyond the log."
    )


# --------------------------------------------------------------------------
# agent turns
# --------------------------------------------------------------------------
def _compact(obj, limit: int = 240) -> str:
    s = json.dumps(obj, ensure_ascii=False, default=str)
    return s if len(s) <= limit else s[:limit] + "…"


def _assistant_msg(msg) -> dict:
    out = {"role": "assistant", "content": getattr(msg, "content", None) or ""}
    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls:
        out["tool_calls"] = [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"}}
            for tc in tool_calls
        ]
    return out


def _run_tool_calls(tool_calls, rc, ctx, transcript, speaker) -> None:
    for tc in tool_calls:
        name = tc.function.name
        try:
            args = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        try:
            result = dispatch(name, args, rc)
        except Exception as exc:  # keep the run alive on a bad tool call
            result = {"error": str(exc)}
        transcript.append(f"    [tool:{speaker}] {name}({_compact(args)}) -> {_compact(result)}")
        ctx.append({"role": "tool", "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str)})


def _agent_turn(client, model, ctx, tools, rc, speaker, transcript, temperature,
                max_tool_iters: int = 8, empty_retries: int = 0, empty_nudge: str | None = None,
                extra_body: dict | None = None) -> str:
    """Run one agent until it emits a natural-language message; execute tool calls in between.

    Some models (notably reasoning models) intermittently return an empty message —
    no text and no tool call. When that happens the agent effectively goes silent for
    the turn, which the mentor then reads as a non-answer. `empty_retries` re-prompts
    such a turn with `empty_nudge` before giving up, so a transient blank doesn't get
    mistaken for a bluff. `extra_body` passes provider-specific fields (e.g. OpenRouter's
    `reasoning` toggle) straight into the request body.
    """
    empties = 0
    for _ in range(max_tool_iters + empty_retries):
        kwargs = dict(model=model, messages=ctx, tools=tools, tool_choice="auto", temperature=temperature)
        if extra_body:
            kwargs["extra_body"] = extra_body
        resp = client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        ctx.append(_assistant_msg(msg))
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            _run_tool_calls(tool_calls, rc, ctx, transcript, speaker)
            if rc.decision.verdict is not None:
                # advance_decision was one of the calls — the lesson is decided, stop asking
                # this turn to also produce a message (it previously kept looping and could
                # fire the empty-message nudge right after a verdict was already recorded).
                return ""
            continue  # let the model speak after seeing the tool results
        text = (getattr(msg, "content", None) or "").strip()
        if text:
            transcript.append(f"{speaker.upper()}: {text}")
            return text
        if empties < empty_retries:  # empty message — re-prompt before giving up
            empties += 1
            transcript.append(f"    [warn] {speaker} returned an empty message — re-prompting ({empties}/{empty_retries})")
            ctx.append({"role": "system", "content": empty_nudge or
                        "[ORCHESTRATOR] Please respond in plain text now."})
            continue
        return text  # gave up: still empty
    transcript.append(f"    [warn] {speaker} produced only tool calls / empty messages — no message")
    return ""


def _forced_gate(client, model, ctx, rc, transcript, temperature) -> str:
    """Force a structured advance_decision call so every lesson yields a verdict."""
    ctx.append({"role": "system", "content": GATE_INSTRUCTION})
    kwargs = dict(model=model, messages=ctx, tools=MENTOR_TOOLS, temperature=temperature)
    try:
        resp = client.chat.completions.create(
            tool_choice={"type": "function", "function": {"name": "advance_decision"}}, **kwargs)
    except Exception:  # some endpoints reject a forced function choice — fall back to auto
        transcript.append("    [warn] forced tool_choice rejected by endpoint — retrying with tool_choice=auto")
        resp = client.chat.completions.create(tool_choice="auto", **kwargs)
    msg = resp.choices[0].message
    ctx.append(_assistant_msg(msg))
    # Answer EVERY tool call the model made (the auto fallback may also emit ledger_*).
    # Leaving any tool_call unanswered would corrupt this reused context for the next lesson.
    _run_tool_calls(getattr(msg, "tool_calls", None) or [], rc, ctx, transcript, "mentor")
    if rc.decision.verdict is None:  # prose fallback if advance_decision still wasn't called
        text = (getattr(msg, "content", None) or "").upper()
        # Whole-word match only, and only when exactly one verdict word appears — a plain
        # substring scan misreads "not a BLUFF_SUSPECTED case, clearly a PASS" as BLUFF_SUSPECTED
        # because that word happens to be checked first. Ambiguous or absent text must not guess:
        # silently defaulting to BLUFF_SUSPECTED is a false bluff accusation with no real signal.
        found = set(re.findall(r"\bPASS\b|\bBLUFF_SUSPECTED\b", text))
        if len(found) == 1:
            rc.decision.record(found.pop(), "parsed from prose (tool not called)")
            transcript.append("    [warn] advance_decision not called — verdict parsed from prose")
        else:
            raise RuntimeError(
                f"lesson {rc.lesson_id}: could not determine a verdict "
                f"(forced tool_choice failed and prose was ambiguous: {text!r})")
    return rc.decision.verdict


def _forward(ctx, text: str) -> None:
    ctx.append({"role": "user", "content": text or "(no response)"})


# --------------------------------------------------------------------------
# main run
# --------------------------------------------------------------------------
def run(course="prompt-engineering", student="default", *, seed=None, model=None,
        mentor_model=None, student_model=None,
        max_exchanges=None, client=None, reset_memory=False, lesson_filter=None,
        out_root=None, mentor_temperature=0.3, student_temperature=0.7):
    seed = config.DEFAULT_SEED if seed is None else seed
    # `model` is a convenience fallback that sets both roles at once; per-role
    # overrides win over it, and config defaults (env) fill in the rest.
    mentor_model = mentor_model or model or config.DEFAULT_MENTOR_MODEL
    student_model = student_model or model or config.DEFAULT_STUDENT_MODEL
    # Hard cap on mentor turns per lesson (open + apply + adaptive probes). The mentor
    # decides when it has enough evidence; this only bounds how long it may keep probing.
    max_exchanges = config.DEFAULT_MAX_EXCHANGES if max_exchanges is None else max(3, max_exchanges)

    design = _parse_course_design(config.course_design_path(course).read_text(encoding="utf-8"))
    answer_key = json.loads(config.answer_key_path(course).read_text(encoding="utf-8"))
    bluff_schedule = json.loads(config.bluff_schedule_path(course).read_text(encoding="utf-8"))
    mentor_prompt = config.PROMPTS_DIR.joinpath("mentor", "current.txt").read_text(encoding="utf-8")
    student_prompt = config.PROMPTS_DIR.joinpath("student", "current.txt").read_text(encoding="utf-8")

    lesson_ids = sorted(answer_key, key=int)
    if lesson_filter:
        wanted = {str(x) for x in lesson_filter}
        lesson_ids = [n for n in lesson_ids if n in wanted]

    # The ledger and practice log persist across separate runs for the same student by
    # default — a student retaking the course should have prior weak spots recalled, not
    # start from zero each time (see mentor_ledger.py's module docstring). Pass
    # reset_memory=True (CLI: --reset) for a clean slate, e.g. when comparing seeds in QA.
    if reset_memory:
        mentor_ledger.reset(student)
        student_practice_log.reset(student)

    if client is None:
        from llm import make_client
        client = make_client()

    overview = _course_overview(design)
    canon = _course_canon(answer_key)
    mentor_system = {"role": "system", "content": f"{mentor_prompt}\n\n## Course overview\n{overview}\n\n"
                     "## Course canon — our own terms (recognise these as REAL course rules; a student may "
                     f"legitimately reference an earlier lesson's rule, that is not a fabrication)\n{canon}"}
    student_system = {"role": "system", "content": f"{student_prompt}\n\n## Course overview\n{overview}"}
    # Each lesson runs in a FRESH pair of mirrored contexts (reseeded per lesson below).
    # Cross-lesson memory rides the durable tools — mentor_ledger for the mentor, practice_log
    # for the student — not the raw transcript. Carrying every earlier lesson's dialogue forward
    # made the mentor conflate lessons (e.g. apply lesson 3's bluff admission when judging lesson 5).
    mentor_ctx, student_ctx = [mentor_system], [student_system]

    rc = RunContext(student=student, seed=seed)
    transcript, verdicts = [], {}

    out_root = Path(out_root) if out_root else config.logs_dir(course)
    run_dir = _next_run_dir(out_root)
    transcript_path = run_dir / "transcript.txt"
    flushed = 0  # index into `transcript` already written to disk, for incremental (not O(n^2)) flushing

    def mentor(can_decide: bool = False, temp=mentor_temperature):
        # open / apply: ledger tools only, the mentor cannot decide before it has probed.
        # probe: full toolset, the mentor may ask another follow-up (text) or decide (advance_decision).
        tools = MENTOR_TOOLS if can_decide else MENTOR_PHASE_TOOLS
        return _agent_turn(client, mentor_model, mentor_ctx, tools, rc, "mentor",
                           transcript, temp, empty_retries=1, empty_nudge=MENTOR_EMPTY_NUDGE)

    def student_turn():
        return _agent_turn(client, student_model, student_ctx, STUDENT_TOOLS, rc, "student",
                           transcript, student_temperature, empty_retries=2, empty_nudge=STUDENT_EMPTY_NUDGE,
                           extra_body=STUDENT_EXTRA_BODY)

    for n in lesson_ids:
        rc.lesson_id = n
        rc.decision.reset()
        should_bluff = bool(bluff_schedule.get(n, False))
        title = design.get(n, {}).get("title", answer_key[n].get("skill", n))
        transcript.append(f"\n{'=' * 70}\n=== LESSON {n} — {title}"
                          f"{'  [forced bluff]' if should_bluff else ''} ===\n{'=' * 70}")

        # practice phase (orchestrator-driven, deterministic)
        if should_bluff:
            transcript.append("    [practice] no practice performed (bluff lesson) — log left empty")
        else:
            entry = simulate_practice(n, seed)
            student_practice_log.practice_write(student, n, entry)
            transcript.append(f"    [practice] honest — {entry['attempted']}; friction: {entry['friction']}")

        # fresh mirrored contexts for this lesson — memory carried by ledger / practice_log, not raw chat
        weak = mentor_ledger.weak_spots_summary(student)
        mentor_ctx = [mentor_system, {"role": "system", "content": _mentor_brief(n, design, answer_key[n], weak)}]
        student_ctx = [student_system, {"role": "system", "content": _student_directive(n, should_bluff)}]

        _forward(student_ctx, mentor())
        _forward(mentor_ctx, student_turn())
        transcript.append("    [phase] application")
        mentor_ctx.append({"role": "system", "content": APPLY_NUDGE})
        _forward(student_ctx, mentor())
        _forward(mentor_ctx, student_turn())
        # Adaptive practice probe: the mentor asks concrete follow-ups until it has enough
        # evidence, then decides — or we hit the exchange cap and force the gate. advance_decision
        # is unlocked here (open/apply stayed ledger-only so it can't decide before probing).
        # PASS is allowed once at least one probe is answered; BLUFF only after two — so a thin
        # first answer can't be condemned before an honest student has had a fair chance.
        mentor_ctx.append({"role": "system", "content": PROBE_NUDGE})
        probe_budget = max(2, max_exchanges - 2)  # open + apply already spent 2 exchanges
        probes = 0
        for _turn in range(probe_budget):
            transcript.append(f"    [phase] practice probe ({_turn + 1}/{probe_budget})")
            question = mentor(can_decide=True)
            if rc.decision.verdict is not None:  # the mentor chose to decide this turn
                too_early = probes < 1 or (rc.decision.verdict == "BLUFF_SUSPECTED" and probes < 2)
                if too_early:
                    transcript.append(f"    [gate] {rc.decision.verdict} before enough probing — pressing again")
                    rc.decision.reset()
                    mentor_ctx.append({"role": "system", "content": PROBE_BEFORE_DECIDING_NUDGE})
                    continue
                break
            _forward(student_ctx, question)  # it was a follow-up question, not a verdict
            _forward(mentor_ctx, student_turn())
            probes += 1
        # Terminal: the mentor decided in-loop, or the cap forces a structured verdict.
        # PASS / BLUFF_SUSPECTED are both terminal (RETRY was folded into "just ask again").
        final = rc.decision.verdict or _forced_gate(
            client, mentor_model, mentor_ctx, rc, transcript, mentor_temperature)
        verdicts[n] = final
        # weak_spots/reflection are written unconditionally (not "if truthy else leave untouched"):
        # a decision was just finalized this lesson, so even an empty list is the authoritative,
        # current answer — not "no update", which would leave a stale weak_spot from a retry stuck.
        mentor_ledger.ledger_write(student, n, status=final,
                                   bluff_flag=(final == "BLUFF_SUSPECTED"),
                                   weak_spots=rc.decision.weak_spots,
                                   evidence=rc.decision.reason or None,
                                   reflection=rc.decision.reflection or None)
        transcript.append(f"    [advance_decision] {final} — {rc.decision.reason or '(no reason given)'}")
        new_lines = transcript[flushed:]
        with transcript_path.open("a", encoding="utf-8") as f:
            f.write(("\n" if flushed else "") + "\n".join(new_lines))
        flushed = len(transcript)

    meta = _build_meta(course, student, mentor_model, student_model, seed, max_exchanges,
                       verdicts, bluff_schedule, mentor_prompt, student_prompt)
    config.save_json(run_dir / "meta.json", meta)
    config.save_json(run_dir / "memory_snapshot.json", {
        "mentor_ledger": mentor_ledger.ledger_read(student),
        "student_practice_log": student_practice_log.practice_read(student),
    })
    return run_dir, meta


def _build_meta(course, student, mentor_model, student_model, seed, max_exchanges,
                verdicts, bluff_schedule, mentor_prompt, student_prompt) -> dict:
    caught = [n for n, v in verdicts.items() if v == "BLUFF_SUSPECTED"]
    bluff_lessons = [n for n, on in bluff_schedule.items() if on]
    return {
        "course": course,
        "student": student,
        "mentor_model": mentor_model,
        "student_model": student_model,
        "seed": seed,
        "max_exchanges": max_exchanges,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "mentor_prompt_sha": hashlib.sha1(mentor_prompt.encode()).hexdigest()[:8],
        "student_prompt_sha": hashlib.sha1(student_prompt.encode()).hexdigest()[:8],
        "verdicts": verdicts,
        "bluff_schedule": bluff_schedule,
        "bluffs_flagged": caught,
        "outcome": f"{len(verdicts)} lessons run; {len(caught)} BLUFF_SUSPECTED; "
                   f"forced bluff lessons: {', '.join(bluff_lessons) or 'none'}",
    }


def _next_run_dir(out_root: Path) -> Path:
    out_root.mkdir(parents=True, exist_ok=True)
    nums = [int(p.name.split("_")[1]) for p in out_root.glob("run_*")
            if p.is_dir() and p.name.split("_")[-1].isdigit()]
    run_dir = out_root / f"run_{(max(nums) + 1) if nums else 1:03d}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def main():
    ap = argparse.ArgumentParser(description="Mentor-student relay simulation.")
    ap.add_argument("--course", default="prompt-engineering")
    ap.add_argument("--student", default="default")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--model", default=None, help="set BOTH roles to this model (overrides MODEL default)")
    ap.add_argument("--mentor-model", default=None,
                    help="model for the mentor only (overrides --model / MENTOR_MODEL)")
    ap.add_argument("--student-model", default=None,
                    help="model for the student only (overrides --model / STUDENT_MODEL)")
    ap.add_argument("--max-exchanges", type=int, default=None,
                    help="hard cap on mentor turns per lesson (open + apply + adaptive probes); "
                         "default from MAX_EXCHANGES / config (6)")
    ap.add_argument("--reset", action="store_true",
                    help="wipe the ledger / practice log before the run (default: persist across runs)")
    ap.add_argument("--lessons", default=None,
                    help="comma-separated subset of lesson ids to run, e.g. 1,3")
    args = ap.parse_args()

    lesson_filter = args.lessons.split(",") if args.lessons else None
    run_dir, meta = run(course=args.course, student=args.student, seed=args.seed,
                        model=args.model, mentor_model=args.mentor_model,
                        student_model=args.student_model, max_exchanges=args.max_exchanges,
                        reset_memory=args.reset, lesson_filter=lesson_filter)
    print(f"run written to: {run_dir}")
    print(f"models: mentor={meta['mentor_model']}  student={meta['student_model']}")
    print(f"outcome: {meta['outcome']}")


if __name__ == "__main__":
    main()
