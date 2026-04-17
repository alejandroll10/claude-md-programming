# Example: Autonomous benchmark generator

First worked example in this repo. Translates the principles in `../../principles.md` into concrete files for a synthetic domain.

**Task.** Given a topic, autonomously produce `target` verified `(problem, solution, tests)` triples. Two independent verifiers must pass each triple under distinct framings before it is admitted.

## What to notice

- **`CLAUDE.md`** carries only the pipeline graph, the state shape, the load-bearing invariants, and pointers to stage docs. Stage procedures live under `docs/`. (§1, §2)
- **`state/pipeline_state.json`** is compact (routing state, not observability). (§1 corollary (e))
- **Each stage dispatches a fresh-context subagent.** The orchestrator never does stage-level work itself. (§1 corollary (d), §3)
- **Verification is its own stage** with two verifiers under different framings, both adversarially posed. The solver never sees the verifier. (§4)
- **Termination is mechanical.** The loop ends when `problems_completed >= target` or when `stuck_count >= 3`. No exit depends only on LLM judgment. (§5)
- **Load-bearing invariants are restated at each surface the work enters from**: this CLAUDE.md, each stage doc, each verifier agent. (§3 delegation corollary)

## What is included

- `CLAUDE.md`: the orchestrator.
- `state/pipeline_state.json`: initial state.
- `docs/stage_verify.md`: the representative stage. Exercises every §4 corollary.
- `.claude/agents/verifier-structured.md` and `.claude/agents/verifier-skeptic.md`: the two verifiers, with distinct framings (§4 corollary (b)).

`docs/stage_propose.md` and `docs/stage_solve.md` are referenced from `CLAUDE.md` but not yet written. They follow the same shape as `stage_verify.md`. Kept out of this first iteration on purpose. The example should be as small as it can be while being real.

The domain is synthetic. Swap "benchmark generator" for any pipeline with the same shape (dataset curation, translation review, proof-obligation discharge) and the scaffolding carries over.
