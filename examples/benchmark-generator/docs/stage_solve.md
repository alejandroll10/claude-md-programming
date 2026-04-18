# Stage: solve

**Agent:** `solver`, dispatched by this stage. Produces `(solution, tests)` for the current proposed problem.

## Procedure

1. Read `state/pipeline_state.json`. Let `id = current_problem_id`.
2. Launch `solver` with `output/proposed/<id>/problem.md`. It writes `output/solved/<id>/{problem.md, solution.*, tests.*}`, copying the problem file verbatim and adding its solution and tests.
3. Verify all three files exist and are non-empty. If not, verdict `ERROR`.
4. Update state: `current_stage = "verify"`. Append a line to `output/history.jsonl`. Commit: `pipeline: solve <id>`.

## Verdict → next stage

| Verdict | Next   | Notes                          |
|---------|--------|--------------------------------|
| SOLVED  | verify |                                |
| ERROR   | halt   | write `output/error_report.md` |

## Invariants (restated here per §3's delegation corollary)

- The solver never dispatches a verifier. Verification is a distinct stage the orchestrator dispatches separately (§4 corollary (e)). A solver that launches its own verifier curates the inputs, and the self-bias reaches the verifier through that curation even in a fresh context. If the solver appears to spawn a verifier, report ERROR.
- The solver writes tests alongside the solution, but the skeptic verifier will not read those tests (see `stage_verify.md`). Tests are for the structured verifier and for future regression, not for the skeptic. The solver does not need to know which verifier sees what; the orchestrator enforces the split.
- The solver receives only `problem.md`, not the proposer's de-duplication list or any prior verdicts. Extra context is a premise-2 tax (long-context degradation) with no routing value at this stage.
