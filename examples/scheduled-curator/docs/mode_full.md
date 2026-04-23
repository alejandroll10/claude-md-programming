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
| publish | RATE_LIMITED | next      | ledger entry `decision: "rate_limited"` recorded; `++items_completed`; advance `current_item_id`. The item is not republished this run; future runs pick it up from source if the caller requeues it. |
| publish | DROPPED      | next      | ledger append with drop reason; `++items_completed`; advance `current_item_id` |
| (loop)  | (last item done) | terminate | `status = complete`                                                     |

### Streak accounting (authoritative)

The orchestrator computes `soft_fail_streak[id]` on each verify transition, not the verify stage. The rule:

- `SOFT-FAIL` and current class set equals `soft_fail_prior_class_set[id]`: `soft_fail_streak[id] += 1`; `soft_fail_prior_class_set[id]` is unchanged.
- `SOFT-FAIL` and current class set differs: `soft_fail_streak[id] = 1`; `soft_fail_prior_class_set[id] = <current class set>`.
- `PASS`, `HARD-FAIL`, `ERROR`: `soft_fail_streak[id] = 0`; `soft_fail_prior_class_set[id] = null`.

The verify stage reports the current round's class set. The prior round's class set is committed to routing state in `soft_fail_prior_class_set[id]` alongside the streak counter, so the comparison survives a mid-loop crash (§1 corollary (a), §1 corollary (g)).

When `soft_fail_streak[id] >= 2` after the update above, the delta trigger fires: the publish stage writes a `dropped_delta` ledger entry and the orchestrator advances to the next item. Same bookkeeping as `DROPPED`.

## Mode-specific preconditions

Full mode requires `state.queue.item_ids` non-empty after intake. Scan-mode state carried over from a prior run does not satisfy this; the `intake` stage's preflight re-verifies the user-supplied queue for this run.

## Parallelism (§6)

Inside `verify`, the two verifier dispatches run concurrently (§6); they write distinct keys in the verify stage's output and the orchestrator gathers both before classifying the verdict. All other stages are sequential: the per-item loop has a data dependency from one stage to the next on the same item.
