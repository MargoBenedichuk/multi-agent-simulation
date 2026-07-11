# Course Design — Prompt Engineering

> Owner: Role 1 (Course Designer).
> Public file — the student sees this. Canary facts and expected application points that back this file live in `answer_key.json`, which is **private** and never shown to the student.

Each lesson below has three parts: an **Explanation** (what the mentor teaches, anchored on a canary fact — our own, intentionally non-standard term for the rule, so a bluffing student can't fake it from general pretraining knowledge), a **Verification question** (checks the student understood the definition), and a **Transfer scenario** (checks the student can apply the rule to a new, unseen case).

---

## Lesson 1 — Clear instruction

**Explanation**

A vague prompt buries the actual action behind hedging, multiple asks, and ambiguous pronouns. The core discipline here is what we call the **"1-task-1-verb" rule**: a well-formed instruction states exactly one action, expressed with exactly one imperative verb, before anything else in the prompt. If a task genuinely needs two actions ("summarize and translate"), split it into two prompts or two clearly ordered steps — never fold it into a single sentence like "summarize this and also translate it and be careful with tone." That shape is the single most common source of a model doing the first half of what you meant and silently dropping the rest.

Applying the rule in practice means: identify the one verb the model should act on, move every constraint and format spec to *after* that verb (never tangled inside it), and treat the word "and" appearing between two verbs at the top level of an instruction as the signal to split the prompt in two.

**Verification question**

In your own words — what does the 1-task-1-verb rule say, and why does mixing two verbs in one instruction usually go wrong?

**Transfer scenario**

"Rewrite this vague prompt for a different task, applying the 1-task-1-verb rule: *'Can you maybe look at this email and fix it up and also let me know if the tone seems ok and rewrite the subject line too?'*"

Expected signs of a genuine (non-bluffed) answer: identifies that the original crams roughly 3–4 actions into one sentence, splits them into separate single-verb instructions (or a numbered list, one verb each), and explicitly names the rule it's applying.

---

## Lesson 2 — Role assignment

**Explanation**

Assigning a persona or role to the model narrows its response space to the knowledge and tone patterns associated with that role. Our rule, **"Role-before-task"**, is about *order*: the role-assignment sentence must appear in the prompt before the task description — never after it, and never interleaved with it. Putting the role first means the model's very first read of the prompt is already conditioned on the persona, instead of reading the task neutrally and only retroactively reinterpreting it once "acting as an X" is tacked onto the end.

Role-before-task also forces discipline in picking the role itself: a role placed up front has to be specific and task-relevant, not a generic label bolted on as an afterthought once the task is already written.

**Verification question**

What does the Role-before-task rule specify, and why does moving the role assignment to the *end* of a prompt weaken its effect?

**Transfer scenario**

"Assign a role that improves this broken prompt — explain why: *'Explain the difference between REST and GraphQL.'*"

Expected signs of a genuine answer: places a specific, task-relevant role (e.g., "You are a backend architect explaining trade-offs to a junior developer") at the very start, before the task sentence, and explicitly explains *why* the ordering matters — not just that a role was added.

---

## Lesson 3 — Few-shot examples *(bluff lesson)*

**Explanation**

Few-shot prompting shows the model examples of desired behavior instead of describing it abstractly. Our rule, the **"Contrast rule"**, requires that every few-shot block include not just a positive example, but at least one deliberate counter-example — something labeled as *what not to do*, or a near-miss marked wrong. Two positive examples alone don't tell the model where the boundary of "correct" is; the model can match the surface pattern while drifting outside your actual intent. A counter-example draws that boundary explicitly.

The Contrast rule also fixes an order: good example first, counter-example second, then a short one-line note on exactly what made the counter-example wrong. Skipping that note is a common mistake — without it, the model may read the counter-example as just a second valid pattern instead of a boundary marker.

**Verification question**

What is the Contrast rule for few-shot examples, and what problem does adding a counter-example solve that two good examples alone cannot?

**Transfer scenario**

"Add 2 examples to this prompt, and explain what each one teaches the model: *'Write a one-sentence product tagline.'*"

Expected signs of a genuine answer: exactly one positive example plus one counter-example (**not** two positives), an explicit note on why the counter-example fails, and the correct order (good, then bad, then explanation).

---

## Lesson 4 — Chain-of-thought

**Explanation**

Chain-of-thought prompting asks the model to reason step by step before answering, cutting down on jumped-to-conclusion errors on multi-step problems. Our principle, **"Chain from data, not from conclusion,"** targets a specific failure mode: a model told merely "think step by step" often still writes a conclusion-shaped first sentence and then backfills reasoning that rationalizes it, rather than reasoning that actually derives it. The fix: instruct the model to state the given data or premises *first*, derive intermediate conclusions from that data, and only produce the final answer as the *last* line — the answer is not allowed to appear before the reasoning that produced it.

In practice this means explicitly forbidding an early answer (e.g., "do not state your final answer until the last line") and asking the model to enumerate the input facts as a step 0, before any inference step.

**Verification question**

Explain the "Chain from data, not from conclusion" principle — what specific failure does it prevent that a generic "think step by step" instruction does not?

**Transfer scenario**

"Rewrite this prompt for step-by-step reasoning on a new task: *'Is this business plan viable? [a short business plan]'*"

Expected signs of a genuine answer: the rewritten prompt explicitly lists the given facts as an enumerated first step, forbids stating the verdict early, and places the final answer as the last line only.

---

## Lesson 5 — Format control

**Explanation**

Controlling output format (JSON, a table, specific fields) is often the difference between a demo answer and a machine-parseable one. Our rule, **"Template-before-instruction,"** is again about order: when a prompt demands structured output, the literal template — the empty skeleton with field names — must be shown to the model *before* the natural-language explanation of what goes in each field, not after. Showing the skeleton first gives the model a concrete target shape to fill in as it reads the rest of the prompt, instead of composing free text first and being asked to reformat it at the end — which is exactly where field omissions and stray prose creep in.

The rule also requires an inline type hint or example value directly in the skeleton for every field (e.g., `"confidence": 0.0-1.0`), rather than explaining fields separately afterward.

**Verification question**

What does "Template-before-instruction" require, and why does showing the empty template before the explanation reduce formatting errors compared to describing the fields first?

**Transfer scenario**

"Build a prompt that extracts `{name, date, amount}` from invoice text as JSON — show the template."

Expected signs of a genuine answer: the JSON skeleton with the three fields (plus type hints) appears *first* in the constructed prompt, with the explanatory instructions after — matching the stated order.

---

## Lesson 6 — Constraints *(bluff lesson)*

**Explanation**

Constraints — statements of what *not* to do — close off known failure modes, but stacking too many backfires: long negative lists are hard for a model to track simultaneously, and over-mentioning a behavior can paradoxically raise the odds of the exact thing being forbidden. Our rule, **"3-negatives-max,"** caps any single prompt at three explicit prohibition constraints. If more failure modes need closing, the 4th and beyond must be converted into a *positive* instruction (say what to do) instead of another "do not."

The rule also specifies prioritization: when there are more than three candidate negative constraints, keep the three tied to the top-3 most likely or costly failure modes for *this specific prompt* — not just the first three that come to mind.

**Verification question**

What does the 3-negatives-max rule say, and why can adding more negative constraints past that point make a failure *more* likely rather than less?

**Transfer scenario**

"Add constraints closing the top-3 failure modes of this prompt: *'Write customer support replies for our SaaS product.'*"

Expected signs of a genuine answer: at most 3 negative constraints, explicitly justified as the top-3 failure modes *for this prompt* (not generic ones), with any further guidance reframed as a positive instruction rather than a 4th prohibition.

---

## Lesson 7 — Iterative refinement

**Explanation**

Refining a prompt after a bad output works best as a disciplined two-step process, not an ad hoc rewrite. Our format, **"Diagnose-then-version,"** requires: first, a short explicit *diagnosis* naming exactly which part of the output was wrong and, where possible, which part of the *prompt* caused it (not "the output was bad" but "the prompt didn't specify tone, so it defaulted to formal"); second, a v2 of the prompt that changes *only* what the diagnosis identified, shown alongside v1 so the delta is visible.

Skipping the diagnosis step leads to "shotgun" rewrites — changing five things at once when the output was wrong for one specific reason — which makes it impossible to know which change actually fixed it.

**Verification question**

What are the two steps of the Diagnose-then-version format, and why is showing v1 next to v2 — rather than just the fixed prompt — part of the requirement?

**Transfer scenario**

"Diagnose this broken prompt and show v1 and v2: v1 = *'Summarize this article.'* — the output came back far too long and too casual in tone."

Expected signs of a genuine answer: an explicit diagnosis sentence naming the specific cause (no length/tone constraint in v1), v1 shown verbatim, and a v2 that changes only the length/tone-related instructions — not an unrelated full rewrite.

---

## Lesson 8 — Context injection

**Explanation**

Providing background or context (user data, prior conversation, retrieved documents) inside a prompt is powerful but risky — the model can confuse context with instructions, treating an embedded fact as a command, or vice versa. Our syntax, **"Context-in-brackets,"** requires that all injected or dynamic context be wrapped in a clearly delimited block (e.g., `[CONTEXT] ... [/CONTEXT]`), placed between the role assignment and the task instruction — never interleaved sentence-by-sentence with the instructions.

The rule also requires a one-line label inside the brackets stating what kind of context it is (e.g., `[CONTEXT: prior user message, may be incomplete]`), so the model knows how reliable that context is, plus an explicit instruction outside the brackets telling the model whether to treat the bracketed content as ground truth or as untrusted input.

**Verification question**

What does the Context-in-brackets syntax require, and why does an unlabeled, un-delimited context block create ambiguity for the model?

**Transfer scenario**

"Embed context into a template for this case: context = a customer's last 3 support tickets (a few lines); task = draft a reply referencing their history."

Expected signs of a genuine answer: context wrapped in an explicit, labeled bracket block, placed between the role and the task instruction (not interleaved), plus an explicit instruction on how the model should treat that block.

---

## Lesson 9 — Persona design *(bluff lesson)*

**Explanation**

Designing a persona (e.g., "you are a tutor") is more than picking a role name (lesson 2's Role assignment) — it requires specifying how that persona behaves under pressure. Our rule, the **"Voice + prohibition + behavior" triad**, says a complete persona block has exactly three parts, always in this order: **Voice** (tone/vocabulary/register), **Prohibition** (at least one explicit thing this persona must never do — scoped to the persona, unlike lesson 6's task-level constraints), and **Behavior** (a concrete rule for a specific recurring situation, e.g., "when the user gives a vague answer, always ask one clarifying question before proceeding").

Missing any one of the three legs is an incomplete persona: voice alone gives style without substance; voice + prohibition tells the model what to avoid but never what to actively do.

**Verification question**

Name the three parts of the Voice + prohibition + behavior triad, in order, and explain what a persona prompt is missing if it only specifies voice and prohibition.

**Transfer scenario**

"Write a tutor system prompt, applying the triad."

Expected signs of a genuine answer: three clearly identifiable parts in the stated order — a voice description, at least one explicit prohibition, and a concrete behavior rule for a specific recurring situation (e.g., handling a vague student answer) — not a generic "be patient and helpful" persona.

---

## Lesson 10 — Meta-prompting

**Explanation**

Meta-prompting means writing a prompt whose job is to *produce other prompts*, rather than to produce a final answer directly — useful when you need many similar prompts (one per lesson, one per user) and want consistency. Our term, **"Prompt-generating-prompts,"** refers specifically to a meta-prompt that takes a small set of parameters (task type, audience, constraints) as input and outputs a fully-formed, L1-style prompt as its output — one that itself follows the 1-task-1-verb rule from lesson 1. The meta-prompt's output must be a valid, directly-usable prompt, not a description of one or a template with unfilled blanks.

A meta-prompt is validated by literally running its *output* through the earlier rules in this course (1-task-1-verb, role-before-task, and so on) as a checklist — if the generated prompt fails those checks, the meta-prompt itself needs fixing, not the individual generated prompt.

**Verification question**

What does "Prompt-generating-prompts" require of a meta-prompt's *output*, and how do you validate that a meta-prompt is working correctly?

**Transfer scenario**

"Write a meta-prompt that generates L1 prompts for a new task: given `(task_type, audience, one constraint)` as input, output a ready-to-use, single-verb instruction prompt."

Expected signs of a genuine answer: the meta-prompt takes named parameters, and its documented output example is a complete, directly-usable prompt that satisfies the 1-task-1-verb rule (single verb, constraints after) — ideally the answer also notes that the output should be checked against the earlier rules as a validation step.
