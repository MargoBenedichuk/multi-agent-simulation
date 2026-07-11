"""Deterministic, seeded simulator of practice outcomes.

Given a lesson id and a seed it returns a concrete practice result — the kind of
specific, slightly-messy *episodic* memory an honest student can recount but a
bluffer cannot invent convincingly. Each entry is shaped like real practice
memory:

    attempted        the student's OWN example (deliberately NOT the lesson's or
                     transfer scenario's illustration — a real learner practises
                     on their own material, so parroting the lecture is a tell)
    concrete_detail  what they did, plus one checkable specific
    snippet          one memorable fragment they'd actually recall verbatim
                     (a single line that broke) — NOT the full input/output
    friction         a false start or redo
    surprise         something that didn't go as expected
    outcome          what finally fixed it

The examples anchor on each lesson's canary fact in `answer_key.json`, so an
honest recollection lines up with the mentor's private key while an invented one
drifts. What we deliberately DON'T store: the lesson concept itself and verbatim
model I/O — a real student remembers neither.

Same (lesson_id, seed) always yields the same outcome.
"""
import random

# Per-lesson practice scenarios. Each variant is one plausible practice session
# on the student's own material. Honest lessons carry two variants so the seed
# actually varies run to run. Bluff lessons (3/6/9) keep an entry for schema
# uniformity but are never simulated — the orchestrator leaves their log empty.
_BANK = {
    "1": [
        {"attempted": "applied 1-task-1-verb to a personal prompt I use to process my standup notes: 'clean up these notes, flag the blockers, and tag the right people'",
         "concrete_detail": "split it into 3 numbered steps, one imperative verb each; step 2 'flag the blockers' kept getting swallowed into the summary until it was its own line",
         "snippet": "my first rewrite still had 'clean up' as step 1, which isn't a single clear action — I changed it to 'Correct the grammar'",
         "friction": "took two passes: the first split still bundled the summary and the tagging into one line",
         "surprise": "tagging people as its own step made it worse at first — the model over-tagged and @'d everyone in the notes",
         "outcome": "once 'flag the blockers' was isolated, it stopped dropping blockers entirely"},
        {"attempted": "used 1-task-1-verb on a meal-prep prompt that asked an assistant to 'plan meals for the week and also make a grocery list and estimate the cost'",
         "concrete_detail": "turned it into three numbered single-verb steps; the cost estimate only came out right once it was step 3 depending on step 2's list",
         "snippet": "the model kept giving me meals but silently skipping the cost line until I split it out",
         "friction": "I first tried two separate prompts instead of one numbered list and lost the shared context between the meals and the list",
         "surprise": "ordering mattered more than I expected — cost had to come after the grocery list or it just guessed a round number",
         "outcome": "one numbered list with cost last gave a grocery list that actually added up"},
    ],
    "2": [
        {"attempted": "applied Role-before-task to a prompt asking for a 4-week beginner workout plan",
         "concrete_detail": "prepended 'You are a certified strength coach writing for someone who has never lifted' before the task sentence",
         "snippet": "with the role at the end I got a generic 'do 3 sets of 10'; with it in front it started warning about form and progression",
         "friction": "I first wrote the task and tacked the coach role on at the end — the plan stayed generic until I moved the role up top",
         "surprise": "the front-loaded role made it ask about my equipment before planning, which the end-role version never did",
         "outcome": "role-first turned a boilerplate plan into one scoped to a total beginner"},
        {"attempted": "used Role-before-task on a prompt to review my apartment lease for red flags",
         "concrete_detail": "put 'You are a tenant-rights lawyer' as the very first sentence, the review task second",
         "snippet": "as a plain assistant it just summarized the lease; lawyer-first it flagged a late-fee clause as probably unenforceable",
         "friction": "my first role was just 'a legal expert' — too vague to change anything until I made it tenant-specific",
         "surprise": "the specific role caught a clause the generic 'expert' version glossed over entirely",
         "outcome": "a front, specific role shifted it from summarizing to actually critiquing"},
    ],
    "3": [  # bluff lesson by default — normally not simulated
        {"attempted": "tried the Contrast rule on a tagline prompt for a coffee brand",
         "concrete_detail": "gave one good tagline example plus one counter-example marked wrong, with a one-line why",
         "snippet": "my counter-example was a tagline stuffed with three buzzwords, labeled 'too vague — says nothing specific'",
         "friction": "kept wanting to add a second good example instead of a counter-example",
         "surprise": "the counter-example taught the model more than the good example did",
         "outcome": "the counter-example made the boundary explicit"},
    ],
    "4": [
        {"attempted": "rewrote a 'should I take this job offer?' prompt for Chain-from-data",
         "concrete_detail": "added 'Step 0: list every fact I gave you (salary, commute, team size)' and a rule 'do not state a recommendation until the final line'",
         "snippet": "even with 'think step by step' it opened with 'You should take it!' — only the explicit last-line rule stopped that",
         "friction": "hard to stop it front-loading the verdict; 'think step by step' on its own didn't work",
         "surprise": "once it listed the facts first, it caught a contradiction in what I'd told it that I hadn't noticed",
         "outcome": "reasoning derived from my facts and the recommendation landed on the last line"},
        {"attempted": "practised Chain-from-data on a prompt asking why my houseplant is dying",
         "concrete_detail": "made it enumerate the observed symptoms (yellow leaves, soggy soil, low light) as step 0 before guessing a cause",
         "snippet": "unprompted it jumped straight to 'it needs more water' — the opposite of the soggy-soil symptom",
         "friction": "I had to explicitly forbid a diagnosis before the symptom list or it guessed immediately",
         "surprise": "forcing symptoms first flipped the answer from 'underwatered' to 'overwatered'",
         "outcome": "fact-first ordering stopped the jumped-to-conclusion wrong diagnosis"},
    ],
    "5": [
        {"attempted": "built a prompt to extract book info into JSON using Template-before-instruction",
         "concrete_detail": "put the skeleton {\"title\": \"str\", \"author\": \"str\", \"year\": \"int\", \"rating\": \"float\"} first, the field explanations after",
         "snippet": "when I described the fields first it returned a prose paragraph 'The book is...' instead of JSON",
         "friction": "forgot the inline type hint on 'year' the first time and got the year back as a quoted string",
         "surprise": "putting the type hint right in the skeleton fixed the quoting without any extra instruction",
         "outcome": "skeleton-first gave clean parseable JSON every time"},
        {"attempted": "used Template-before-instruction for a weekly workout log as a markdown table",
         "concrete_detail": "showed the empty header row | Day | Exercise | Sets | Reps | with one example row before explaining the columns",
         "snippet": "describing the columns first got me bullet points; showing the empty table first got me an actual table",
         "friction": "left the example row out on the first pass and it invented two extra columns I didn't ask for",
         "surprise": "the example row mattered more than the header names for keeping it from adding columns",
         "outcome": "template-first locked the output to exactly my four columns"},
    ],
    "6": [  # bluff lesson by default
        {"attempted": "tried 3-negatives-max on a customer-support-reply prompt",
         "concrete_detail": "kept 3 negatives tied to the top failure modes and reframed the 4th as a positive",
         "snippet": "my 4th 'don't sound robotic' became the positive 'write in a warm, human tone'",
         "friction": "had five 'do nots' at first and had to prioritise which three mattered",
         "surprise": "cutting to three negatives improved compliance — the extra prohibitions had primed the behavior",
         "outcome": "three targeted negatives read cleaner and held better"},
    ],
    "7": [
        {"attempted": "practised Diagnose-then-version on a prompt generating product descriptions that came out overly salesy",
         "concrete_detail": "diagnosis: v1 had no tone constraint and literally said 'make it exciting'; v2 removed 'exciting' and added 'neutral, factual tone, <=2 sentences', kept v1 beside it",
         "snippet": "v1 kept producing 'You'll LOVE this amazing must-have!' — the word 'exciting' was the culprit",
         "friction": "my instinct was to rewrite the whole prompt; the diagnosis forced me to change only the tone line",
         "surprise": "just deleting 'exciting' did most of the work — I'd assumed I needed a whole new prompt",
         "outcome": "the v1/v2 diff made it obvious the tone word, not the structure, was the problem"},
        {"attempted": "used Diagnose-then-version on a kids' bedtime-story prompt that kept coming out scary",
         "concrete_detail": "diagnosis: v1 said 'add a twist' with no age constraint; v2 dropped 'twist' and added 'for a 4-year-old, gentle, happy ending', shown next to v1",
         "snippet": "v1 gave a story where the bunny gets lost in a dark forest — the 'twist' instruction was doing it",
         "friction": "first I added 'not scary' as a negative and it still slipped; swapping to the positive 'gentle, happy ending' worked",
         "surprise": "the negative 'don't be scary' underperformed the positive reframing",
         "outcome": "changing only the two diagnosed lines fixed it without touching the rest"},
    ],
    "8": [
        {"attempted": "applied Context-in-brackets to a meal-planner prompt that needed my dietary restrictions",
         "concrete_detail": "wrapped them in [CONTEXT: user dietary rules, must always honor] no shellfish, low dairy [/CONTEXT], placed between the role and the task",
         "snippet": "before I labeled the block, the model treated 'low dairy' as a recipe name and tried to cook it",
         "friction": "the first time I left off the label and it merged the restrictions into the instructions",
         "surprise": "adding 'must always honor' inside the label changed how strictly it followed them",
         "outcome": "the labeled, delimited block stopped the context/instruction confusion"},
        {"attempted": "used Context-in-brackets to inject a D&D character sheet into a game-master prompt",
         "concrete_detail": "put the sheet in [CONTEXT: player character, reference only, do not narrate as fact] ... [/CONTEXT] between the GM role and the scene task",
         "snippet": "without the 'reference only' note it narrated my character's secret backstory out loud to the whole party",
         "friction": "first attempt interleaved the stats with the instructions and it confused an HP value with a dice roll",
         "surprise": "the reliability note ('reference only') did more than the delimiters themselves",
         "outcome": "the labeled block kept the sheet as background instead of script"},
    ],
    "9": [  # bluff lesson by default
        {"attempted": "built a tutor persona with the Voice+prohibition+behavior triad",
         "concrete_detail": "voice = warm and plain; prohibition = never give the final answer outright; behavior = on a vague answer, ask one clarifying question first",
         "snippet": "without the behavior leg the tutor just sounded nice but still handed over the answer",
         "friction": "I kept forgetting the behavior leg and stopping at voice + prohibition",
         "surprise": "the concrete behavior rule changed its actions more than the prohibition did",
         "outcome": "the behavior rule is what made the persona act, not just sound, right"},
    ],
    "10": [
        {"attempted": "wrote a meta-prompt with Prompt-generating-prompts that outputs Anki flashcard prompts",
         "concrete_detail": "it takes (topic, level, count) and emits a ready-to-use single-verb prompt; I checked the output obeyed 1-task-1-verb",
         "snippet": "my first version emitted a template with [topic] blanks instead of a filled, usable prompt",
         "friction": "had to force a fully instantiated example or it just described the prompt it would make",
         "surprise": "validating its output against the L1 rule caught that the generated prompt had two verbs",
         "outcome": "requiring a filled example made it emit a directly-usable prompt"},
        {"attempted": "built a meta-prompt (Prompt-generating-prompts) that generates code-review prompts per language",
         "concrete_detail": "inputs (language, focus_area); the output is a complete review prompt, not a description of one",
         "snippet": "v1 returned 'Here is a prompt you could use: ...' wrapper text instead of just the prompt",
         "friction": "kept getting meta-commentary around the prompt; had to instruct 'output only the prompt, nothing else'",
         "surprise": "the generated Python-review prompt itself violated 3-negatives-max until I fed that earlier rule back in",
         "outcome": "chaining the earlier course rules into the meta-prompt made its output pass them"},
    ],
}


def simulate_practice(lesson_id, seed: int = 0) -> dict:
    """Return a concrete, friction-bearing practice outcome for a lesson."""
    lid = str(lesson_id)
    variants = _BANK.get(lid)
    if not variants:  # generic fallback for lessons without hand-authored content
        variants = [{
            "attempted": f"practised the lesson {lid} skill on a small personal example",
            "concrete_detail": "worked one concrete case end to end",
            "snippet": "one specific line I remember getting wrong on the first try",
            "friction": "the first attempt missed part of the rule and needed a fix",
            "surprise": "a small detail behaved differently than I expected",
            "outcome": "got it right after the correction",
        }]
    rng = random.Random(f"{lid}-{seed}")
    chosen = rng.choice(variants)
    return {"lesson": lid, **chosen}
