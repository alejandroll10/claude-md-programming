# State schema: patterns

How to shape the routing-state JSON for a pipeline. Read `principles.md` first; this doc is a pattern catalog, not foundations. The principles call routing state "compact, no transcripts, schema declared, not emergent" (§1, §1 corollary (i), §2). That's necessary but not sufficient for designing the actual fields. This doc fills the gap with patterns from real pipelines.

## Required fields (every pipeline has these)

**`current_stage` (or `current_step`).** The pointer into the pipeline graph. The orchestrator's first read every turn. Always a string from a closed enum that matches the stage list in CLAUDE.md.

**`status`.** The orchestrator's loop condition. Closed enum, typically `not_started` / `running` / `complete` / `stuck`. The `while state.status == "running"` in §1's pseudocode reads this field.

These two fields together define resumability. A new run reads them and either starts (`not_started`) or re-enters at `current_stage` (`running`). The `complete` and `stuck` terminal states stop the loop and let observability take over.

## Common patterns (most pipelines)

**Counter family.** Per-loop counters that feed termination predicates (§5). One counter per loop body, one per escalation stage. Real pipelines accumulate many: `problem_attempt`, `idea_round`, `theory_version`, `referee_round`, `pivot_round`, `stuck_count`, `fix_empirics_rounds`. Each has a budget cap somewhere in CLAUDE.md or a stage doc. Counters reset only on the transition that ends their loop (`stuck_count` resets on ACCEPT, not on any other event). The reset rules belong with the counter declaration so the orchestrator does not invent them per run.

**Mode or variant flag.** When one CLAUDE.md serves multiple flows (autopilot has `daily_scan` vs. `rebalance`), the active flow is a state field. The orchestrator routes on it before consulting `current_stage`.

**Input snapshot with provenance.** Inputs the pipeline captures from outside (drifted weights, a manual seed, a user-supplied target) live in state with three things: the value, the source (where and when it came from), and a consistency check. autopilot's `drifted_weights` ships with `drifted_weights_source` (prose attribution) and `drifted_weights_total: 100.0` (stages can reject if it does not sum). Without provenance, a stale or corrupted snapshot is invisible; with it, downstream stages have something to fail loudly on.

**Sparse fill-as-you-go dicts.** When stages contribute scores, verdicts, or partial results that accumulate across iterations (token5's `scores`), declare the dict but do not pre-populate keys. Each stage writes its own key. Premise 3 (coherence drift) bites if every stage is asked to "make sure all the keys are there."

**Nullable transitions.** Some fields are meaningfully absent until a stage produces them. token5 carries `pivot_resolved: null` until the puzzle-triage stage emits a verdict. Null is the schema-declared "not yet observed" value; do not conflate with missing keys.

**Cross-cycle context.** Pipelines that run repeatedly carry narrative state from one cycle to the next, distinct from append-only history. autopilot's `prior_cycle_context` is one slot, overwritten each cycle with a short prose summary the next cycle's stages can read. Different from the history array: history is append-only and grows; cross-cycle context is a slot that gets replaced.

## Pointers, not bodies

State holds *paths and identifiers*, not the artifacts they point to. `current_problem_id: 42` not the problem statement; `verdict_path: "output/verify_42.json"` not the verdict. §2 (context costly) applies to state because state is read at every transition. A 2KB state file read 1000 times is 2MB; a 200KB state file is 200MB. The same artifact rule that applies to dispatch prompts applies to state.

## The history-array tension

Both real pipelines have a `history` array of `{timestamp, event/step, summary}`. This is borderline observability vs. routing. The principle (§1 corollary (e)) says routing state and observability are separate; if `history` is in routing state but no stage routes on it, it is miscategorized. Two clean resolutions:

- **Move it out.** Append events to `output/history.jsonl` (the example does this). Routing state stays compact.
- **Earn its place.** Keep `history` in state only if a stage actually routes on it (e.g., the resume logic reads the most recent entry to find where it crashed, or a termination predicate reads the last N entries to detect a stalled loop). Otherwise it's observability dressed as state.

Real pipelines often blur this because the convenience of one file is real and the cost of two files is small. Be deliberate: if `history` is in state, name which stage routes on it.

## What never goes in state

- Transcripts of agent conversations.
- Full artifact contents (paths only).
- Free-form prose longer than a one-line summary.
- Anything that could grow unboundedly with run length.
- Anything only observability reads (see the history tension above).

If a field would benefit from being grep-able or human-readable in a dashboard but no stage routes on it, that field belongs in an observability log, not state.

## Anti-patterns

**Pre-declared keys for sparse data.** Forces every stage to write placeholders, drifts under premise 3.

**Schema changes as side effects.** Per §1 corollary (i), a stage that adds a new field is making a schema change. Declare schema changes as their own transition; do not let stages mutate the shape silently.

**Routing state as audit log.** If you find yourself appending entries to state for "completeness," the entries belong in observability.

**Bare values without provenance for external inputs.** A `drifted_weights` field with no source attribution looks identical whether it's fresh or three days stale. Provenance is what lets a stage reject corruption.

## Schema as a transition

State schema lives next to the pipeline graph in CLAUDE.md (or in a referenced schema file). Schema changes are themselves a pipeline transition: write a migration stage that reads old state, writes new state, and commits. Never let a working stage silently produce a different shape than it consumed.
