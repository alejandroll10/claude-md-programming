# Example: Scheduled curator

Second worked example. Complements `../benchmark-generator/` by exercising patterns that example deliberately skips.

**Task.** Consume a user-supplied queue of draft items and publish accepted ones to a release ledger, subject to a rolling-window rate constraint per category. Two run modes: a short-form `scan` that only triages the queue, and a `full` cycle that drafts, verifies, and publishes.

## What this example exercises that `benchmark-generator` does not

- **Multi-mode orchestrator.** Trigger phrase selects `scan` vs `full`; each mode has its own transition table (`../../state-schema-patterns.md`, "Mode or variant flag").
- **User-input stage (`intake`, full mode).** Blocks for a human-supplied queue file path, records value + provenance in routing state (`../../stages-best-practices.md`, "User-input stages").
- **Domain ledger.** `state/release_ledger.jsonl` is append-only, read by the `publish` stage for rolling-window rate constraints (`../../state-schema-patterns.md`, "Domain ledgers").
- **Preflight / post-check bookends.** Every stage doc shows explicit input freshness checks and output validation (`../../stages-best-practices.md`, "Preflight / post-check bookends").
- **Script vehicle.** `publish` stage dispatches `scripts/format_validator.py` directly (`../../principles.md` §3, "Scripts").
- **Correction-aware verifier verdict space.** `verify` emits `PASS` / `SOFT-FAIL` / `HARD-FAIL`; the `publish` stage consumes SOFT-FAIL corrections without re-dispatching the drafter (`../../subagents-best-practices.md`, "Verifier verdict spaces").
- **Graceful degradation recorded as signal (§5(f)).** When the queue input is missing, the `intake` stage records a `fallback_used` marker and emits `ERROR` rather than silently completing an empty run.

## What `benchmark-generator` already covers (and this example does not re-demonstrate)

- Single-mode pipeline shape.
- Binary `ACCEPT` / `REJECT` verifier verdict space.
- Two verifiers with distinct framings (this example reuses the pattern but does not re-argue it).
- `stuck_count` + equal-last-two delta trigger termination.
- Three-stage proposer/solver/verifier loop.

## Files

```
scheduled-curator/
├── CLAUDE.md                               # two-mode orchestrator
├── state/
│   ├── pipeline_state.json                 # routing state (mode, current_stage, counters, provenance)
│   └── release_ledger.jsonl                # append-only domain ledger (empty initial)
├── docs/
│   ├── mode_scan.md                        # scan-mode flow
│   ├── mode_full.md                        # full-mode flow
│   ├── stage_intake.md                     # user-input stage
│   ├── stage_triage.md                     # scan-mode worker stage
│   ├── stage_draft.md
│   ├── stage_verify.md                     # correction-aware verdict space
│   └── stage_publish.md                    # ledger consult + script dispatch
├── .claude/agents/
│   ├── triager.md
│   ├── drafter.md
│   ├── verifier-structured.md
│   └── verifier-skeptic.md
├── scripts/
│   └── format_validator.py                 # deterministic post-draft formatter (script vehicle)
└── input/
    └── queue.example.json                  # example of the user-supplied queue shape
```

## What this example does not exercise

- Parallel dispatch at the stage level (stages are sequential per item). The two verifiers inside `verify` run in parallel.
- Schema migration as a transition (§1(i)).
- Explicit rollback of a committed stage (§1(j)).

The domain is synthetic. Items are short textual announcements with categories; the constraint is a rolling-window rate per category. Swap for any queue-with-rate-constraint domain (release notes, moderation decisions, scheduled posts) and the scaffolding carries over.
