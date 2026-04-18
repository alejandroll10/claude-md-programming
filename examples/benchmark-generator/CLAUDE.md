# CLAUDE.md: Benchmark Generator

Autonomously produce `target` verified `(problem, solution, tests)` triples on a named topic. Runs unattended.

## Pipeline state

Tracked in `state/pipeline_state.json`. Read at session start; update after every stage transition; commit every update atomically (§1 corollary (a) of `../../principles.md`).

Shape:

```json
{
  "topic": "<string>",
  "target": <int>,
  "problems_completed": 0,
  "current_problem_id": null,
  "current_stage": "propose",
  "stuck_count": 0,
  "recent_reject_classes": [],
  "status": "running"
}
```

Observability (one JSONL line per transition) is appended to `output/history.jsonl`, not stored in routing state (§1 corollary (e)). The orchestrator never reads it for routing; the `propose` stage does scan it once per invocation to build a de-duplication list of prior titles, which is worker input, not a routing decision.

Line shape:

```json
{
  "ts": "<ISO 8601 UTC>",
  "stage": "propose" | "solve" | "verify",
  "verdict": "<stage verdict, e.g. PROPOSED, SOLVED, ACCEPT, REJECT, ERROR>",
  "id": "<problem id or null before mint>",
  "title": "<problem title, set by propose; null elsewhere>",
  "reject_classes": [{"verifier": "structured" | "skeptic", "class": "<tag>"}] | null,
  "notes": "<free-form, optional>"
}
```

`title` is populated only by `propose`. `reject_classes` is populated only by `verify` on REJECT and carries the same tags the verify stage writes into `recent_reject_classes` in state (see termination). All other fields required every line.

## Pipeline graph

```
┌──── loop while problems_completed < target ────┐
│                                                │
│  propose  ──→  solve  ──→  verify              │
│     ↑                         │                │
│     ├── REJECT (++stuck) ─────┤                │
│     └── ACCEPT (++done) ──────┘                │
│                                                │
│  if stuck_count >= 3: ESCALATE → terminate     │
└────────────────────────────────────────────────┘
```

Orchestrator loop (§1):

```
while state.status == "running":
    state   = read("state/pipeline_state.json")
    stage   = state.current_stage
    doc     = read(f"docs/stage_{stage}.md")
    verdict = dispatch(stage, doc, state)        # fresh-context subagent
    state   = transition(state, verdict)         # per table below
    write_atomic("state/pipeline_state.json", state)
    append("output/history.jsonl", event)
    commit(f"pipeline: {stage} → {verdict}")
```

Top-level transitions:

| From    | Verdict  | Next                            | Notes                          |
|---------|----------|---------------------------------|--------------------------------|
| propose | PROPOSED | solve                           | new `current_problem_id`       |
| solve   | SOLVED   | verify                          |                                |
| verify  | ACCEPT   | propose (++problems_completed)  | reset `stuck_count` to 0       |
| verify  | REJECT   | propose (++stuck_count)         | drop current triple            |
| any     | ERROR    | terminate                       | write `output/error_report.md` |

Local routing (verdict space within each stage) lives in the stage doc.

## Load-bearing invariants

Project-specific rules whose silent breach corrupts downstream work. Per §3's delegation corollary, they are stated at each surface: here, in each stage doc, and in each agent definition.

1. **Every accepted triple passes two independent verifiers under distinct framings.** One verifier is a noisy sample (premise 4, stochastic error); identical framings share blind spots (§4 corollaries (a), (b)).
2. **Verifiers never see the solver's context.** Verification is a distinct stage dispatched by this orchestrator (§4 corollary (e)). The solver does not choose the verifier's framing.
3. **One commit per stage transition.** Atomic and durable (§1 corollary (a)). Never batch.

## Stages

- `propose` → `docs/stage_propose.md`
- `solve` → `docs/stage_solve.md`
- `verify` → `docs/stage_verify.md`

## Termination

Mechanical (§5). The loop ends when any of:

- `problems_completed >= target`: set `status: "complete"`.
- `stuck_count >= 3`: budget ceiling. Set `status: "stuck"`, write `output/stuck_report.md`, halt.
- `recent_reject_classes` has two entries (each entry is one REJECT round's set of `{verifier, class}` failures) and the two are structurally equal, delta-based (§5 corollary (b)): the feedback isn't moving, so a third attempt is unlikely to. Set `status: "stuck"`, halt. The verify stage maintains this list: it appends on REJECT (trimming to the last two rounds), and resets to `[]` on ACCEPT. Class tags come from the closed set declared in each verifier's agent definition.

No termination path depends only on LLM judgment.

## Resume and self-recovery

**Resume (§1 corollary (g)).** State, artifacts, and the history log are committed together at the end of each loop iteration. On startup, the orchestrator reads `state/pipeline_state.json` and re-enters the loop. If the working tree has uncommitted changes (a crash mid-stage), discard them (`git reset --hard HEAD`) so the stage is re-run cleanly from the prior commit. There is no first-run branch; the first run starts with the committed initial state.

**Self-recovery (§5 corollary (e)).** The REJECT → propose path is the signal-level recovery: a failed triple triggers a new attempt, not an escalation. Termination (budget, delta) is the backstop, not the first response.

Infrastructure failures (tool timeout, rate limit, parse failure) are retried at the dispatch layer: each agent invocation gets up to 3 independent attempts. In the verify stage, the structured and skeptic retry budgets are independent; a timeout on one does not charge the other. These retries do **not** feed `stuck_count` (§5 corollary (c), separating signal and noise counters). A stage emits `ERROR` to the transition table only after its own retry budget is exhausted.

## Commit protocol

One commit per stage transition. Prefix: `pipeline:` for state changes, `artifact:` for stage output. Never batch.
