# Mode: full

Full curator cycle. Intake the queue once (user-input), then loop per item through draft, verify, publish.

## Flow

```
intake ──→ (per item in queue.item_ids):
            draft ──→ verify ──→ publish ──→ next item
                                   │
                                   └── HARD-FAIL → draft (++hard_fail_count[id])
```

## Stages

- `intake` → `docs/stage_intake.md`
- `draft` → `docs/stage_draft.md`
- `verify` → `docs/stage_verify.md`
- `publish` → `docs/stage_publish.md`

## Transition table

| From    | Verdict      | Next      | State update                                                                 |
|---------|--------------|-----------|------------------------------------------------------------------------------|
| intake  | QUEUE_READY  | draft     | `queue.*` populated; `current_item_id = item_ids[0]`; `hard_fail_count[id]=0`; `soft_fail_streak[id]=0` |
| intake  | EMPTY_QUEUE  | terminate | `status = stuck`, `fallback_used = "empty_queue"`                            |
| draft   | DRAFTED      | verify    |                                                                              |
| verify  | PASS         | publish   |                                                                              |
| verify  | SOFT-FAIL    | publish   | `soft_fail_streak[id]` updated per the rule below; corrections list passed to publish |
| verify  | HARD-FAIL    | draft     | `++hard_fail_count[id]`; if `>=2`, route to publish with `decision: dropped_hard_fail` |
| publish | PUBLISHED    | next      | `++items_completed`; advance `current_item_id`; `soft_fail_streak[id]=0`     |
| publish | RATE_LIMITED | next      | item returned to queue tail with marker; `++items_completed` skipped; advance `current_item_id` |
| publish | DROPPED      | next      | ledger append with drop reason; `++items_completed`; advance `current_item_id` |
| (loop)  | (last item done) | terminate | `status = complete`                                                     |

### Streak accounting (authoritative)

The orchestrator computes `soft_fail_streak[id]` on each verify transition, not the verify stage. The rule:

- `SOFT-FAIL` and class set equals the prior round's class set for this item: `soft_fail_streak[id] += 1`.
- `SOFT-FAIL` and class set differs: `soft_fail_streak[id] = 1`.
- `PASS`, `HARD-FAIL`, `ERROR`: `soft_fail_streak[id] = 0`.

The verify stage reports the current round's class set; storage of the prior round's class set for comparison lives in the orchestrator's local variable across iterations (not in routing state, since it only matters for the immediately next decision).

When `soft_fail_streak[id] >= 2` after the update above, the delta trigger fires: the publish stage writes a `dropped_delta` ledger entry and the orchestrator advances to the next item. Same bookkeeping as `DROPPED`.

## Mode-specific preconditions

Full mode requires `state.queue.item_ids` non-empty after intake. Scan-mode state carried over from a prior run does not satisfy this; the `intake` stage's preflight re-verifies the user-supplied queue for this run.

## Parallelism (§6)

Inside `verify`, the two verifier dispatches run concurrently (§6); they write distinct keys in the verify stage's output and the orchestrator gathers both before classifying the verdict. All other stages are sequential: the per-item loop has a data dependency from one stage to the next on the same item.
