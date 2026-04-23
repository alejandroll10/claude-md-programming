# Stage: verify (full mode)

Two verifiers in parallel (§6) evaluate the draft. Their verdicts combine into one stage verdict using the correction-aware scheme from `../../subagents-best-practices.md`, "Verifier verdict spaces".

Full-mode only.

## Inputs

- `output/<date>/drafts/<current_item_id>.md`.
- Queue item (the original, from `state.queue.path`, to give verifiers the original intent).

## Preflight

- Draft file `mtime > dispatch_start_time_of_draft_stage`. Not just `> pipeline_started_at`: verify must see *this round's* draft, not an earlier draft left over from a prior HARD-FAIL round.
- Queue checksum unchanged (same check as draft stage).

If any fail: emit `ERROR`.

## Dispatch (parallel)

Two Agent calls in one message (§6):

- `.claude/agents/verifier-structured.md` with inputs draft path + queue item path + output path `output/<date>/verify/<item_id>_structured.json`.
- `.claude/agents/verifier-skeptic.md` with the same two inputs and output `output/<date>/verify/<item_id>_skeptic.json`.

Neither verifier sees the other's framing, verdict, or critique (invariant 2). Each returns a JSON with `{verdict, class, corrections, critique}` per the agent definitions.

## Post-check

- Both output JSON files exist and `mtime > dispatch_start_time`.
- Each parses to the expected shape (`verdict` in closed set; `class` present on non-PASS; `corrections` is a list).

If any fail: signal failure.

## Combining the two verdicts

Closed set of per-verifier verdicts: `PASS`, `SOFT-FAIL`, `HARD-FAIL`. The stage verdict is the *max* of the two (with order PASS < SOFT-FAIL < HARD-FAIL): either verifier can veto, and the more severe verdict wins.

- Both PASS → stage verdict `PASS`.
- At least one SOFT-FAIL, none HARD-FAIL → stage verdict `SOFT-FAIL`; corrections = union of both verifiers' `corrections` lists, de-duplicated by class.
- At least one HARD-FAIL → stage verdict `HARD-FAIL`; classes = set of classes across both verifiers.

## Delta trigger bookkeeping

On `SOFT-FAIL`: compare the class set with the prior round's class set for this item (stored implicitly in `state.soft_fail_streak[id]` as a count of consecutive same-class rounds). If the current class set equals the prior round's class set, the streak holds; otherwise reset the streak to 1. When `soft_fail_streak[id] >= 2`, the orchestrator drops the item per `docs/mode_full.md` (delta trigger, §5 corollary (b)).

The orchestrator, not the verifier stage, computes the streak. The verify stage only reports the current round's class set.

## Verdict space

- `PASS`: both verifiers passed; publish without corrections.
- `SOFT-FAIL`: at least one verifier enumerated corrections; publish with corrections applied.
- `HARD-FAIL`: at least one verifier judged the draft unsalvageable; re-draft.
- `ERROR`: dispatch-layer retries exhausted or post-check failed.

## Outgoing edges

Per `docs/mode_full.md`. The orchestrator computes the stage verdict by combining per `above` and routes.

## Restated invariants

1. **Verifiers do not see each other's framings, verdicts, or critiques** (CLAUDE.md invariant 2). The dispatch prompt to each is independent; neither can reference the other.
2. **Find errors, do not confirm correctness.** Each verifier agent's system prompt declares this (§4 corollary (e)); the stage doc re-states it here because the dispatch prompt is a second surface the rule can be breached from.
