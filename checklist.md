# Setup checklist

A sequence of decisions for starting a new pipeline, each mapped to the principle it implements. Read `principles.md` first; this page is the short form.

## 1. Pipeline graph (§1)

- [ ] List the stages, in order. Each stage is a single subagent dispatch with a clear verdict space.
- [ ] Write the transition table: `(from_stage, verdict) → next_stage`. Include an `ERROR` row.
- [ ] Draw the graph in CLAUDE.md. The orchestrator needs the whole shape at a glance (§1 corollary (b)).
- [ ] If the pipeline has multiple flows selected by trigger phrase, declare the `mode` enum and the trigger-to-mode table in CLAUDE.md, each mode with its own transition table (`state-schema-patterns.md`, "Mode or variant flag").
- [ ] List any stages that block on human-supplied input. They are declared stages with their own transition-table entries, not side-effects of other stages (`stages-best-practices.md`, "User-input stages").

## 2. State shape (§1 corollary (i), §2)

- [ ] Declare the JSON schema alongside the graph. Routing fields only. No transcripts, no accumulated logs.
- [ ] Commit a valid initial state at setup so the first run and a resume take the same code path (§1 corollary (h)).
- [ ] Decide where observability goes (JSONL log, dashboard, commit messages). Never in routing state (§1 corollary (e)).
- [ ] Specify the freshness check each stage runs before consuming intermediate inputs: mtime against pipeline-start, or an explicit freshness marker. Without this, a resumed run silently consumes prior-run outputs (§1 corollary (a)). Pair with a per-stage output post-check; see `stages-best-practices.md`, "Preflight / post-check bookends" for the dual pattern.

## 3. Environmental ground truth (§1 corollary (f))

- [ ] If the pipeline reads external data or services, write a reference artifact at pipeline entry. Every stage reads it; nothing routes on it.
- [ ] Skip if the pipeline is closed-world.

## 4. Invariants to restate (§3 delegation corollary)

- [ ] List the rules whose breach would be silent, cascading, and reachable from more than one surface in this pipeline. A rule missing any of the three is not on this list (§3 delegation corollary).
- [ ] For each, identify the surfaces it can enter from in this pipeline, and restate at each. The surfaces are descriptive per pipeline, not a fixed list.

## 5. Per-stage delegation (§3)

For each stage:

- [ ] Pick the vehicle: **doc** (orchestrator acts on it), **script** (deterministic code, no model judgment at run time), **skill** (capability the worker loads), **agent** (fresh-context subagent). See §3's table.
- [ ] Default to agent for anything that produces the stage's artifact. Orchestrator routes, doesn't work (§1 corollary (d)).
- [ ] If a skill is used by this stage, confirm it loads inside the dispatched agent, not in the orchestrator (§3).
- [ ] Write the stage doc. It owns the local verdict space, the outgoing edges, and the per-stage preflight (upstream inputs) and post-check (this stage's outputs). See `stages-best-practices.md`, "Preflight / post-check bookends".

## 6. Verification gates (§4)

For each stage whose output the orchestrator routes on:

- [ ] Make verification its own stage, dispatched by the orchestrator, not by the worker (§4 corollary (a)).
- [ ] Two verifiers minimum. Distinct framings (§4 corollaries (b), (c)).
- [ ] Each verifier is adversarially posed: find errors, not confirm correctness (§4 corollary (e)).
- [ ] Ship a structured verdict for routing and a free-form critique for content (§4 corollary (d)).
- [ ] Confirm verifiers do not see each other's rubrics or verdicts (§4 corollary (c): identical instructions and shared signals correlate their samples).
- [ ] If a worker retries, confirm it does not see prior rounds' scores or verdicts. A visible target invites gaming (§4 corollary (d)).
- [ ] For each stage's verdict space, decide which branches the orchestrator routes on as enumerated verdicts (hot paths, default) and which it reads the full artifact on (rare branches). Verdicts buy efficiency, not correctness (§5 corollary (d)).
- [ ] If verifier errors can be consumed as corrections by a downstream stage without re-dispatching the producer, declare a correction-aware verdict space (`PASS` / `SOFT-FAIL` / `HARD-FAIL`); otherwise stick with binary. See `subagents-best-practices.md`, "Verifier verdict spaces".

## 7. Termination (§5)

- [ ] For each routing branch in the pipeline, classify the predicate as mechanical (numeric rules over state) or LLM-judged (orchestrator reads output and decides). Both are legitimate; termination is the exception (§5).
- [ ] Every unbounded loop has at least one mechanical exit on its termination path (§5 corollary (a)).
- [ ] For each such loop, pick the strongest termination strategy your data supports: absolute cap (new loop, no history), budget cap (history shows where marginal value saturates), or delta trigger (per-iteration signal is reliable enough to threshold). Early runs feed the next tier (§5 corollary (b)).
- [ ] Separate signal-failure and infrastructure-failure counters. Infra retries live at dispatch (§5 corollary (c)).
- [ ] Before termination fires, cheap self-recovery paths run out: fresh-instance retry, framing swap, coarser fallback (§5 corollary (e)).
- [ ] Any fallback that degrades input quality is recorded in state, not only in logs (§5 corollary (f)).

## 8. Atomicity and resume (§1 corollary (g), §1 corollary (j))

- [ ] One commit per stage transition. State, artifacts, and observability log commit together (§1 corollary (g)).
- [ ] On startup, discard any uncommitted working-tree changes from a crashed stage.
- [ ] If the pipeline supports manual rollback of a committed stage, define the teardown artifact: what was deleted, what was preserved (§1 corollary (j)).

## 9. Parallelism (§6)

- [ ] For each stage, confirm which subagent dispatches have no data dependency on each other, and run those concurrently. The test is data dependency, not dispatch structure.
- [ ] Parallel branches write distinct state keys, or the orchestrator gathers after all return. Concurrent writes to the same field race and corrupt state.

## 10. Budget audit (§2)

Before the first run:

- [ ] CLAUDE.md contains graph + state shape + invariants + stage pointers. Not procedures, examples, or edge-case notes.
- [ ] Each stage doc is the minimum the stage needs. No "just in case" content.
- [ ] Subagent dispatches pass paths, not file bodies, when the agent can fetch.
- [ ] Read CLAUDE.md line by line and confirm every line names the step it serves. Delete any that can't answer "load-bearing for which step?"
