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

## 1. CLAUDE.md is the orchestrator — not a manual, and not a worker

The CLAUDE.md at the root of a project is always loaded into context. Treat it as the body of a program's main loop.

Two things it is **not**:

- **Not a manual.** Don't write stage-by-stage procedures, examples, or edge-case notes into it "just in case." Those belong in per-stage docs loaded on demand.
- **Not a worker.** The orchestrator does not do the work of the stages. It doesn't analyze the artifact, write the forecast, or review the proof. It dispatches to agents and reads their outputs. The moment the orchestrator starts producing stage-level content itself, its context fills with domain material and it loses the distance that makes routing reliable — the three LLM failure modes (self-bias, long-context degradation, coherence drift) re-enter through the front door.

The orchestrator's job is small and structural: read the current state, load the one doc it needs for this step, dispatch the right work to an agent, read back a verdict or artifact, update state, repeat. Everything else — how to actually do a step, examples, rationale, edge cases — lives in a separate doc loaded on demand, and the *doing* happens inside fresh-context subagents.

### The big-picture graph belongs in CLAUDE.md

The orchestrator needs to know, at a glance, where it is in the whole pipeline. If knowing "what comes after stage N" requires reading stage N's doc to find out, every routing decision pays for an extra doc read — and the orchestrator can't reason about future stages at all without loading them.

So the always-loaded CLAUDE.md pays the token cost of the **overall pipeline graph** — the stage list, the gates, the main loops, the escalation table. It does not pay the cost of each stage's procedure. The graph is cheap in tokens; procedures are not.

What lives in stage docs is the *local* routing: this stage's verdict space, and which stage each verdict points to next. The high-level graph in CLAUDE.md points at the stages; the stages own their own outgoing edges.

### Pseudocode

```
while state.status == "running":
    stage   = state.current_stage
    doc     = read(f"docs/{stage}.md")        # loaded on demand, not upfront
    verdict = run_stage(doc, state)            # may dispatch agents, write files
    state   = transition(state, verdict)       # mechanical: verdict → next stage
    commit(state)
```

The CLAUDE.md contains the `while`, the shape of `state`, and the `transition` table. It does not contain the body of `run_stage` for every stage — those are the `docs/*.md` files.

### Branches come in two flavors

The `transition` step is a big `if/elif`. Two kinds of predicates live inside it:

- **Mechanical** — evaluated by numeric rules over the state JSON:
  `if state.errors_plateau_for >= 2: escalate()`
- **LLM-judged** — evaluated by the orchestrator itself (which is an LLM) reading the agent's output. The orchestrator doesn't need a parseable boolean. It can read a full audit report and decide whether to advance, go back, or escalate.

Because the orchestrator is an LLM, `if` is not restricted to bools. It can route on free-form content. A classical `if verdict == "PASS"` is still useful — but as an **optimization**, not a requirement:

- A short enumerated verdict (`PASS/FAIL`, `NOVEL/INCREMENTAL/KNOWN`) saves tokens: the orchestrator can match on it without re-reading the whole artifact.
- Routing on a fixed token is more reliable than routing on re-interpreted prose.
- The verdict keeps the orchestrator's context small — a Markov-friendly property.

But none of that is load-bearing. If an agent writes a long free-form audit with no summary line, the orchestrator can still read it and decide. Verdicts are for cheap, common paths; for rare or ambiguous ones, reading the body is fine.

The discipline that keeps this a program rather than vibes:

1. **Prefer enumerated verdicts on hot paths.** When a branch is taken often, the summary token pays for itself in tokens and reliability. When it's taken rarely, the orchestrator can afford to read.
2. **Every loop that could run forever needs at least one mechanical branch on the exit path** — a counter, a threshold, a strike limit. Otherwise the LLM orchestrator will rationalize another attempt indefinitely. This is the one place LLM judgment alone is not enough.

### What this rules out

- Putting stage-by-stage procedures inline in CLAUDE.md. They bloat always-on context and push the model toward long-context degradation.
- "See how it's going and decide what to do" branches with no enumerated verdict set. That isn't a branch; it's a vibe.
- Pure-LLM loops with no mechanical exit. Eventually the model talks itself into one more try.

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
