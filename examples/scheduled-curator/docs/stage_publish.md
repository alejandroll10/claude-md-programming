# Stage: publish (full mode)

Consults the release ledger for the rolling-window rate constraint, decides publish / rate-limit / drop, runs the deterministic formatter script, and appends the decision to the ledger.

Full-mode only.

## Inputs

- `state/pipeline_state.json` (reads `current_item_id`, `hard_fail_count`, `soft_fail_streak`, `queue.path`).
- `output/<date>/drafts/<current_item_id>.md` (the accepted draft).
- `output/<date>/verify/<current_item_id>_*.json` (the verifier outputs; used for correction lists when stage verdict was SOFT-FAIL).
- `state/release_ledger.jsonl` (append-only; read for the rolling-window query).
- Queue item's `category` from `state.queue.path`.

## Preflight

- Draft exists and `mtime > dispatch_start_time_of_draft_stage` (same as verify preflight).
- Verifier outputs exist (both structured and skeptic) if the inbound verdict is `SOFT-FAIL`; their `corrections` lists are consumed.
- Ledger file exists (may be empty).

If any fail: emit `ERROR`.

## Procedure

1. **Rate check.** Read `state/release_ledger.jsonl` and count entries matching:
   - `category == item.category`.
   - `timestamp >= now() - 24h`.
   - `decision == "published"` (rate-limit excludes dropped entries).

   Compare to the category rate limit (default: 3 per 24h per category; adjust in practice).

2. **Decision branch.**
   - **Rate exceeded:** emit `RATE_LIMITED`. Write a ledger entry with `decision: "rate_limited"` so the constraint remains auditable; the orchestrator advances `items_completed` and moves to the next item (the item is not republished this run).
   - **HARD-FAIL budget exhausted upstream** (`hard_fail_count[id] >= 2`): emit `DROPPED`. Write a ledger entry with `decision: "dropped_hard_fail"`.
   - **Delta trigger** (`soft_fail_streak[id] >= 2`): emit `DROPPED`. Write a ledger entry with `decision: "dropped_delta"`.
   - **Otherwise:** proceed to format + publish.

3. **Apply corrections if SOFT-FAIL.** Read each verifier's `corrections` list; apply each as a textual substitution to the draft, producing `output/<date>/published/<item_id>.md`. Record the applied corrections in the ledger entry's `corrections_applied` field for provenance (see `../../subagents-best-practices.md`, "Verifier verdict spaces").

4. **Run formatter (script vehicle).** Dispatch `scripts/format_validator.py`:

   ```
   python3 scripts/format_validator.py \
       --in output/<date>/published/<item_id>.md \
       --out output/<date>/published/<item_id>.formatted.md
   ```

   The script is deterministic (§3, "Scripts"): no model judgment during execution. Exit code 0 means the file is well-formed; non-zero means the draft violates a format rule and the stage signals failure (§5 corollary (c)).

5. **Append to ledger.** One JSONL line:

   ```json
   {
     "ts": "<ISO 8601 UTC>",
     "item_id": "<id>",
     "category": "<category>",
     "decision": "published" | "rate_limited" | "dropped_hard_fail" | "dropped_delta",
     "draft_path": "output/<date>/drafts/<id>.md",
     "published_path": "output/<date>/published/<id>.formatted.md" | null,
     "corrections_applied": [<list of correction records>] | [],
     "verifier_classes": [<class tags if SOFT-FAIL or HARD-FAIL>]
   }
   ```

6. **Emit verdict.** `PUBLISHED` / `RATE_LIMITED` / `DROPPED` per step 2 / 5.

## Post-check

- One new line appended to `state/release_ledger.jsonl`, `mtime > dispatch_start_time`.
- If verdict is `PUBLISHED`: `output/<date>/published/<item_id>.formatted.md` exists, non-empty, formatter exit code was 0.
- Ledger entry's `item_id` equals `state.current_item_id`.

If any fail: signal failure, do not transition.

## Verdict space

- `PUBLISHED`: draft passed rate, formatted, appended to ledger.
- `RATE_LIMITED`: category rate exceeded; ledger entry written (`decision: "rate_limited"`); `items_completed` advances; item is not republished this run.
- `DROPPED`: HARD-FAIL budget or delta trigger fired; ledger entry with drop reason; advance.
- `ERROR`: draft missing, formatter failed unrecoverably, or ledger write failed.

## Restated invariants

1. **Rate check precedes publish.** The ledger consult is not optional; publishing past the rate limit corrupts the constraint the ledger exists to enforce (CLAUDE.md invariant 3).
2. **Every publish decision writes exactly one ledger entry**, including rate-limited and dropped. Silent absence corrupts future rate queries.
3. **Corrections are recorded in the ledger with provenance.** Per `../../subagents-best-practices.md`, "Verifier verdict spaces": when a downstream consumer applies corrections without recording them, provenance is lost.
4. **Verify input freshness against `pipeline_started_at`** (CLAUDE.md invariant 4). The preflight block enforces this for draft and verifier outputs.
5. **One commit per stage transition, atomic and durable** (CLAUDE.md invariant 5). The ledger append and the state write commit together; a ledger entry without the corresponding state transition (or vice versa) corrupts resume.
