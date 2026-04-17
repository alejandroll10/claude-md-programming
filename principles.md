# Principles

## Premises: four LLM failure modes

Every principle here is derived from one or more of four weaknesses of LLMs as a programming substrate. These aren't bugs that a better model will fix — they're properties of how autoregressive generation over a finite context window behaves, and they shape what "reliable" means in this regime.

1. **Self-bias.** An LLM that has produced context gets pulled toward defending and continuing it. It rationalizes its prior output instead of evaluating it freshly. *Consequence:* the same LLM instance cannot reliably grade its own work.

2. **Long-context degradation.** As context grows, recall and reasoning quality degrade. The model misses details in the middle of long inputs, forgets instructions stated at the top, and conflates similar items. *Consequence:* anything the model doesn't strictly need, hurts.

3. **Coherence drift.** Across many steps, invariants get forgotten, overridden, or silently reinterpreted. Small local departures compound. *Consequence:* rules that must hold across a whole run need redundant enforcement, not a single statement.

4. **Stochastic error.** Even on tasks the model can do, it fails on some fraction of attempts — a sign slip, an off-by-one, a dropped constraint, a misread token. The errors are noise from a sampling process, not a ceiling on capability. *Consequence:* a single pass is unreliable even from a capable agent. A different instance with the same model often catches the error, because the error roll is independent. This is what makes adversarial review and multi-pass verification load-bearing rather than decorative.

Each principle below can be read as "given these four failure modes, do X." If a principle doesn't trace to at least one of them, it is decoration.

---

## 1. CLAUDE.md is the orchestrator — not a manual, and not a worker

The CLAUDE.md at the root of a project is always loaded into context. Treat it as the body of a program's main loop.

Two things it is **not**:

- **Not a manual.** Don't write stage-by-stage procedures, examples, or edge-case notes into it "just in case." Those belong in per-stage docs loaded on demand.
- **Not a worker.** The orchestrator does not do the work of the stages. It doesn't analyze the artifact, write the forecast, or review the proof. It dispatches to agents and reads their outputs. The moment the orchestrator starts producing stage-level content itself, its context fills with domain material and it loses the distance that makes routing reliable — the three LLM failure modes (self-bias, long-context degradation, coherence drift) re-enter through the front door.

The orchestrator's job is small and structural: read the current state, load the one doc it needs for this step, dispatch the right work to an agent, read back a verdict or artifact, update state, repeat. Everything else — how to actually do a step, examples, rationale, edge cases — lives in a separate doc loaded on demand, and the *doing* happens inside fresh-context subagents.

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
