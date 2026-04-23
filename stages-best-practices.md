# Stages: best practices

How to author the stage docs under `docs/*.md` that the orchestrator loads on demand and acts on. Parallel to `subagents-best-practices.md` (agent files) and `skills-best-practices.md` (skill files). Read `principles.md` first; this doc is operational, not foundational.

A stage doc owns the local verdict space, the outgoing edges, and the procedure for the stage body. Two shapes recur across stage authors regardless of domain and do not have a natural home in the other docs: the preflight/post-check that bookends every stage body, and the special shape of a stage that blocks on user input.

## Preflight / post-check bookends

Every stage body has two gates around the work: a **preflight** that verifies upstream inputs are fresh and well-formed before dispatch, and a **post-check** that verifies this stage's outputs before the transition commits.

Both are mechanical (§5): they run numeric rules over state and artifacts, not LLM judgment. That is the point.

Shape:

```
dispatch stage N:
  preflight:
    for each upstream artifact required:
      exists? mtime > pipeline_state.<freshness_anchor>? schema / size / content ok?
    if any fail: STOP, rerun the producing stage
  run stage N (agent or script)
  post-check:
    for each artifact this stage claims to produce:
      exists? mtime > dispatch-start? schema / size / content ok?
    if any fail: mark stage failed (signal counter per §5(c)); do not transition
```

Why both:

- **Preflight** catches stale leftovers from a crashed or rolled-back prior run, and cross-stage corruption the producer's own post-check could not see (§1 corollary (a)).
- **Post-check** catches silent producer failure: an agent dispatch returned, but the artifact is empty or malformed. Without the post-check, the next stage consumes garbage and "dispatch succeeded" is the only signal the orchestrator has.

Key properties:

- **Freshness anchor is the pipeline-start timestamp, not the calendar date.** Long runs cross midnight; a file written at 23:50 is fresh when the downstream stage runs at 00:30. Two common choices: a dedicated routing-state field (`pipeline_started_at`, set at launch; used by `examples/scheduled-curator/` and `scaffold/`) or the first entry of a `history` array kept in routing state (`pipeline_state.history[0].timestamp`; see `state-schema-patterns.md`, "Earn its place"). Pick one per pipeline and use it everywhere; do not mix.
- **Each stage declares its own preflight and post-check in its stage doc**, naming the exact files and predicates. The mandate ("every stage verifies freshness") belongs in CLAUDE.md; the per-stage procedure belongs in the stage doc (see `invariants.md`, "Mandate vs procedure").
- **Preflight of stage N replicates the post-check of stages N depends on.** Intentional redundancy: the producer's post-check catches producer-side failure; the consumer's preflight catches cross-stage corruption between commit and consume (rollback orphans, manual edits, multi-host races).
- **Predicates beyond existence.** Empty files pass existence. Add at least one of: size threshold, schema parse, expected-key presence, date-column equality, row-count lower bound. The cheapest predicate that covers a known failure mode for the artifact type.
- **Failures are signal, not noise (§5 corollary (c)).** A stale input or a malformed output is a task-level failure counted against the signal-failure counter. Distinct from dispatch-layer retries for infrastructure failures.

Antipatterns:

- **Existence-only preflight.** Passes for empty or truncated files. Add a content-side predicate.
- **Calendar-date freshness check.** Fails across midnight. Use the pipeline-start marker.
- **Post-check inside the agent.** The agent defends its own output (premise 1). Post-check is the orchestrator's job, reading the artifact fresh.
- **Stage that fails preflight and continues on a fallback.** Silent graceful degradation (§5 corollary (f)). Record the downgrade in state or rerun the producer.

## User-input stages

Some pipelines legitimately block for a human-supplied value before proceeding: a parameter the user adjusts between runs, a snapshot captured from an external system the orchestrator cannot query, a signoff on an irreversible step. The principles otherwise assume every dispatch returns a verdict from an agent or a script, so these stages need explicit handling.

Shape:

- **Dedicated input stage at the point in the flow where the value is needed.** Named, declared in the pipeline graph, with its own entry in the transition table. Not a side-effect of another stage.
- **The stage reads nothing and dispatches nothing; it blocks on a user-supplied value.** The orchestrator pauses, asks, and records the value in routing state. The next stage's preflight verifies the value was recorded *this run* (not carried over from a prior run).
- **The input carries provenance** (`state-schema-patterns.md`, "Input snapshot with provenance"): value, source, timestamp, a consistency check where one is cheap (checksum, an invariant the next stage can validate).
- **No silent fallback.** A user-input stage that substitutes a cached value when the user is absent is a graceful-degradation event (§5 corollary (f)): record the downgrade and count it against the signal-failure budget. Silent defaulting hides a half-automated decision.
- **Resume semantics are explicit.** If the run crashed after the user supplied the value, resume must not re-ask. The value lives in committed state; `status == "running"` with the field populated means proceed, not re-prompt.
- **Observability posts the handoff.** When the orchestrator blocks for input, an observability entry (Slack, dashboard, email) announces the block; when the value arrives, a second entry confirms. Without this, a remote observer cannot distinguish a blocked run from a crashed one.

Antipattern: treating the user as just another agent. The user is asynchronous and untyped, and the premises about LLM sampling (4, 8) do not apply to human inputs. Every user-supplied value needs its own validation at the next stage's preflight, not an implicit trust.
