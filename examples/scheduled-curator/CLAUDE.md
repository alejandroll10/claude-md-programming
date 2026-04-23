# CLAUDE.md: Scheduled curator

Autonomously consume a user-supplied queue of draft items and publish accepted ones to a rate-limited release ledger. Two modes triggered by user phrase.

| Trigger phrase                         | Mode   | Doc                    |
|----------------------------------------|--------|------------------------|
| "scan the queue" / "triage"            | `scan` | `docs/mode_scan.md`    |
| "run the curator" / "full cycle"       | `full` | `docs/mode_full.md`    |

Mode is set once per run by the trigger phrase, never changed mid-run (§1 corollary (i) of `../../principles.md`).

## Pipeline state

Tracked in `state/pipeline_state.json`. Read at session start; update after every stage transition; commit every update atomically (§1 corollary (g)).

Shape:

```jsonc
{
  "mode": "scan" | "full",
  "current_stage": "intake" | "triage" | "draft" | "verify" | "publish",
  "status": "running" | "complete" | "stuck",
  "pipeline_started_at": null,          // ISO 8601 UTC, set at launch before the first stage; freshness anchor for §1(a)
  "queue": {                             // populated by the user-input intake stage (full mode only)
    "path": null,
    "source": null,                      // e.g., "user 2026-04-23T14:00Z"
    "checksum": null,                    // SHA-256 of the file at confirmation time
    "confirmed_at": null,
    "item_ids": []                       // ids in the order they will be processed
  },
  "current_item_id": null,               // the id being processed in the per-item loop (full mode)
  "items_completed": 0,
  "soft_fail_streak": {},                // per-item id: count of consecutive same-class SOFT-FAIL rounds, for delta trigger
  "soft_fail_prior_class_set": {},       // per-item id: the prior round's verifier class set; needed for the streak comparison to survive crashes
  "hard_fail_count": {},                 // per-item id: count of HARD-FAIL drafts, budget 2 per item
  "fallback_used": null                   // populated when intake downgrades (§5 corollary (f))
}
```

The release ledger is a separate append-only file `state/release_ledger.jsonl`, not routing state (`../../state-schema-patterns.md`, "Domain ledgers"). The `publish` stage reads it to compute the rolling-window rate; the orchestrator never reads it for routing.

Observability (one JSONL line per transition) is appended to `output/history.jsonl`, not stored in routing state (§1 corollary (e)).

## Pipeline graph

```
scan mode:
    triage  ──→  complete

full mode:
    intake ──→ (per-item loop over queue.item_ids):
                 ┌─────────────────────────────────────┐
                 │   draft ──→ verify                  │
                 │              │                       │
                 │              ├── PASS      ─────────┤──→ publish ──→ next item
                 │              ├── SOFT-FAIL ─────────┤──→ publish  (consume corrections)
                 │              └── HARD-FAIL ─────────┘──→ draft (++hard_fail_count[id])
                 └─────────────────────────────────────┘
              after last item: status = complete

    mechanical exits:
      hard_fail_count[id] >= 2           (drop item, record in ledger as "dropped", continue to next)
      soft_fail_streak[id] >= 2          (delta trigger: same-class SOFT-FAIL twice; drop + ledger)
      items_completed >= len(item_ids)   (complete)
```

Orchestrator loop (§1):

```
state = read("state/pipeline_state.json")

if state.status == "not_started":
    phrase = await_user_trigger()                # "scan the queue" | "run the curator" | ...
    state.mode = phrase_to_mode(phrase)
    state.current_stage = first_stage_of(state.mode)   # triage for scan; intake for full
    state.pipeline_started_at = utc_now()
    state.status = "running"
    commit_and_push("curator: launch → " + state.mode)

while state.status == "running":
    state   = read("state/pipeline_state.json")
    mode    = state.mode
    stage   = state.current_stage
    doc     = read(f"docs/stage_{stage}.md")
    verdict = dispatch(stage, doc, state)        # agent, script, or user-input prompt
    state   = transition(state, mode, verdict)   # per each mode doc's transition table
    write_atomic("state/pipeline_state.json", state)
    append("output/history.jsonl", event)
    commit_and_push(f"curator: {mode}/{stage} → {verdict}")
```

The initial committed state has `status: "not_started"`. First run enters the launch block above; resume enters the loop directly because a resumed run has `status: "running"` (§1 corollary (h)).

Local transitions live in the mode docs; each mode's table is the authoritative routing for that mode.

Top-level ERROR routing (applies in both modes):

| From   | Verdict | Next      | Notes                                  |
|--------|---------|-----------|----------------------------------------|
| any    | ERROR   | terminate | write `output/error_report.md`, status=stuck |

## Load-bearing invariants

1. **The drafter never sees verifier verdicts or critiques from prior rounds on the same item.** A visible target invites gaming (§4 corollary (d)); self-bias (premise 1) defends prior output. The orchestrator's retry prompt to `drafter` passes only the original queue item, not prior drafts or feedback. Restated in `docs/stage_draft.md`, `docs/stage_verify.md`, and `.claude/agents/drafter.md`.
2. **Verifiers do not see each other's framings, verdicts, or critiques.** Identical instructions collapse the §4(b) independence to one sample (§4 corollary (c)). Each verifier is dispatched independently in parallel with only the drafted artifact as input. Restated in `docs/stage_verify.md`, `.claude/agents/verifier-structured.md`, `.claude/agents/verifier-skeptic.md`.
3. **Publish consults the ledger for the rolling-window rate before appending.** Category rate > limit means the item is not published this run: the publish stage writes a `decision: "rate_limited"` ledger entry, `items_completed` advances, and the run moves on. Silent publish past the limit corrupts the constraint the ledger exists to enforce. Restated in `docs/stage_publish.md`.
4. **Every stage verifies input freshness against `pipeline_started_at` before consuming.** Silent consumption of stale files from a prior run is the most likely cross-stage corruption (§1 corollary (a)). Restated as a per-stage preflight in every stage doc.
5. **One commit per stage transition, atomic and durable.** On multi-host runs, push after each commit so a peer host resumes from the committed state, not the local state (§1 corollary (g)).

## Termination

Mechanical (§5). No termination path depends only on LLM judgment.

- `status = complete` when:
  - `scan` mode: `triage` returns.
  - `full` mode: `items_completed >= len(queue.item_ids)`.
- Per-item drops (loop continues after each; not termination on their own):
  - `hard_fail_count[id] >= 2` for an item: drop the item, append `decision: "dropped_hard_fail"` to ledger, advance `current_item_id`.
  - `soft_fail_streak[id] >= 2`: delta trigger (same-class SOFT-FAIL twice); drop the item, append `decision: "dropped_delta"` to ledger, advance.
- `status = stuck` when any stage returns `ERROR` after its dispatch-layer retries exhaust. A run in which every item is dropped still completes normally (`status = complete`) once `items_completed >= len(item_ids)`; drops count as processed.

Self-recovery (§5 corollary (e)): in-pipeline recovery paths (HARD-FAIL → re-draft, SOFT-FAIL → publish-with-corrections) run out before termination fires. Fresh-instance retries on parse failure (noise) happen at the dispatch layer and do not count toward `hard_fail_count` or `soft_fail_streak` (§5 corollary (c)).

**Graceful degradation (§5 corollary (f)).** If the `intake` stage finds no queue file when the user expected one, it records `fallback_used = "empty_queue"` in state and emits `ERROR` rather than silently completing. A silent empty run is a broken stage.

## Resume and self-recovery

State and the release ledger are committed together at the end of each loop iteration. On startup, read `pipeline_state.json`; if `status == "running"`, re-enter the loop at `current_stage`. On uncommitted working-tree changes from a crashed stage, discard (`git reset --hard HEAD`) before continuing. First run starts from the committed initial state (§1 corollary (h)).

## Commit protocol

One commit per stage transition, prefixed with `curator: {mode}/{stage} → {verdict}`. Push after every commit (§1 corollary (g)) so multi-host resumes see the current state.
