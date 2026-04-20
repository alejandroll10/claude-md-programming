# Principles

## Scope

This document is for **long-running autonomous systems** (pipelines where Claude is expected to work for hours or days with no human at the terminal). The design may be overkill for interactive sessions. In an autonomous system, every step must know what to do next; robustness compounds over the run length; and silent failures cost more because no one is watching.

## Premises

Every principle here is derived from structural properties: LLM weaknesses and capabilities that come from the substrate, plus cost properties that bind any real deployment. These aren't bugs a better model will fix.

### Weaknesses

1. **Self-bias.** An LLM that has produced context gets pulled toward defending and continuing it. It rationalizes its prior output instead of evaluating it freshly. *Consequence:* the same LLM instance cannot reliably grade its own work.

2. **Long-context degradation.** As context grows, recall and reasoning quality degrade. The model misses details in the middle of long inputs, forgets instructions stated at the top, and conflates similar items. *Consequence:* anything the model doesn't strictly need, hurts.

3. **Coherence drift.** Across many steps, invariants get forgotten, overridden, or silently reinterpreted. Small local departures compound. *Consequence:* rules that must hold across a whole run need redundant enforcement, not a single statement.

4. **Stochastic error: outputs are noisy signals.** Every output is a noisy sample of a latent quality, not the quality itself. Even on tasks the model can do, some fraction of attempts fail: a sign slip, an off-by-one, a dropped constraint, a misread token. *Consequence:* a single pass is evidence, not a measurement. A different instance often catches the error because the error roll is independent, which is what makes adversarial review and multi-pass verification load-bearing.

5. **Path-of-least-resistance.** LLMs are trained to fulfill objectives, so when several paths satisfy the letter of an instruction they prefer the cheapest one (a shortcut, surface-level compliance, a premature "done"). This shows up as specification gaming (technically fulfilling the ask while missing the intent), skipping available tools because they're unfamiliar, and declaring a task complete before the harder part is actually attempted. *Consequence:* self-reports aren't evidence. If the path isn't specified explicitly and checked externally, the model fills the gap with shortcuts.

### Capabilities

6. **Reads any text.** An LLM makes sense of prose, tables, JSON, and mixed formats. *Consequence:* contracts between components can specify what information must appear, not its exact shape.

7. **Judges open-ended predicates.** Given a well-posed question, an LLM can read an artifact and return a verdict ("is this sound?", "does this meet the criteria?"). *Consequence:* routing and verification aren't limited to mechanical rules over state; they can be semantic.

8. **Fresh instances are less correlated, not independent.** Two calls with different prompts and no shared context sample errors at substantially lower correlation than a single continuation, but not at zero: they still share the model's weights, training-data biases, and systematic failure modes. *Consequence:* spawning a new subagent is a real reset of session-local context and dramatically reduces correlated failure, but multi-verifier variance reduction has a floor at the model-level correlation. Crossing different models lowers the floor further.

### Deployment

9. **Tokens and time cost.** Every token spent charges dollars and latency; every second of wall-clock charges latency. Costs are linear in the input. *Consequence:* at equal correctness, the cheaper design wins. The superlinear bite (marginal cost of added context rising because premises 2 and 3 make earlier content less reliable) is derived in §2, not assumed here.

10. **Infrastructure fails independently of the work.** Long autonomous runs accumulate transient failures (tool timeouts, rate limits, malformed outputs from a flake, network blips) that are exogenous to the task signal. *Consequence:* any predicate or counter fed by task signal must distinguish exogenous from endogenous failures, or the downstream decision is noisier than the signal warrants.

Each principle below can be read as a response to these properties (defending against a weakness, leaning on a capability, or trading on the deployment side). If a principle doesn't trace to at least one, it's decoration. The mapping:

- §1 state ← 1, 2, 3, 10
- §1 control flow ← 1, 3, 5
- §2 ← 2, 3, 9
- §3 ← 1, 2, 3, 4, 5, 6, 8
- §4 ← 1, 4, 5, 7, 8
- §5 ← 5, 6, 7, 9, 10
- §6 ← 9

---

## 1. The pipeline is a Markov machine with external control flow

Given the premises above, two system properties are forced:

- **State carries history explicitly.** Accumulated context degrades recall (premise 2, long-context degradation), drifts invariants (premise 3, coherence drift), and inherits prior-step biases (premise 1, self-bias). History must live in a compact, explicit state object, not in a growing transcript.
- **Control flow lives outside the worker.** An LLM routing itself takes shortcuts (premise 5, path-of-least-resistance), forgets its place across long runs (premise 3, coherence drift), and can't neutrally judge its own output (premise 1, self-bias). The routing graph must be structure, not the worker's judgment.

CLAUDE.md is where both live: the state (or a pointer to where state is stored) and the high-level pipeline graph. The orchestrator is itself an LLM session with CLAUDE.md always loaded; each step it reads state, dispatches work to a subagent or loads a doc, updates state, and transitions. Everything that is not control flow or state belongs somewhere cheaper: a per-stage doc, a skill, a subagent (see §3, Delegate).

### Pseudocode

```
while state.status == "running":
    stage   = state.current_stage
    doc     = read(f"docs/{stage}.md")        # loaded on demand, not upfront
    verdict = run_stage(doc, state)            # may dispatch agents, write files
    state   = transition(state, verdict)       # verdict → next stage
    commit(state)
```

CLAUDE.md contains the `while`, the shape of `state`, the high-level pipeline graph, and the top-level transition table. It does not contain the body of `run_stage` for every stage. Those live in `docs/*.md` and in subagent definitions.

### Corollary (a): state must be fresh

If state is the sole carrier of history, a stale file silently breaks the Markov property. The "current" inputs a stage reads may be leftovers from a prior run. The failure mode sharpens across session boundaries: a crashed-then-resumed run finds previous outputs in place and consumes them as this run's work. Verify intermediate inputs are current (mtime against pipeline-start, or an explicit freshness marker) before consuming.

### Corollary (b): the big-picture graph lives here

The orchestrator needs to know, at a glance, where it sits in the whole pipeline. If knowing "what comes after stage N" requires reading stage N's doc, every routing decision pays for an extra doc read, and the orchestrator can't reason about the shape of future stages without loading them.

So the always-loaded CLAUDE.md pays the token cost of the **overall pipeline graph** (the stage list, the gates, the main loops, the escalation table). It does not pay the cost of each stage's procedure. The graph is cheap; procedures are not.

Local routing (this stage's verdict space, and which stage each verdict points to) lives in the stage doc. The high-level graph in CLAUDE.md points at the stages; the stages own their own outgoing edges.

### Corollary (c): CLAUDE.md is not a manual

Stage-by-stage procedures, examples, and edge-case notes are not control flow. They belong in per-stage docs loaded on demand (see §3, Delegate). Inlining them bloats always-on context (premise 2).

### Corollary (d): CLAUDE.md is not a worker

Doing the work of a stage (analyzing the artifact, writing the forecast, reviewing the proof) is not control flow. It belongs inside a fresh-context subagent dispatched by the orchestrator. The moment the orchestrator does stage-level work, its context fills with domain material and the failure modes the separation kept at arm's length take hold. The distance that makes routing reliable is gone.

This separation is enforced by discipline, not structure: the orchestrator is itself an LLM and can always reach for stage-level work if the doc doesn't forbid it. State the boundary explicitly, and route stage work outward even when "just reading one file" looks cheaper than spawning an agent.

### Corollary (e): routing state is not observability

Long autonomous runs also produce human-facing artifacts (logs, dashboards, commit messages, process records) so someone outside the loop can monitor, intervene, or learn from the run. This is observability, not state. The orchestrator never reads it to route. Corollary (a)'s freshness requirement doesn't apply; §2's compactness bar doesn't apply. Keep them in separate files with separate budgets: a stale dashboard is ugly, a stale `state.json` silently breaks the Markov property.

### Corollary (f): establish environmental ground truth before the loop

Some facts the pipeline depends on describe the *environment*, not the work (which data sources exist, which tools have credentials, which services are up). If each stage re-derives or silently assumes these, they drift (premise 3, coherence drift) and fill gaps with shortcuts (premise 5, path-of-least-resistance). Capture them once at pipeline entry in a reference artifact every stage reads. This is a third artifact class beyond routing state and observability: the pipeline consumes it, but the orchestrator doesn't transition on it. If the environment changes mid-run, update the artifact and commit the update. Silent drift in ground truth is worst: every stage downstream inherits the stale assumption.

### Corollary (g): resumability is a property, not a feature

A long-running pipeline outlives any single session (premise 10, infrastructure fails). Laptops sleep, processes get killed, tools rate-limit, connections drop. Stages carry non-idempotent side effects (artifact writes, agent dispatches, external API calls) that can't safely be replayed, so each transition must commit atomically and durably before the next begins. Batching multiple logical transitions into one write leaves the resume point ambiguous after a crash. Git commits, write-ahead logs, and append-only journals all qualify; the principle is the atomicity, not the tool.

Eliminate the first-run branch by shipping a valid initial state pre-committed. The orchestrator's entry point is then identical on a fresh run and a resume: read state, and if `status == "running"` with `current_stage` set, continue.

This in turn demands a property on every stage: its effects must be either committed to state when the transition commit lands, or safely redoable from the post-commit state. A stage that writes artifacts without recording them in state leaves orphans after a crash; one that marks itself complete before finishing silently skips work on resume. On resume, the orchestrator should discard any uncommitted working-tree changes left by a crashed stage before continuing; doing so assumes the pipeline runs in a dedicated directory where untracked files are always orphan artifacts, never user work.

---

## 2. Context is costly

Every always-loaded byte is a bet that its value exceeds its cost, and the cost rises faster than length. The direct cost (premise 9, tokens and time cost) is linear in length, but attention (premise 2, long-context degradation) and drift (premise 3, coherence drift) degrade the reliability of *everything already loaded*. Adding a marginal line taxes the prior content's recall and the prior invariants' hold, so the cost of adding the N+1th line grows with N rather than being constant. Total context cost is therefore superlinear in length. That superlinearity is why "earns its keep" has to be strict: the break-even bar rises as the doc grows.

This makes CLAUDE.md programming a **budget problem**: every always-loaded byte and every token passed to a subagent is judged on:

1. **Is this load-bearing for *this* step?** If not, it belongs in a deferred doc, not the prompt.
2. **Is this load-bearing for *every* step?** If yes, it earns a place in CLAUDE.md. If only some, it lives in the relevant stage doc.
3. **Will this still be needed on step 1000?** Things that only mattered early should get compacted out or replaced by a summary in state.

Consequences:

- CLAUDE.md stays small by default. Additions must earn their keep.
- Agents receive minimal inputs: file **paths** rather than file bodies, when the agent can fetch for itself.
- State is compact. Running details get summarized; raw transcripts don't live in the state JSON.
- Big-picture graph is the exception that proves the rule (see §1): it's always-on because *every* step needs to know where it sits in the whole.

"Just in case" content is the enemy.

---

## 3. Delegate

§1 and §2 together force delegation: the machinery to do the work should not live in the orchestrator's context. It lives somewhere else, loaded or spawned only when needed.

Three vehicles for delegation, ordered by cost and isolation:

- **Docs.** Content the orchestrator reads on demand. Cheapest. Zero isolation: the content lands in the current context. Use for: stage procedures, reference material, content the orchestrator itself needs to act on. Stage docs specify the path, not just the goal. Premise 5 (path-of-least-resistance) fills underspecified paths with shortcuts.
- **Skills.** Self-contained modules (instructions, often with scripts or tools) that the harness loads on trigger. Lands in whoever is currently running (orchestrator or subagent). Use for: reusable capabilities that multiple workers need (math verification, domain formulas, standard workflows). Pairs especially well with agents: a fresh-context subagent loads only the skill it needs, without polluting the orchestrator.
- **Agents.** Fresh-context sub-conversations with their own system prompt. Full isolation: capability 8 (fresh instances are less correlated than continuations) is what makes isolation real rather than rhetorical. Use for: work needing independent judgment (premise 1, self-bias), long work that would pollute parent context (premise 2, long-context degradation), parallel execution, or any place stochastic-error re-sampling matters (premise 4, stochastic error).

### Pick the right vehicle

| Situation | Vehicle |
|---|---|
| Content the orchestrator itself must read and act on | Doc |
| Reusable capability multiple workers need | Skill |
| Work requiring isolation, fresh perspective, or parallelism | Agent |

The orchestrator's loop becomes very short: read state, pick a vehicle, dispatch, update state. It doesn't do the work itself. It decides where the work happens.

### What this rules out

- Inlining procedures, code, or long instructions into CLAUDE.md. The orchestrator's context is not a library.
- Doing stage work without spawning an agent. The pretext of "just this once" always returns.
- Loading a skill in the orchestrator for work that belongs in a subagent. Skills should land where the work happens, not in the always-on context.

### Corollary: load-bearing invariants travel with the delegation

Delegation moves work out of the orchestrator's context and into docs, skills, and agents. Each delegation target is a fresh surface where an invariant can be silently dropped (premise 3, coherence drift). Only invariants whose breach is **silent, cascading, and reachable from more than one surface** must be restated at each surface, not only at the dispatch site. This subset is what "load-bearing invariants" means throughout.

In this architecture the surfaces are typically three:

- **CLAUDE.md** catches biased launch prompts written by the orchestrator.
- **The stage doc** catches improvised procedures when the top-level rule is honored but details drift.
- **The agent definition** catches invocations outside the pipeline, where upstream steering never applied.

The count is descriptive, not prescriptive: restate at each surface the rule can enter from in your own pipeline. §2's budget still applies, so most rules don't clear the bar; only the ones that do.

---

## 4. Verify, don't trust

Workers defend their own output (premise 1, self-bias) and prefer cheap paths (premise 5, path-of-least-resistance), so self-reports aren't evidence the work got done. And any verdict, from a worker or a verifier, is a noisy sample of the underlying quality (premise 4, stochastic error): one draw isn't enough. Verify everything the orchestrator will route on using other LLMs (capability 7, judges predicates), not the same instance (capability 8, fresh-instance sampling).

### Corollary (a): at least two verifiers, more when the signal is noisier

Less-correlated samples reduce variance; one verifier's report is evidence, not proof, so two is the floor. Above two, more is monotonically better, with the marginal value rising in signal noise (premise 4) and sample independence (premise 8). Variance falls as 1/N only in the independent limit, so extra verifiers on the same model and framing buy less than the ideal bound.

### Corollary (b): distinct framings

The 1/N variance bound in (a) assumes independence. Two verifiers given identical instructions aren't independent; they share the blind spots the instructions force them into. Vary the framing: different postures (structured step-by-step re-derivation vs. skeptical-reader holistic pass), different phrasings of the question, different rubrics on the same target. The less the instructions overlap, the closer to independent the samples get, and the more each additional verifier buys. Framing is the floor; different models, tools, or context sizes reduce correlation further.

### Corollary (c): at least one free-form

A numeric score or enumerated verdict is cheap to route on, but easy to game when the worker can see it (retry loops that include prior scores, or workers told the rubric upfront). A numeric score is a noisy proxy for latent quality (premise 4), and a visible target invites gaming it (premise 5); optimizing the proxy under pressure diverges from the target. A free-form critique has no single number to climb; its feedback is qualitative and open-ended. Ship both: the structured verdict for routing, the free-form audit for content.

### Corollary (d): each verifier is framed adversarially

A verifier told "check whether this is correct" drifts toward confirming. Premise 1 (self-bias) reaches the verifier through its own instructions, even in a fresh context. State the job as finding errors, not evaluating correctness: the verifier has no loyalty to the work, and its goal is to break it. This is orthogonal to (b): adversarial posture applies per verifier, before any cross-verifier variation.

### Corollary (e): verification is a distinct stage, not a sub-step

A worker that spawns its own verifier inside its own stage hasn't escaped premise 1 (self-bias). The worker chooses the framing, the inputs, and what to show. The self-bias reaches the verifier through the curation, even though the verifier's context is fresh. Verification must be a stage the orchestrator dispatches separately: inputs come from state (or from artifacts the worker wrote, not selected), framing comes from the stage doc, and the verdict flows back to the orchestrator, not to the worker. The worker never sees the verifier; the orchestrator, not the worker, routes on the verdict.

---

## 5. Termination must be mechanical

The orchestrator is a program. Sequences, if/else, for-loops over agent lists, while-loops, early returns: ordinary control-flow shapes are fair game. The constraint is not on which shapes you can use; it's on the *predicate* that gates each branch, which is one of two kinds:

- **Mechanical**: predicate evaluated by numeric rules over the state JSON: `if state.errors_plateau_for >= 2: escalate()`.
- **LLM-judged**: predicate evaluated by the orchestrator itself reading an agent's output and deciding (capability 7, judges predicates). Input format is flexible; see corollary (c).

Both are legitimate for routing; pick based on what the predicate asks. Termination is the exception, as the corollaries make explicit.

### Corollary (a): runaway loops need a mechanical termination

Any loop that could run forever must have at least one mechanical branch on the termination path (a counter, a threshold, a strike limit). An LLM orchestrator will rationalize "one more try" indefinitely if termination depends only on its own judgment (premise 1, self-bias defending prior work; premise 3, drift from earlier stopping conditions).

### Corollary (b): termination triggers when marginal value stops

A counter caps pathological infinite loops, but the harder case is loops that keep executing while producing nothing (a retry returning the same score, a revision with no new feedback). The mechanical termination should fire when the *next* iteration is unlikely to add value, not only when some absolute ceiling is hit. Three strategies, ordered by how much data they require: (i) a conservative absolute cap when the loop is new and you have neither history nor a clean signal (corollary (a)'s counter, set tight); (ii) a budget cap at the count where marginal value historically saturates for that loop, once you have runs to fit it on; (iii) a delta trigger that escalates when Δ(score, feedback-novelty) falls below a threshold, when the per-iteration signal is reliable enough to threshold. Use the strongest strategy your data supports, and treat early runs as data collection for the next tier.

### Corollary (c): separate signal retries from noise retries

Long runs accumulate infrastructure failures (premise 10) alongside task-signal failures (premise 4). The two have different remedies: task failures feed termination; infrastructure failures get retried at the dispatch layer. Collapsing them into one counter means a flaky network trips termination on a task the pipeline would otherwise complete, or a genuinely stuck loop hides behind "retry, it was just a blip." Keep two counters: one for signal-driven failures (verifier REJECT, solver gave up, malformed model output); one for noise-driven failures (tool timeout, network blip, infrastructure parse error), bounded separately. The classifier is the *source*, not the surface: an unparseable response from the model is signal even though it surfaces at the parse step; a tool that returns garbage is noise even if downstream code can't tell them apart.

### Corollary (d): verdicts on hot paths, prose on rare branches

Capability 6 (reads-any-text) means the orchestrator reads any text, and §2 says structure costs tokens without buying safety unless it earns its keep. An enumerated verdict (`PASS/FAIL`, `NOVEL/INCREMENTAL/KNOWN`) is cheap to route on, so it's the default on hot paths (structure that earns its keep). On rare or ambiguous branches, the orchestrator can read the full artifact and decide; no verdict token needed. Verdicts buy efficiency, not correctness.

### Corollary (e): prefer self-recovery to escalation

Mechanical termination is required (corollary (a)); the backstop must exist and must rarely fire. Every escalation imposes a cost on someone who wasn't there. Design the pipeline so cheap self-recovery paths run out before termination fires: a fresh-instance retry (premise 4), a framing swap when the same class repeats, a coarser fallback. The delta predicate in (b) should catch genuine plateaus, not single stochastic misses, and (c)'s signal/noise separation keeps infrastructure noise out of the termination counter.

---

## 6. Parallelize independent dispatches

When two dispatches have no data dependency, run them concurrently. Run quality is unchanged; wall-clock time falls. Latency is part of premise 9's cost surface, so cutting it without changing token load is a pure win.

Constraint: parallelism is in dispatch, not in state mutation. Parallel branches write distinct keys, or the orchestrator gathers writes after both return. Concurrent writes to the same field race.

