# Stage: intake (full mode)

User-input stage. Blocks for a human-supplied queue file path, validates the file, records provenance into routing state, then hands off to `draft` on the first item.

Full-mode only. Scan mode skips intake.

## Inputs

- `state/pipeline_state.json` (has `mode = "full"`, `current_stage = "intake"`).
- `<queue file path>` (user-supplied; the path is the human input).

## Preflight

- `state.mode == "full"` and `state.current_stage == "intake"`. If either differs, dispatch is wrong; emit ERROR.
- `state.queue.path` is either null (fresh intake) or a prior-run leftover. If non-null and `state.queue.confirmed_at < state.pipeline_started_at`, treat as stale and re-prompt: the queue must be confirmed *this run* to prevent silent reuse of a prior run's batch (§1 corollary (a)).

## Procedure

1. Post observability entry: "`intake` blocked on user queue path."
2. Prompt the user: "Provide the queue file path for this run, or type `empty` if there is no queue."
3. If the response is `empty`:
   - Set `state.fallback_used = "empty_queue"` (§5 corollary (f)).
   - Emit `EMPTY_QUEUE` (routes to terminate per `docs/mode_full.md`).
4. Else, treat the response as a path. Read the file.
5. Validate: JSON parses; top-level is a list of objects each with `id` (string), `category` (string), `text` (string), optional `sources` (list of strings). No duplicate `id`s.
6. Compute SHA-256 of the file bytes; record as `checksum`.
7. Populate state:
   - `state.queue.path = <path>`.
   - `state.queue.source = f"user {utc_now_iso()}"`.
   - `state.queue.checksum = <sha256>`.
   - `state.queue.confirmed_at = utc_now_iso()`.
   - `state.queue.item_ids = [item.id for item in queue]`, preserving queue order.
   - `state.current_item_id = state.queue.item_ids[0]`.
   - `state.hard_fail_count[id] = 0` for each id; same for `soft_fail_streak`.
8. Post observability entry: "`intake` confirmed, N items queued, checksum <prefix>."
9. Emit `QUEUE_READY`.

## Post-check

- `state.queue.path`, `source`, `checksum`, `confirmed_at` all non-null.
- `state.queue.confirmed_at > state.pipeline_started_at`.
- `state.queue.item_ids` non-empty (empty is caught by the `empty` branch above).
- `state.current_item_id` is in `state.queue.item_ids`.

If any fail: signal failure, do not transition.

## Verdict space

- `QUEUE_READY`: queue validated and recorded; ready to draft first item.
- `EMPTY_QUEUE`: user confirmed no queue this run; terminate.
- `ERROR`: unrecoverable (e.g., malformed path input after 3 dispatch-layer retries); terminate.

## Restated invariants

1. **The queue's source, timestamp, and checksum must all be recorded** (§1 corollary (f), "provenance for snapshots"). An unprovenanced queue file cannot be distinguished from a prior-run leftover.
2. **A stale `queue.path` from a prior run is not consumed silently.** The `confirmed_at > pipeline_started_at` check enforces this at preflight. Without it, a resumed run would process yesterday's batch as today's.
