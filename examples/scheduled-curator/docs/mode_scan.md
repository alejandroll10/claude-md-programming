# Mode: scan

Short-form triage pass over the queue. One stage, then complete.

## Flow

`triage` → `complete`

## Stages

- `triage` → `docs/stage_triage.md`

## Transition table

| From     | Verdict   | Next       | State update                                 |
|----------|-----------|------------|----------------------------------------------|
| triage   | TRIAGED   | terminate  | `status = complete`                          |
| triage   | ERROR     | terminate  | `status = stuck`, write `output/error_report.md` |

## Mode-specific preconditions

The `triage` stage does not require `queue` to be populated in state (the scan mode reads the queue file path from the user's trigger message or a default path `input/queue.json`). If full-mode intake has already populated `state.queue.path` on a prior run, scan mode is free to reuse it; the stage's preflight verifies freshness against `pipeline_started_at`.
