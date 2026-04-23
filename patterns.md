# Patterns

Operational patterns that cross surfaces (orchestrator, stages, agents) and recur across production pipelines. Read `principles.md` first; this doc is applied, not foundational.

Each pattern names a shape, the premises and principles it serves, when it earns its place, and the antipatterns it resists.

## Preflight / post-check bookends

Every stage body has two gates around the work: a **preflight** that verifies upstream inputs are fresh and well-formed before dispatch, and a **post-check** that verifies this stage's outputs before the transition commits.

Both are mechanical (§5): they run numeric rules over state and artifacts, not LLM judgment. That is the point.

Shape:

```
dispatch stage N:
  preflight:
    for each upstream artifact required:
      exists? mtime > pipeline_state.history[0].timestamp? schema / size / content ok?
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

- **Freshness anchor is the pipeline-start timestamp, not the calendar date.** Long runs cross midnight; a file written at 23:50 is fresh when the downstream stage runs at 00:30. Use `pipeline_state.history[0].timestamp` (see `state-schema-patterns.md`, "Earn its place") as the anchor.
- **Each stage declares its own preflight and post-check in its stage doc**, naming the exact files and predicates. The mandate ("every stage verifies freshness") belongs in CLAUDE.md; the per-stage procedure belongs in the stage doc (see `invariants.md`, "Mandate vs procedure").
- **Preflight of stage N replicates the post-check of stages N depends on.** Intentional redundancy: the producer's post-check catches producer-side failure; the consumer's preflight catches cross-stage corruption between commit and consume (rollback orphans, manual edits, multi-host races).
- **Predicates beyond existence.** Empty files pass existence. Add at least one of: size threshold, schema parse, expected-key presence, date-column equality, row-count lower bound. The cheapest predicate that covers a known failure mode for the artifact type.
- **Failures are signal, not noise (§5(c)).** A stale input or a malformed output is a task-level failure counted against the signal-failure counter. Distinct from dispatch-layer retries for infrastructure failures.

Antipatterns:

- **Existence-only preflight.** Passes for empty or truncated files. Add a content-side predicate.
- **Calendar-date freshness check.** Fails across midnight. Use the pipeline-start marker.
- **Post-check inside the agent.** The agent defends its own output (premise 1). Post-check is the orchestrator's job, reading the artifact fresh.
- **Stage that fails preflight and continues on a fallback.** Silent graceful degradation (§5(f)). Record the downgrade in state or rerun the producer.

## Correction-aware verifier verdict spaces

The canonical §4 picture has verifiers emitting a binary `ACCEPT` / `REJECT`. Some verifier stages instead emit enumerated corrections that a downstream consumer applies without re-dispatching the producer:

- `PASS`: no errors found.
- `SOFT-FAIL`: errors found; the verifier enumerated them; a downstream aggregator or consumer applies the corrections.
- `HARD-FAIL`: errors severe enough that the producer must rerun with explicit feedback.

When the extra verdict earns its place:

- The producer's output is expensive to regenerate (a multi-agent forecast, a long analysis, a several-thousand-token research doc).
- The errors are local and mechanical (a wrong date, a broken ticker symbol, a misapplied unit, a citation to a stale source).
- A downstream stage already integrates multiple inputs and consuming corrections is cheaper than re-dispatching.

When it does not:

- If the "correction" would change the artifact's conclusions, it is not a correction. Verdict is `HARD-FAIL`; producer reruns.
- If the consumer applies corrections without recording which were applied, provenance is lost. The downstream artifact must list what was changed (ledger pattern; see `state-schema-patterns.md`, "Domain ledgers").

Invariants this verdict space needs:

- **The verifier does not apply its own corrections.** §4(a) separation: the verifier enumerates, the downstream stage applies. A verifier that also edits the artifact re-imports self-bias (premise 1) by forcing its own interpretation of the fix.
- **HARD-FAIL retry budget is bounded** (§5 corollary (a)). Two strikes per producer-verifier pair is a common budget; after that, escalate rather than loop.
- **SOFT-FAIL counts toward the delta trigger** (§5(b), §5(c)). Two consecutive rounds producing the same class of SOFT-FAIL on the same producer is a stalled loop wearing the mask of progress; terminate or escalate.

Compared to binary: the extra verdict buys cycle-level efficiency when corrections are genuinely local. It is not a substitute for the §4 gate. The verifier still runs in a fresh context, is still framed adversarially, and still emits a structured verdict plus a free-form critique.

## Multi-mode orchestrators

One CLAUDE.md can serve multiple flows: a short-form scan, a full rebuild, a maintenance-only run. A trigger phrase picks the mode.

Shape:

- **`mode` is a routing-state field** (see `state-schema-patterns.md`, "Mode or variant flag"), set before `current_stage` on each run. Closed enum matching the flows declared in CLAUDE.md.
- **The orchestrator reads `mode` before `current_stage`.** Each mode has its own top-level transition table; `current_stage` is interpreted within the active mode.
- **Trigger phrases map to modes in a table in CLAUDE.md.** The mapping is orchestrator-level routing; it does not belong in stage docs or agent definitions.

Example shape in CLAUDE.md:

```
| Trigger phrase                       | Mode   | Doc                  |
|---|---|---|
| "quick scan" / "daily scan"          | scan   | `docs/mode_scan.md`  |
| "full run" / "rebuild"               | full   | `docs/mode_full.md`  |
```

- **Mode is set once per run, never changed mid-run.** Mid-run mode swaps are schema-level rewrites (§1(i)) and should be handled as a rollback-plus-new-run (§1(j)), not as a transition.
- **Stages shared between modes have one stage doc each.** Mode-specific preconditions are documented as mode-guards at the top of the stage doc; the stage body does not branch per mode beyond what its preflight requires.

Antipattern: branching on `mode` inside every stage body. That puts mode-level routing in N stages; one breaks, routing drifts (premise 3). Keep mode routing in the top-level transition table.

## User-input stages

Some pipelines legitimately block for a human-supplied value before proceeding: a parameter the user adjusts between runs, a snapshot captured from an external system the orchestrator cannot query, a signoff on an irreversible step. The principles otherwise assume every dispatch returns a verdict from an agent or a script, so these stages need explicit handling.

Shape:

- **Dedicated input stage at the point in the flow where the value is needed.** Named, declared in the pipeline graph, with its own entry in the transition table. Not a side-effect of another stage.
- **The stage reads nothing and dispatches nothing; it blocks on a user-supplied value.** The orchestrator pauses, asks, and records the value in routing state. The next stage's preflight verifies the value was recorded *this run* (not carried over from a prior run).
- **The input carries provenance** (§1(f); `state-schema-patterns.md`, "Input snapshot with provenance"): value, source, timestamp, a consistency check where one is cheap (checksum, an invariant the next stage can validate).
- **No silent fallback.** A user-input stage that substitutes a cached value when the user is absent is a graceful-degradation event (§5(f)): record the downgrade and count it against the signal-failure budget. Silent defaulting hides a half-automated decision.
- **Resume semantics are explicit.** If the run crashed after the user supplied the value, resume must not re-ask. The value lives in committed state; `status == "running"` with the field populated means proceed, not re-prompt.
- **Observability posts the handoff.** When the orchestrator blocks for input, an observability entry (Slack, dashboard, email) announces the block; when the value arrives, a second entry confirms. Without this, a remote observer cannot distinguish a blocked run from a crashed one.

Antipattern: treating the user as just another agent. The user is asynchronous and untyped, and the premises about LLM sampling (4, 8) do not apply to human inputs. Every user-supplied value needs its own validation at the next stage's preflight, not an implicit trust.
