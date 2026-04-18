# Stage: propose

**Agent:** `proposer`, dispatched by this stage. Proposes one new `(problem)` for the configured topic.

## Why this is its own stage

Proposing and solving in a single context biases the proposer toward problems it already knows it can solve (premise 5, path-of-least-resistance, of `../../principles.md`). A fresh-context proposer commits to a problem before a solver is ever loaded, so "is this solvable by me right now" cannot steer problem selection.

## Procedure

1. Read `state/pipeline_state.json`. Let `topic = state.topic`.
2. Read `output/history.jsonl` and collect the titles of all previously proposed problems (accepted and rejected) for this topic. Pass them to the proposer as a de-duplication list, not as examples to imitate.
3. Launch `proposer` with the topic and the de-duplication list. It writes `output/proposed/<id>/problem.md`, where `<id>` is a fresh monotonic id assigned by this stage (not by the agent).
4. Verify the file exists and is non-empty. If not, verdict `ERROR`.
5. Update state: `current_problem_id = <id>`, `current_stage = "solve"`. Append a line to `output/history.jsonl`. Commit: `pipeline: propose <id>`.

## Verdict → next stage

| Verdict  | Next  | Notes                              |
|----------|-------|------------------------------------|
| PROPOSED | solve | `current_problem_id` set           |
| ERROR    | halt  | write `output/error_report.md`     |

## Invariants (restated here per §3's delegation corollary)

- The proposer never reads prior solutions or verifier verdicts. It sees the topic and the de-duplication titles only. Feeding it solutions anchors new problems to the shape of solutions already seen.
- The id is assigned by the orchestrator, not the agent. Agents that mint their own ids race on collisions across parallel runs and defeat the atomic-commit protocol (§1 corollary (a)).
- The proposer does not dispatch the solver. Stages are chained by the orchestrator, not by the worker (§1 corollary (d)).
