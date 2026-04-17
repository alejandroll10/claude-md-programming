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

- **Mechanical** — evaluated by numeric rules:
  `if state.errors_plateau_for >= 2: escalate()`
- **LLM-judged** — evaluated by a bounded-verdict subagent:
  `if verdict == "PASS": proceed()`

Both are legitimate. The discipline that keeps this a program rather than vibes:

1. Every LLM-judged branch returns one of a **fixed, enumerated set of verdicts** (e.g., `PASS/FAIL`, `NOVEL/INCREMENTAL/KNOWN`). Not free-form prose.
2. Every loop that could, in principle, run forever has **at least one mechanical branch** on the exit path — a counter, a threshold, a strike limit. Otherwise the LLM will rationalize another attempt indefinitely.

### What this rules out

- Putting stage-by-stage procedures inline in CLAUDE.md. They bloat always-on context and push the model toward long-context degradation.
- "See how it's going and decide what to do" branches with no enumerated verdict set. That isn't a branch; it's a vibe.
- Pure-LLM loops with no mechanical exit. Eventually the model talks itself into one more try.
