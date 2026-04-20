# Stage: verify

**Agents:** `verifier-structured` and `verifier-skeptic`, dispatched independently by this stage. Both must PASS for the triple to be accepted.

## Why two verifiers, and why these two

A single verdict is one noisy sample of the underlying quality (premise 4, stochastic error). Variance falls roughly as 1/N under independent draws, but only under independent draws. Two verifiers given identical instructions share blind spots (§4 corollary (c) of `../../principles.md`).

The two framings:

- **`verifier-structured`**: re-derive. Writes its own solution from scratch in a clean context, runs the submitted tests against its own solution, then checks that its solution and the submitted solution agree on every input.
- **`verifier-skeptic`**: break. Given only the problem and the submitted solution (NOT the submitted tests), constructs adversarial inputs aimed at weak points. If the submitted solution misbehaves on any, FAIL.

Both are framed adversarially (the job is finding errors, not confirming correctness) (§4 corollary (e)).

Both verifiers run on the same underlying model. Framing-induced independence is the floor, not the ceiling (§4 corollary (b)). A same-model pair still shares model-level biases. Cross-model verification is the next step up when the budget allows.

## Procedure

1. Read `state/pipeline_state.json`. Let `id = current_problem_id`.
2. Launch `verifier-structured` on `output/solved/<id>/`. Save result to `output/verified/<id>/structured.md`.
3. Launch `verifier-skeptic` on `output/solved/<id>/problem.md` + `solution.*` (**do not pass** `tests.*`). Save to `output/verified/<id>/skeptic.md`.
4. Read both verdicts. Each failing verdict carries a `class` tag from its declared closed set.
5. On double PASS: move the triple to `output/accepted/<id>/`. Update state: `problems_completed += 1`, `stuck_count = 0`, `recent_reject_classes = []`, `current_problem_id = null`, `current_stage = "propose"`. Append a line to `output/history.jsonl`. Commit: `pipeline: accept <id>`.
6. On any FAIL: keep the verdict logs, drop `output/solved/<id>/`. Collect the class tag(s) from the failing verifier(s) into a list `[{verifier, class}, ...]`. Update state: `stuck_count += 1`, append the list to `recent_reject_classes` and trim to the last two entries, `current_problem_id = null`, `current_stage = "propose"`. Append a line to `output/history.jsonl` with the list in `reject_classes`. Commit: `pipeline: reject <id>, <structured>/<skeptic>`.

Steps 2 and 3 are independent and may run in parallel.

## Verdict → next stage

Local verdict is the `(Structured, Skeptic)` pair. The orchestrator collapses it to the top-level verdicts named in `../CLAUDE.md`'s transition table: double PASS → `ACCEPT`, anything else → `REJECT`.

| Structured | Skeptic | Top-level | Next                                         |
|------------|---------|-----------|----------------------------------------------|
| PASS       | PASS    | ACCEPT    | propose (++problems_completed)               |
| PASS       | FAIL    | REJECT    | propose (++stuck_count)                      |
| FAIL       | *       | REJECT    | propose (++stuck_count)                      |

The orchestrator, not either verifier, routes on the pair. Neither verifier knows the other's verdict.

## Invariants (restated here per §3's delegation corollary)

- Both verifiers are dispatched by the orchestrator, not by the solver (§4 corollary (a)). If the solver's stage ever launches a verifier, the invariant is broken. Report ERROR.
- Both verifiers are adversarially framed (§4 corollary (e)), stated as "find errors," not "evaluate correctness."
- The floor is two verifiers (§4 corollary (b)): a single verdict is a noisy sample. Dropping to one silently collapses the independence guarantee.
- Framings are distinct (§4 corollary (c)): re-derivation vs. break-by-adversarial-input.
- The skeptic does not see the submitted tests. Identical tests would anchor its search to the same cases the submitter already considered. The verdict would be a restatement, not an independent sample.
- **Teardown on REJECT (§1 corollary (j)).** Step 6 drops `output/solved/<id>/`, an automated rollback of a committed stage's artifact. Deleted: `output/solved/<id>/`, named in the `pipeline: reject <id>, <classes>` commit and in the `reject_classes` state entry. Survives: `output/proposed/<id>/`, abandoned in place as an orphan. It is reachable by id but never looked up: no stage scans `output/proposed/*/`; every stage reads only the id in `current_problem_id`, which is reset to null on REJECT. This path-addressing-by-state, not by directory scan, is what makes the separate survivor record §1(j) would otherwise require unnecessary here.
