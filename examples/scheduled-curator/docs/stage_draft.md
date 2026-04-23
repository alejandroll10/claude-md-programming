# Stage: draft (full mode)

Produces a drafted artifact for the current queue item, suitable for verification and publication.

Full-mode only.

## Inputs

- `state/pipeline_state.json` (has `current_item_id` set).
- The queue file at `state.queue.path`.
- Prior draft at `output/<date>/drafts/<id>.md` if `hard_fail_count[id] > 0` (this is a HARD-FAIL redraft).

## Preflight

- `state.queue.checksum` matches the current SHA-256 of the queue file. If diverged, the queue file has been edited mid-run; emit `ERROR`.
- Queue file `mtime > state.pipeline_started_at`. (The intake check is not sufficient on resume: a mid-run external edit would pass intake and fail here.)
- `state.current_item_id in state.queue.item_ids`.

If any fail: emit `ERROR`.

## Dispatch

Agent: `.claude/agents/drafter.md`. Dispatch prompt passes:

- `queue_path`: path to queue file.
- `item_id`: `state.current_item_id`.
- `output_path`: `output/<date>/drafts/<item_id>.md`.

**Not passed:** prior-round verifier verdicts, critiques, or counters. A visible target invites gaming (§4 corollary (d)); the drafter produces a draft from the queue item alone (invariant 1 in CLAUDE.md).

## Post-check

- `output/<date>/drafts/<item_id>.md` exists and `mtime > dispatch_start_time`.
- File size > 50 bytes (a common empty-draft failure mode).
- Contains at least one non-blank line of actual content (not just headers).

If any fail: signal failure, do not transition.

## Verdict space

- `DRAFTED`: draft file written and passes post-check.
- `ERROR`: queue corruption (mtime / checksum) or dispatch-layer retries exhausted.

## Outgoing edges

Per `docs/mode_full.md`.

## Restated invariants

1. **The drafter never sees verifier verdicts or critiques from prior rounds** (CLAUDE.md invariant 1). The dispatch prompt carries only the original queue item, even on a HARD-FAIL redraft.
2. **Verify input freshness against `pipeline_started_at`** (CLAUDE.md invariant 4). The preflight block above enforces this; a stale queue file would silently taint every item.
3. **One commit per stage transition, atomic and durable** (CLAUDE.md invariant 5). The orchestrator commits after this stage returns; do not batch across items.
