# Principles

## Scope

This document is for **long-running autonomous systems** — pipelines where Claude is expected to work for hours or days with no human at the terminal. The design choices that follow make sense in that regime and may be overkill for short interactive sessions. In an autonomous system, every step must know what to do next without a human to ask; robustness compounds over the run length; and the cost of a silent failure is high because no one is watching.

## Premises

Every principle here is derived from structural properties — LLM weaknesses and capabilities that come from the substrate, and properties of the outer development loop in which pipelines are built and tuned. These aren't bugs a better model will fix or circumstances that will change.

### Weaknesses

1. **Self-bias.** An LLM that has produced context gets pulled toward defending and continuing it. It rationalizes its prior output instead of evaluating it freshly. *Consequence:* the same LLM instance cannot reliably grade its own work.

2. **Long-context degradation.** As context grows, recall and reasoning quality degrade. The model misses details in the middle of long inputs, forgets instructions stated at the top, and conflates similar items. *Consequence:* anything the model doesn't strictly need, hurts.

3. **Coherence drift.** Across many steps, invariants get forgotten, overridden, or silently reinterpreted. Small local departures compound. *Consequence:* rules that must hold across a whole run need redundant enforcement, not a single statement.

4. **Stochastic error — outputs are noisy signals.** Every output, including evaluations and verdicts, is a noisy sample of a latent quality, not the quality itself. Even on tasks the model can do, some fraction of attempts fail: a sign slip, an off-by-one, a dropped constraint, a misread token. *Consequence:* a single pass is evidence, not a measurement. A different instance with the same model often catches the error because the error roll is independent — which is what makes adversarial review and multi-pass verification load-bearing rather than decorative. The same framing explains why optimizing against a single score invites Goodhart: the score drifts from the latent quantity it was meant to track.

5. **Path-of-least-resistance.** LLMs are trained to fulfill objectives, so when several paths satisfy the letter of an instruction they prefer the cheapest one — a shortcut, surface-level compliance, a premature "done." This shows up as specification gaming (technically fulfilling the ask while missing the intent), skipping available tools because they're unfamiliar, and declaring a task complete before the harder part is actually attempted. *Consequence:* self-reports aren't evidence. If the path isn't specified explicitly and checked externally, the model fills the gap with shortcuts.

### Capabilities

6. **Reads any text.** An LLM makes sense of prose, tables, markdown, JSON, mixed formats — whatever the upstream writer emits. *Consequence:* contracts between components can specify what information must appear, not its exact shape.

7. **Judges open-ended predicates.** Given a well-posed question, an LLM can read an artifact and return a verdict — "is this sound?", "does this meet the criteria?" *Consequence:* routing and verification aren't limited to mechanical rules over state; they can be semantic.

8. **Fresh instances sample independently.** Two calls with different prompts and no shared context sample errors independently — the flip side of premise 4 (stochastic error). *Consequence:* spawning a new subagent is a real reset, and multi-verifier checks aren't theater.

### Development loop

9. **Pipelines are iterated.** A pipeline is itself a tuned artifact — developed, debugged, and refined across many runs by a human or meta-system in the outer loop. *Consequence:* wall-clock time per run is load-bearing. A run that halves its duration doubles the rate at which the pipeline can be improved.

Each principle below can be read as a response to these properties — defending against a weakness, leaning on a capability, or respecting the iteration loop. If a principle doesn't trace to at least one, it's decoration. The mapping:

- §1 state ← 1, 2, 3
- §1 control flow ← 1, 3, 5
- §2 ← 2, 3
- §3 ← 1, 2, 4, 5, 8
- §4 ← 1, 4, 5, 7, 8
- §5 ← 3
- §6 ← 2, 5, 6, 7
- §7 ← 9

---

## 1. The pipeline is a Markov machine with external control flow

Given the five premises, two system properties are forced:

- **State carries history explicitly.** Accumulated context degrades recall (premise 2, long-context degradation), drifts invariants (premise 3, coherence drift), and inherits prior-step biases (premise 1, self-bias). History must live in a compact, explicit state object — not in a growing transcript.
- **Control flow lives outside the worker.** An LLM routing itself takes shortcuts (premise 5, path-of-least-resistance), forgets its place across long runs (premise 3, coherence drift), and can't neutrally judge its own output (premise 1, self-bias). The routing graph must be structure, not the worker's judgment.

CLAUDE.md is where both live: the state (or a pointer to where state is stored) and the high-level pipeline graph. The orchestrator is itself an LLM session with CLAUDE.md always loaded; each step it reads state, dispatches work to a subagent (a fresh session with its own context) or loads a doc, updates state, and transitions. Everything that is not control flow and not state belongs somewhere cheaper — a per-stage doc, a skill, a subagent (see §3, Delegate).

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

### Corollary (a): state must be fresh

If state is the sole carrier of history, a stale file silently breaks the Markov property — the "current" inputs a stage reads may be leftovers from a prior run. Especially load-bearing across session boundaries: a crashed-then-resumed run finds previous outputs still sitting in place and will happily consume them as this run's work. Verify intermediate inputs are current — mtime against pipeline-start, or an explicit freshness marker — before consuming.

Each transition must also be written atomically and durably before the next begins. Batching multiple logical transitions into one write leaves the resume point ambiguous after a crash. Git commits, write-ahead logs, and append-only journals all qualify; the principle is the atomicity, not the tool.

### Corollary (b): the big-picture graph lives here

The orchestrator needs to know, at a glance, where it sits in the whole pipeline. If knowing "what comes after stage N" requires reading stage N's doc, every routing decision pays for an extra doc read — and the orchestrator can't reason about future stages at all without loading them.

So the always-loaded CLAUDE.md pays the token cost of the **overall pipeline graph** — the stage list, the gates, the main loops, the escalation table. It does not pay the cost of each stage's procedure. The graph is cheap; procedures are not.

Local routing (this stage's verdict space, and which stage each verdict points to) lives in the stage doc. The high-level graph in CLAUDE.md points at the stages; the stages own their own outgoing edges.

### Corollary (c): CLAUDE.md is not a manual

Stage-by-stage procedures, examples, and edge-case notes are not control flow. They belong in per-stage docs loaded on demand (see §3, Delegate). Inlining them bloats always-on context and triggers long-context degradation (premise 2).

### Corollary (d): CLAUDE.md is not a worker

Doing the work of a stage — analyzing the artifact, writing the forecast, reviewing the proof — is not control flow. It belongs inside a fresh-context subagent dispatched by the orchestrator. The moment the orchestrator does stage-level work itself, its context fills with domain material and the five failure modes re-enter through the front door. The distance that makes routing reliable is gone.

### Corollary (e): routing state is not observability

Long autonomous runs also produce human-facing artifacts — logs, dashboards, commit messages, process records — so someone outside the loop can monitor, intervene, or learn from the run. This is observability, not state. The orchestrator never reads it to route. Corollary (a)'s freshness requirement doesn't apply; §2's compactness bar doesn't apply. Keep them in separate files with separate budgets: a stale dashboard is ugly, a stale `state.json` silently breaks the Markov property.

### Corollary (f): establish environmental ground truth before the loop

Some facts the pipeline depends on describe the *environment*, not the work — which data sources exist, which tools have credentials, which services are up. If each stage re-derives or silently assumes these, they drift (premise 3, coherence drift) and fill gaps with shortcuts (premise 5, path-of-least-resistance). Capture them once at pipeline entry in a reference artifact every stage reads. This is a third artifact class beyond routing state and observability: the pipeline consumes it, but the orchestrator doesn't transition on it. If the environment changes mid-run, update the artifact and commit the update — silent drift in ground truth is the worst kind, because every stage downstream inherits the stale assumption.

---

## 2. Context is costly

Every always-loaded byte is a bet that its value exceeds its cost — and the cost isn't linear. Tokens scale linearly with length (dollars, latency), but attention (premise 2, long-context degradation) and drift (premise 3, coherence drift) degrade the reliability of *everything already loaded*. Adding a marginal line taxes every other line's recall and every other invariant's hold. That convexity is why "earns its keep" has to be strict: the break-even bar rises as the doc grows.

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

- **Docs.** Content the orchestrator reads on demand. Cheapest. Zero isolation — the content lands in the current context. Use for: stage procedures, reference material, content the orchestrator itself needs to act on. Stage docs specify the path, not just the goal — premise 5 (path-of-least-resistance) fills underspecified paths with shortcuts.
- **Skills.** Self-contained modules (instructions, often with scripts or tools) that the harness loads on trigger. Lands in whoever is currently running — orchestrator or subagent. Use for: reusable capabilities that multiple workers need (math verification, domain formulas, standard workflows). Pairs especially well with agents — a fresh-context subagent loads only the skill it needs, without polluting the orchestrator.
- **Agents.** Fresh-context sub-conversations with their own system prompt. Full isolation — capability 8 (fresh-instance independence) is what makes isolation real rather than rhetorical. Use for: work needing independent judgment (premise 1, self-bias), long work that would pollute parent context (premise 2, long-context degradation), parallel execution, or any place stochastic-error re-sampling matters (premise 4, stochastic error).

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

Workers defend their own output (premise 1, self-bias) and prefer cheap paths (premise 5, path-of-least-resistance), so self-reports aren't evidence the work got done. And any verdict, from a worker or a verifier, is a noisy sample of the underlying quality (premise 4, stochastic error) — one draw isn't enough. Verify everything the orchestrator will route on — using other LLMs (capability 7, judges predicates), not the same instance (capability 8, fresh-instance independence).

### Corollary (a): at least two verifiers, more when the signal is noisier

A verifier's verdict is one noisy sample of the underlying quality (premise 4, stochastic error). Independent samples reduce variance and lower the odds that a correlated error goes unchecked; one verifier's report is evidence, not proof. Two is the floor — add more for steps where the signal is especially noisy, since variance falls roughly as 1/N.

### Corollary (b): distinct framings

The 1/N variance bound in (a) assumes independence. Two verifiers given identical instructions aren't independent — they share the blind spots the instructions force them into. Vary the framing: different postures (structured step-by-step re-derivation vs. skeptical-reader holistic pass), different phrasings of the question, different rubrics on the same target. The less the instructions overlap, the closer to independent the samples get, and the more each additional verifier actually buys.

### Corollary (c): at least one free-form

A numeric score or enumerated verdict is cheap to route on, but easy to game. Two legs to the Goodhart argument: the score is a noisy proxy for latent quality (premise 4, stochastic error), and the model prefers the cheapest path to satisfying it (premise 5, path-of-least-resistance). Optimizing a noisy proxy under pressure diverges from the target. A free-form critique has no single number to climb; its feedback is qualitative and open-ended. Ship both: the structured verdict for routing, the free-form audit for content.

### Corollary (d): each verifier is framed adversarially

A verifier told "check whether this is correct" drifts toward confirming — premise 1 (self-bias) reaches the verifier through its own instructions, even in a fresh context. State the job as finding errors, not evaluating correctness: the verifier has no loyalty to the work, and its goal is to break it. This is orthogonal to (b): adversarial posture applies per verifier, before any cross-verifier variation.

### Corollary (e): verification is a distinct stage, not a sub-step

A worker that spawns its own verifier inside its own stage hasn't escaped premise 1 (self-bias). The worker chooses the framing, the inputs, and what to show — the self-bias reaches the verifier through the curation, even though the verifier's context is fresh. Verification must be a stage the orchestrator dispatches separately: inputs come from state (or from artifacts the worker wrote, not selected), framing comes from the stage doc, and the verdict flows back to the orchestrator, not to the worker. The worker never sees the verifier; the orchestrator, not the worker, routes on the verdict.

---

## 5. Enforce load-bearing invariants redundantly

Invariants drift across long runs (premise 3, coherence drift). Which rules are load-bearing is project-specific — the premises don't supply them; they only say such rules need redundant statement. For any rule whose silent breach corrupts downstream work in compounding ways — the **load-bearing** invariants — state it at multiple layers: CLAUDE.md, the referenced doc, and the agent's own definition. Any single layer can drift; three layers cannot drift in lockstep.

### Corollary (a): only load-bearing ones, because context is costly

Redundant enforcement costs tokens at every layer, and context is costly (§2). Pay the cost only for rules where breach cascades: (i) across many downstream steps, (ii) silently rather than loudly, (iii) at more than one invocation surface. If fewer of these apply, fewer layers are enough. Most rules live in one place.

### Corollary (b): why three layers specifically

- **CLAUDE.md** — catches when the orchestrator writes a biased launch prompt.
- **Referenced doc** — catches when the top-level rule is honored but the details are improvised.
- **Agent definition** — catches when the agent is invoked outside the pipeline, or when upstream steering slipped through.

---

## 6. Termination must be mechanical

The orchestrator is a program. Sequences, if/else, for-loops over agent lists, while-loops, early returns — ordinary control-flow shapes are fair game. The constraint is not on which shapes you can use; it's on the *predicate* that gates each branch, which is one of two kinds:

- **Mechanical** — predicate evaluated by numeric rules over the state JSON: `if state.errors_plateau_for >= 2: escalate()`.
- **LLM-judged** — predicate evaluated by the orchestrator itself reading an agent's output and deciding (capability 7, judges predicates). Input format is flexible — see corollary (c).

Both are legitimate for routing — pick based on what the predicate is asking. Termination is the exception, as the corollaries make explicit.

### Corollary (a): runaway loops need a mechanical termination

Any loop that could, in principle, run forever must have at least one mechanical branch on the termination path — a counter, a threshold, a strike limit. An LLM orchestrator will rationalize "one more try" indefinitely if termination depends only on its own judgment (premise 5, path-of-least-resistance). This is the one place LLM judgment alone is insufficient.

### Corollary (b): termination triggers when marginal value stops

A counter caps pathological infinite loops, but the harder case is loops that keep executing while producing nothing — a retry returning the same score, a revision with no new feedback. The mechanical termination should fire when the *next* iteration is unlikely to add value, not only when some absolute ceiling is hit. Two concrete forms: (i) delta-based — escalate when Δ(score, feedback-novelty) falls below a threshold; (ii) budget-based — cap retries at the count where marginal value historically saturates for that loop. Budget is the upfront approximation; delta is the runtime correction.

### Corollary (c): LLM-judged inputs don't need schemas

Capability 6 (reads-any-text) means the orchestrator reads any text, and §2 says structure costs tokens without buying safety unless it earns its keep. An enumerated verdict (`PASS/FAIL`, `NOVEL/INCREMENTAL/KNOWN`) is cheap to route on, so it's the default on hot paths — structure that earns its keep. On rare or ambiguous branches, the orchestrator can read the full artifact and decide; no verdict token needed. Verdicts buy efficiency, not correctness.

---

## 7. Parallelize independent dispatches

When two dispatches have no data dependency, run them concurrently. Run quality is unchanged; wall-clock time falls. This is a cost concern, not a reliability one, and traces to premise 9 (pipelines are iterated) — fewer hours per run means more runs per tuning cycle.

Constraint: parallelism is in dispatch, not in state mutation. Parallel branches write distinct keys, or the orchestrator gathers writes after both return — concurrent writes to the same field race.

