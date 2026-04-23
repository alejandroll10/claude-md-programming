# CLAUDE.md: <pipeline name>

<One-sentence purpose. What does this pipeline produce, autonomously, over hours to days?>

## Pipeline state

Tracked in `state/pipeline_state.json`. Read at session start; update after every stage transition; commit every update atomically (§1 corollary (g) of `../principles.md`).

Shape:

```json
{
  "current_stage": "<stage_a>",
  "status": "running",
  "pipeline_started_at": null,        // ISO 8601 UTC, set at first stage entry; freshness anchor for §1(a)
  "fallback_used": null,               // non-null when a stage substituted a weaker input (§5 corollary (f))
  "<counter_name>": 0,
  "<other_routing_field>": null
}
```

<Declare every routing field here. Do not add fields in stages without declaring a schema change (§1 corollary (i)). For reference artifacts, domain ledgers, and observability, use separate files (see `../state-schema-patterns.md`).>

Observability (one JSONL line per transition) is appended to `output/history.jsonl`, not stored in routing state (§1 corollary (e)). The orchestrator never reads it for routing.

### Environmental ground truth (delete if closed-world)

<If the pipeline reads external data, credentials, or services, capture them once at pipeline entry in a reference artifact every stage reads (§1 corollary (f)). Declare the artifact path and what it contains here. Delete this subsection if the pipeline is closed-world.>

- Reference artifact: `<path>`, <one-line description>.

## Pipeline graph

```
<ASCII diagram of the stage graph: stages, edges, mechanical exits.>
```

Orchestrator loop (§1):

```
while state.status == "running":
    state   = read("state/pipeline_state.json")
    stage   = state.current_stage
    doc     = read(f"docs/stage_{stage}.md")
    verdict = dispatch(stage, doc, state)        # fresh-context subagent or script
    state   = transition(state, verdict)         # per table below
    write_atomic("state/pipeline_state.json", state)
    append("output/history.jsonl", event)
    commit(f"pipeline: {stage} → {verdict}")
```

Top-level transitions:

| From        | Verdict   | Next          | Notes                          |
|-------------|-----------|---------------|--------------------------------|
| <stage_a>   | <V_OK>    | <stage_b>     |                                |
| <stage_b>   | <V_ACC>   | <stage_a>     | <reset/advance counters>       |
| <stage_b>   | <V_REJ>   | <stage_a>     | <++counter>                    |
| any         | ERROR     | terminate     | write `output/error_report.md` |

Local routing (the verdict space within each stage) lives in the stage doc.

### User-input stages (delete if none)

<If any stage blocks on a human-supplied value, declare it as a first-class stage here with its own transition-table entries. Not a side-effect of another stage. See `../stages-best-practices.md` "User-input stages".>

### Parallelism (§6)

<Identify stage dispatches that have no data dependency and run them concurrently. Concurrent writes to the same state field race; parallel branches must write distinct keys or be gathered after all return.>

## Load-bearing invariants

Rules whose silent breach corrupts downstream work. Per `../invariants.md`, list only rules that are silent, cascading, and reachable from more than one entry surface. Restate at each surface the rule can enter from; see `../invariants.md` "Multi-surface restatement" and "From incident to rule" for placement and wording.

1. **<invariant name>.** <Body: name the shortcut, cite the reason (incident / system property / structural distance / premise-5).>
2. <...>

## Stages

- `<stage_a>` → `docs/stage_<stage_a>.md`
- `<stage_b>` → `docs/stage_<stage_b>.md`

## Termination

Mechanical (§5). The loop ends when any of:

- `<condition_1>`: set `status: "complete"`.
- `<counter_name> >= <N>`: budget ceiling. Set `status: "stuck"`, write `output/stuck_report.md`, halt.
- <optional delta trigger: equal-last-two rejection classes, no-progress over K rounds, etc.>

No termination path depends only on LLM judgment. See §5 corollary (b) for strategy choice (absolute cap / budget cap / delta trigger) based on the data you have.

## Resume and self-recovery

**Resume (§1 corollary (g)).** State, artifacts, and the history log are committed together at the end of each loop iteration. On startup, read `state/pipeline_state.json` and re-enter the loop. If the working tree has uncommitted changes (crash mid-stage), discard them (`git reset --hard HEAD`) so the stage is re-run cleanly from the prior commit. The first run starts with the committed initial state (§1 corollary (h)).

**Self-recovery (§5 corollary (e)).** <Name the in-pipeline recovery path (e.g., REJECT → retry, fresh-instance on parse failure). Termination is the backstop, not the first response.>

Infrastructure failures (tool timeout, rate limit, parse failure) are retried at the dispatch layer (bounded, e.g., 3 attempts per dispatch). These retries do **not** feed the signal-failure counter (§5 corollary (c), separating signal and noise).

**Graceful degradation (§5 corollary (f)).** A stage that substitutes a weaker input for a missing one must record the downgrade in `state.fallback_used` and count it against the signal-failure counter. A silent fallback is a broken stage.

## Commit protocol

One commit per stage transition, prefixed with the stage and verdict. Never batch. On multi-host pipelines, push after each commit so peer hosts see the update (§1 corollary (g)).
