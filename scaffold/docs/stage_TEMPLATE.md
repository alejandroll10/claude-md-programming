# Stage: <stage_name>

<One-sentence purpose for this stage. What artifact does it produce, or what routing decision does it gate?>

## Inputs

<Paths the stage reads, one per line. Paths, not bodies (§2, `../subagents-best-practices.md` Layer 3).>

- `state/pipeline_state.json`
- `<other/required/path>`

## Preflight

Before dispatch, verify every input:

- Exists.
- `mtime > pipeline_state.pipeline_started_at` (freshness anchor; §1 corollary (a), `../stages-best-practices.md`).
- <Schema / size / content predicate appropriate to the artifact. Not just existence: empty files pass existence.>

If any fail: STOP, re-run the producing stage. Do not dispatch.

## Dispatch

<One of: agent / script / skill. See `../principles.md` §3 for vehicle choice.>

- **Agent:** dispatch `.claude/agents/<agent_name>.md` with the dispatch prompt `<one-line input spec, path-based>`.
- **Script:** run `<script path>` with `<args>`.
- **Skill:** loaded inside the dispatched agent via its frontmatter.

## Post-check

After dispatch returns, verify every artifact this stage produces:

- Exists.
- `mtime > dispatch_start_time`.
- <Schema / size / content predicate.>

If any fail: mark stage failed, increment the signal-failure counter (§5 corollary (c)), do not transition.

## Verdict space

Closed set of verdicts this stage emits. Declared here so the orchestrator's transition table stays grounded.

- `<VERDICT_A>`: <meaning>.
- `<VERDICT_B>`: <meaning>.
- `ERROR`: <unrecoverable; routes to terminate per top-level transitions>.

## Outgoing edges

| Verdict        | Next stage       | State update                          |
|----------------|------------------|---------------------------------------|
| `<VERDICT_A>`  | `<stage_x>`      | `<field_1> = <value>`                 |
| `<VERDICT_B>`  | `<stage_y>`      | `<counter> += 1`                      |
| `ERROR`        | terminate        | write `output/error_report.md`        |

## Restated invariants

<Only the load-bearing invariants from CLAUDE.md that this stage's body can breach. Not all invariants. See `../invariants.md` "Multi-surface restatement".>

1. <invariant text, named where relevant to this stage's procedure>.
