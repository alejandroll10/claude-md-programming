# CLAUDE.md — Benchmark Generator

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
  "status": "running",
  "history": []
}
```

`history` is append-only observability (§1 corollary (e)). The orchestrator does not route on it.

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

Project-specific rules whose silent breach corrupts downstream work. Per §5, they are stated here, in the relevant stage doc, and in each agent definition — any one layer can drift, three cannot drift in lockstep.

1. **Every accepted triple passes two independent verifiers under distinct framings.** One verifier is a noisy sample (premise 4, stochastic error); identical framings share blind spots (§4 corollaries (a), (b)).
2. **Verifiers never see the solver's context.** Verification is a distinct stage dispatched by this orchestrator (§4 corollary (e)). The solver does not choose the verifier's framing.
3. **One commit per stage transition.** Atomic and durable (§1 corollary (a)). Never batch.

## Stages

- `propose` → `docs/stage_propose.md`
- `solve` → `docs/stage_solve.md`
- `verify` → `docs/stage_verify.md`

## Termination

Mechanical (§6). The loop ends when either:

- `problems_completed >= target` — set `status: "complete"`.
- `stuck_count >= 3` — set `status: "stuck"`, write `output/stuck_report.md`, halt.

No termination path depends only on LLM judgment. The budget exists precisely so "one more try" can't compound.

## Commit protocol

One commit per stage transition. Prefix: `pipeline:` for state changes, `artifact:` for stage output. Never batch.
