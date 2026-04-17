# Principles

## Scope

This document is for **long-running autonomous systems** — pipelines where Claude is expected to work for hours or days with no human at the terminal. The design choices that follow make sense in that regime and may be overkill for short interactive sessions. In an autonomous system, every step must know what to do next without a human to ask; robustness compounds over the run length; and the cost of a silent failure is high because no one is watching.

## Premises: five LLM failure modes

Every principle here is derived from one or more of five weaknesses of LLMs as a programming substrate. These aren't bugs that a better model will fix — they're properties of how autoregressive generation over a finite context window, trained to fulfill objectives, behaves. They shape what "reliable" means in this regime.

1. **Self-bias.** An LLM that has produced context gets pulled toward defending and continuing it. It rationalizes its prior output instead of evaluating it freshly. *Consequence:* the same LLM instance cannot reliably grade its own work.

2. **Long-context degradation.** As context grows, recall and reasoning quality degrade. The model misses details in the middle of long inputs, forgets instructions stated at the top, and conflates similar items. *Consequence:* anything the model doesn't strictly need, hurts.

3. **Coherence drift.** Across many steps, invariants get forgotten, overridden, or silently reinterpreted. Small local departures compound. *Consequence:* rules that must hold across a whole run need redundant enforcement, not a single statement.

4. **Stochastic error.** Even on tasks the model can do, it fails on some fraction of attempts — a sign slip, an off-by-one, a dropped constraint, a misread token. The errors are noise from a sampling process, not a ceiling on capability. *Consequence:* a single pass is unreliable even from a capable agent. A different instance with the same model often catches the error, because the error roll is independent. This is what makes adversarial review and multi-pass verification load-bearing rather than decorative.

5. **Path-of-least-resistance.** LLMs are trained to fulfill objectives, so when several paths satisfy the letter of an instruction they prefer the cheapest one — a shortcut, surface-level compliance, a premature "done." This shows up as specification gaming (technically fulfilling the ask while missing the intent), skipping available tools because they're unfamiliar, and declaring a task complete before the harder part is actually attempted. *Consequence:* two countermeasures, both needed. (a) **Detailed instructions** that spell out what counts as the work being done — the goal alone underspecifies the path. (b) **Independent verifiers** that measure whether the work got done, rather than trusting the agent's own self-report. The agent doing the work cannot be the agent judging whether the work is complete. And because stochastic error (premise 4) applies to verifiers too, one verifier is not enough — use at least two with *slightly distinct instructions* (e.g., structured step-by-step check vs. skeptical-reader free-form pass). Same target, different posture, less-correlated blind spots.

Each principle below can be read as "given these five failure modes, do X." If a principle doesn't trace to at least one of them, it is decoration.

---

## 1. CLAUDE.md is the orchestrator

The CLAUDE.md at the root of a project is always loaded into context. Its job is to hold the two things every step needs in order to proceed: **control flow** (where we are, what comes next, what to do on each verdict) and **state** — either inline or via a pointer to where state lives (typically a small JSON file).

Nothing else — or as close to nothing else as possible. Everything that is not control flow and not state belongs somewhere cheaper: a per-stage doc, a skill, a subagent (see §3, Delegate).

### Pseudocode

```
while state.status == "running":
    stage   = state.current_stage
    doc     = read(f"docs/{stage}.md")        # loaded on demand, not upfront
    verdict = run_stage(doc, state)            # may dispatch agents, write files
    state   = transition(state, verdict)       # verdict → next stage
    commit(state)
```

CLAUDE.md contains the `while`, the shape of `state`, the high-level pipeline graph, and the top-level transition table. It does not contain the body of `run_stage` for every stage — those live in `docs/*.md` and in subagent definitions.

### The big-picture graph belongs in CLAUDE.md

The orchestrator needs to know, at a glance, where it sits in the whole pipeline. If knowing "what comes after stage N" requires reading stage N's doc, every routing decision pays for an extra doc read — and the orchestrator can't reason about future stages at all without loading them.

So the always-loaded CLAUDE.md pays the token cost of the **overall pipeline graph** — the stage list, the gates, the main loops, the escalation table. It does not pay the cost of each stage's procedure. The graph is cheap; procedures are not.

Local routing (this stage's verdict space, and which stage each verdict points to) lives in the stage doc. The high-level graph in CLAUDE.md points at the stages; the stages own their own outgoing edges.

### Shared values belong in CLAUDE.md

Control flow and state are not the only things every step needs. Values that must shape *every* agent's judgment — "prior work is sunk cost," "surprises are discoveries," "never inflate framing," "every trade needs a why-now" — earn their place in the always-loaded context. The orchestrator reads them and bakes them into the launch prompts it writes; the agent definition restates the ones that agent must embody (§5). CLAUDE.md is the upstream layer of that redundant enforcement, and the only one the orchestrator sees when deciding how to dispatch.

Narrow category, same test as §5: only commitments whose silent breach corrupts downstream work across stages. Stage-specific conventions and operational tips don't qualify — they live in the stage doc.

### Corollary (a): CLAUDE.md is not a manual

Stage-by-stage procedures, examples, and edge-case notes are not control flow. They belong in per-stage docs loaded on demand (see §3, Delegate). Inlining them bloats always-on context and triggers long-context degradation (premise 2).

### Corollary (b): CLAUDE.md is not a worker

Doing the work of a stage — analyzing the artifact, writing the forecast, reviewing the proof — is not control flow. It belongs inside a fresh-context subagent dispatched by the orchestrator. The moment the orchestrator does stage-level work itself, its context fills with domain material and the five failure modes re-enter through the front door. The distance that makes routing reliable is gone.

---

## 2. Context is costly

Every token in context pays three separate costs:

- **Attention.** Long context degrades recall and reasoning (premise 2). The effect shows up well below the nominal context limit.
- **Tokens.** Every step pays to generate against the full loaded context. Over thousands of steps, it adds up to real money and real latency.
- **Drift.** More context = more surface area for invariant drift (premise 3). Irrelevant detail makes it easier for the model to rationalize ignoring a rule.

This turns CLAUDE.md programming from "write what you want" into a **budget problem**. Every always-loaded byte and every token passed to a subagent is evaluated on:

1. **Is this load-bearing for *this* step?** If not, it belongs in a deferred doc, not the prompt.
2. **Is this load-bearing for *every* step?** If yes, it earns a place in CLAUDE.md. If only some, it lives in the relevant stage doc.
3. **Will this still be needed on step 1000?** Things that only mattered early should get compacted out or replaced by a summary in state.

Consequences:

- CLAUDE.md stays small by default. Additions must earn their keep.
- Agents receive minimal inputs — file **paths** rather than file bodies, when the agent can fetch for itself.
- State is compact. Running details get summarized; raw transcripts don't live in the state JSON.
- Big-picture graph is the exception that proves the rule (see §1) — it's always-on because *every* step needs to know where it sits in the whole.

"Just in case" content is the enemy.

---

## 3. Delegate

The orchestrator is not the worker (§1), and context is costly (§2). Put together, these force delegation: the machinery to do the work should not live in the orchestrator's context. It lives somewhere else, loaded or spawned only when needed.

Three vehicles for delegation, ordered by cost and isolation:

- **Docs.** Content the orchestrator reads on demand. Cheapest. Zero isolation — the content lands in the current context. Use for: stage procedures, reference material, content the orchestrator itself needs to act on.
- **Skills.** Self-contained modules (instructions, often with scripts or tools) that the harness loads on trigger. Lands in whoever is currently running — orchestrator or subagent. Use for: reusable capabilities that multiple workers need (math verification, domain formulas, standard workflows). Pairs especially well with agents — a fresh-context subagent loads only the skill it needs, without polluting the orchestrator.
- **Agents.** Fresh-context sub-conversations with their own system prompt. Full isolation. Use for: work needing independent judgment (premise 1), long work that would pollute parent context (premise 2), parallel execution, or any place stochastic-error re-sampling matters (premise 4).

### Pick the right vehicle

| Situation | Vehicle |
|---|---|
| Content the orchestrator itself must read and act on | Doc |
| Reusable capability multiple workers need | Skill |
| Work requiring isolation, fresh perspective, or parallelism | Agent |

The orchestrator's loop becomes very short: read state, pick a vehicle, dispatch, update state. It doesn't do the work itself — it decides where the work happens.

### What this rules out

- Inlining procedures, code, or long instructions into CLAUDE.md. The orchestrator's context is not a library.
- Doing the work of a stage without spawning an agent for it, on the pretext of "just this once." The pretext always returns.
- Loading a skill in the orchestrator for work that belongs in a subagent. Skills should land where the work happens, not in the always-on context.

---

## 4. Verify, don't trust

Workers defend their own output (premise 1) and prefer cheap paths (premise 5), so self-reports are not evidence the work got done. Verify everything the orchestrator will route on — using other LLMs, not the same instance.

### Corollary (a): at least two verifiers

Stochastic error applies to verifiers too (premise 4). One verifier's report is evidence, not proof.

### Corollary (b): distinct postures

Two copies of the same verifier share their blind spots — the instructions force them there. Vary the frame (e.g. structured step-by-step re-derivation vs. skeptical-reader holistic pass) so the blind spots don't correlate.

### Corollary (c): at least one free-form

A numeric score or enumerated verdict is cheap to route on, but easy to game — the orchestrator starts optimizing for "make the score go up" rather than for the substance (premise 5). A free-form critique has no single number to climb; its feedback is qualitative and open-ended. Ship both: the structured verdict for routing, the free-form audit for content.

### Corollary (d): each verifier is framed adversarially

A verifier told "check whether this is correct" drifts toward confirming — premise 1 reaches the verifier through its own instructions, even in a fresh context. State the job as finding errors, not evaluating correctness: the verifier has no loyalty to the work, and its goal is to break it. This is orthogonal to (b): adversarial posture applies per verifier, before any cross-verifier variation.

### Corollary (e): verify inputs are current, not just that outputs are correct

When a stage reads intermediate files written earlier in the run, check they are fresh — mtime against pipeline-start, or an explicit freshness marker — before consuming. A stale file from a prior run looks identical to a current one; the consumer can't tell, and corruption cascades silently downstream. Especially load-bearing across session boundaries: a crashed-then-resumed run may find previous outputs still sitting in place, and will happily read them as if they were this run's work.

---

## 5. Enforce load-bearing invariants redundantly

Invariants drift across long runs (premise 3). Rules whose silent breach corrupts downstream work in compounding ways — the **load-bearing** invariants — get stated at multiple layers: CLAUDE.md, the referenced doc, and the agent's own definition. Any single layer can drift; three layers cannot drift in lockstep.

### Corollary (a): only load-bearing ones, because context is costly

Redundant enforcement costs tokens at every layer, and context is costly (§2). Pay the cost only for rules where breach cascades: (i) across many downstream steps, (ii) silently rather than loudly, (iii) at more than one invocation surface. If fewer of these apply, fewer layers are enough. Most rules live in one place.

### Corollary (b): why three layers specifically

- **CLAUDE.md** — catches when the orchestrator writes a biased launch prompt.
- **Referenced doc** — catches when the top-level rule is honored but the details are improvised.
- **Agent definition** — catches when the agent is invoked outside the pipeline, or when upstream steering slipped through.

---

## 6. Control flow is mechanical or LLM-judged

The orchestrator is a program. Sequences, if/else, for-loops over agent lists, while-loops, early returns — ordinary control-flow shapes are fair game. The constraint is not on which shapes you can use; it's on the *predicate* that gates each branch, which is one of two kinds:

- **Mechanical** — predicate evaluated by numeric rules over the state JSON: `if state.errors_plateau_for >= 2: escalate()`.
- **LLM-judged** — predicate evaluated by the orchestrator itself reading an agent's output and deciding (§7).

Both are legitimate. Pick based on what the predicate is asking.

### Corollary (a): runaway loops need a mechanical exit

Any loop that could, in principle, run forever must have at least one mechanical branch on the exit path — a counter, a threshold, a strike limit. An LLM orchestrator will rationalize "one more try" indefinitely if the exit depends only on its own judgment (premise 5). This is the one place LLM judgment alone is insufficient.

### Corollary (b): exits trigger when marginal value stops

A counter caps pathological infinite loops, but the harder case is loops that keep executing while producing nothing — a retry returning the same score, a revision with no new feedback. The mechanical exit should fire when the *next* iteration is unlikely to add value, not only when some absolute ceiling is hit. Two concrete forms: (i) delta-based — escalate when Δ(score, feedback-novelty) falls below a threshold; (ii) budget-based — cap retries at the count where marginal value historically saturates for that loop. Budget is the upfront approximation; delta is the runtime correction.

---

## 7. LLMs read any text

The orchestrator and the subagents are LLMs. They read prose, tables, markdown, JSON, mixed formats — whatever the upstream writer emits — and make sense of it. There is no structural requirement for parseable tokens, fixed schemas, or strict output formats between components.

### Corollary (a): coverage contracts over schemas

When the consumer is another LLM, specify *what information* must be present, not its exact shape. The consumer finds it in prose. Forcing JSON between LLMs costs expressiveness without buying safety.

### Corollary (b): enumerated verdicts are an optimization, not a requirement

An enumerated verdict (`PASS/FAIL`, `NOVEL/INCREMENTAL/KNOWN`) is cheap to route on (§6) and reliable, so it's the default on hot paths. But on rare or ambiguous branches, the orchestrator can read the full artifact and decide — no verdict token needed. Verdicts buy efficiency; they don't buy correctness.

