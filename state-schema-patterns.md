# State schema: patterns

How to shape the routing-state JSON for a pipeline. Read `principles.md` first; this doc is a pattern catalog, not foundations. The principles call routing state "compact, no transcripts, schema declared, not emergent" (§1, §1 corollary (i), §2). That is necessary but not sufficient for designing the fields. This doc fills the gap with patterns from production pipelines.

## Required fields (every pipeline has these)

**`current_stage` (or `current_step`).** The pointer into the pipeline graph. The orchestrator's first read every turn. Always a string from a closed enum that matches the stage list in CLAUDE.md.

**`status`.** The orchestrator's loop condition. Closed enum, typically `not_started` / `running` / `complete` / `stuck`. The `while state.status == "running"` in §1's pseudocode reads this field.

These two fields together define resumability. A new run reads them and either starts (`not_started`) or re-enters at `current_stage` (`running`). The `complete` and `stuck` terminal states stop the loop and let observability take over.

## Common patterns (most pipelines)

**Counter family.** Per-loop counters that feed termination predicates (§5). One counter per loop body, one per escalation stage. Pipelines accumulate many: `attempt`, `round`, `version`, `revision`, `pivot`, `stuck_count`, `retry_count`. Each has a budget cap somewhere in CLAUDE.md or a stage doc. Counters reset only on the transition that ends their loop (`stuck_count` resets on ACCEPT, not on any other event). The reset rules belong with the counter declaration so the orchestrator does not invent them per run.

**Mode or variant flag.** When one CLAUDE.md serves multiple flows (a pipeline with both a "quick scan" mode and a "full rebuild" mode), the active flow is a state field. The orchestrator routes on it before consulting `current_stage`.

**Input snapshot with provenance.** Inputs the pipeline captures from outside (a manual seed, a user-supplied target, a configuration vector pulled from an external system) live in state with three things: the value, the source (where and when it came from), and a consistency check. A `config` field shipped with `config_source` (prose attribution) and `config_checksum` (or another invariant the stage can validate) lets downstream stages fail loudly on a stale or corrupted snapshot. Without provenance, the snapshot is invisible.

**Sparse fill-as-you-go dicts.** When stages contribute scores, verdicts, or partial results that accumulate across iterations, declare the dict but do not pre-populate keys. Each stage writes its own key. Premise 3 (coherence drift) bites if every stage is asked to "make sure all the keys are there."

**Nullable transitions.** Some fields are meaningfully absent until a stage produces them. A `triage_verdict: null` field stays null until the triage stage emits one. Null is the schema-declared "not yet observed" value; do not conflate with missing keys.

**Cross-cycle context.** Pipelines that run repeatedly carry narrative state from one cycle to the next, distinct from append-only history. A `prior_cycle_context` slot, overwritten each cycle with a short prose summary the next cycle's stages can read, is one shape. Different from the history array: history is append-only and grows; cross-cycle context is a slot that gets replaced.

## Pointers, not bodies

State holds *paths and identifiers*, not the artifacts they point to. `current_problem_id: 42` not the problem statement; `verdict_path: "output/verify_42.json"` not the verdict. §2 (context costly) applies to state because state is read at every transition. A 2KB state file read 1000 times is 2MB; a 200KB state file is 200MB.

## The history-array tension

A common shape is a `history` array of `{timestamp, event/step, summary}` carried inside the state file. This is borderline observability vs. routing. The principle (§1 corollary (e)) says routing state and observability are separate; if `history` is in routing state but no stage routes on it, it is miscategorized. Two clean resolutions:

- **Move it out.** Append events to `output/history.jsonl` (the example does this). Routing state stays compact.
- **Earn its place.** Keep `history` in state only if a stage actually routes on it. Common reasons it earns the slot: resume logic reads the most recent entry to find where it crashed; a termination predicate reads the last N entries to detect a stalled loop; the first entry's timestamp is the freshness-check anchor (§1(a)) every downstream stage compares input mtimes against, so deleting it breaks the freshness protocol. Any of those makes `history` a routing-state field with an observability side-benefit, not observability misfiled. If none apply, it is observability dressed as state.

Pipelines often blur this because the convenience of one file is genuine and the cost of two files is small. Be deliberate: if `history` is in state, name which stage routes on it.

## Domain ledgers

Some pipelines carry an append-only ledger of domain facts, distinct from routing state and from observability. A trade-history ledger, a dispatch log consulted for rate limiting, a decision journal read to enforce "no two consecutive X without a new Y". Stages both append entries and read past entries to compute constraints; the orchestrator routes on derived quantities (a rolling-window sum, a "most-recent-N" scan, a presence check for a catalyst tag).

This is a fourth artifact class alongside routing state (§1(e)), observability (§1(e)), and reference artifacts (§1(f)). It differs from each:

- **Not routing state.** It grows unboundedly with run length, which violates §2's compactness bar for the file read every transition. Routing state consults it through a derived query, not by loading the whole file.
- **Not observability.** Stages do route on it. §1(e)'s "never read to route" rule does not apply.
- **Not a reference artifact.** It is written *by* the pipeline over time, not captured once at entry.

Patterns:

- **Append-only, never rewritten.** A stage appends one entry per transition of interest; prior entries are immutable. Premise 3 (coherence drift) bites if the ledger is mutable: a retroactive rewrite makes last run's story look better, and downstream constraints compute on fiction.
- **Schema per entry is closed.** Every entry conforms to a declared per-entry shape, the same way routing state has a schema (§1 corollary (i)). A stage that needs a new field declares a schema change, not a one-off entry.
- **Derived queries live in the stage that needs them.** The rolling-window sum, the "last two entries equal" test, the "most-recent catalyst" lookup belong in the stage doc that routes on them. Compute over the ledger and route on the scalar; copying the ledger into routing state violates §2.
- **Provenance per entry.** Who wrote it, when, what decision, what verdict. Without provenance a ledger is rows later stages cannot reason about.

**When a ledger is the right shape.** Constraints of the form "this kind of event can happen at most N times per window" or "this kind of event requires that other event to precede it". A counter in routing state loses the per-event detail those constraints need.

**When it is not.** A pure counter with no per-event metadata belongs in routing state. Ledgers earn their cost only when queries on individual entries matter.

## What never goes in state

- Transcripts of agent conversations.
- Full artifact contents (paths only).
- Free-form prose longer than a one-line summary.
- Anything that could grow unboundedly with run length. If you need an append-only domain history to route on, split it into a separate ledger file (see "Domain ledgers" above).
- Anything only observability reads (see the history tension above).

If a field would benefit from being grep-able or human-readable in a dashboard but no stage routes on it, that field belongs in an observability log, not state.

## Anti-patterns

**Pre-declared keys for sparse data.** Forces every stage to write placeholders, drifts under premise 3.

**Schema changes as side effects.** Per §1 corollary (i), a stage that adds a new field is making a schema change. Declare schema changes as their own transition; do not let stages mutate the shape silently.

**Routing state as audit log.** If you find yourself appending entries to state for "completeness," the entries belong in observability.

**Bare values without provenance for external inputs.** An external-input field with no source attribution looks identical whether it is fresh or three days stale. Provenance is what lets a stage reject corruption.

## Schema as a transition

State schema lives next to the pipeline graph in CLAUDE.md (or in a referenced schema file). Schema changes are themselves a pipeline transition: write a migration stage that reads old state, writes new state, and commits. Never let a working stage silently produce a different shape than it consumed.
