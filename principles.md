# Principles

## 1. CLAUDE.md is the orchestrator, not a manual

The CLAUDE.md at the root of a project is always loaded into context. Treat it as the body of a program's main loop — not as a manual you write things into "just in case."

The orchestrator's job is small: read the current state, load the one doc it needs for this step, dispatch the right work, update state, repeat. Everything else — how to actually do a step, examples, rationale, edge cases — lives in a separate doc loaded on demand.

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
