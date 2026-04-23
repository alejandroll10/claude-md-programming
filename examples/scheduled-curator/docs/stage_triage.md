# Stage: triage (scan mode)

Short-form triage of the queue. Tags each item as `ready` / `needs_revision` / `drop` and writes a report. Does not publish.

Scan-mode only.

## Inputs

- `state/pipeline_state.json` (has `mode = "scan"`).
- Queue file at `state.queue.path` if set; otherwise default `input/queue.json`.

## Preflight

- Queue file exists. `mtime > state.pipeline_started_at` OR the file was explicitly named in the trigger phrase (the trigger is a fresher source than mtime for scan mode).
- JSON parses; schema matches the shape declared in `docs/stage_intake.md` (list of items with `id`, `category`, `text`, optional `sources`).

If any fail: emit `ERROR`. No silent fallback.

## Dispatch

Agent: `.claude/agents/triager.md`. Dispatch prompt passes the queue path and the output path `output/<date>/triage.md`, not the queue contents (§2, paths not bodies).

## Post-check

- `output/<date>/triage.md` exists, `mtime > dispatch_start_time`.
- Every item id from the queue appears in the report with a tag from the closed set.

If any fail: signal failure, do not transition.

## Verdict space

- `TRIAGED`: report written, all items tagged.
- `ERROR`: unrecoverable after 3 dispatch-layer retries.

## Outgoing edges

Per `docs/mode_scan.md`. Either verdict terminates the run.

## Restated invariants

1. **Freshness anchor is `pipeline_started_at`** (CLAUDE.md invariant 4). Scan mode does not re-confirm the queue file; the preflight freshness check is the only defense against consuming a stale file (§1 corollary (a)).
2. **One commit per stage transition, atomic and durable** (CLAUDE.md invariant 5). Scan mode is short, but the commit discipline is identical.
