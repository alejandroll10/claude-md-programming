# Example: Autonomous benchmark generator

First worked example in this repo. Translates the principles in `../../principles.md` into concrete files for a synthetic domain.

**Task.** Given a topic, autonomously produce `target` verified `(problem, solution, tests)` triples. Two independent verifiers must pass each triple under distinct framings before it is admitted.

## What to notice

- **`CLAUDE.md`** carries only the pipeline graph, the state shape, the invariants, and pointers to stage docs. Stage procedures live under `docs/`. (§1, §2)
- **`state/pipeline_state.json`** is compact (routing state, not observability). (§1 corollary (e))
- **Each stage dispatches a fresh-context subagent.** The orchestrator never does stage-level work itself. (§1 corollary (d), §3)
- **Verification is its own stage** with two verifiers under different framings, both adversarially posed. The solver never sees the verifier. (§4)
- **Termination is mechanical.** The loop ends when `problems_completed >= target`, when `stuck_count >= 3` (budget ceiling), or when the last two REJECT rounds' `{verifier, class}` sets are equal (delta trigger). No exit depends only on LLM judgment. (§5)
- **Load-bearing invariants are restated at each surface the work enters from**: this CLAUDE.md, each stage doc, each agent definition. Not every invariant appears at every surface; each is restated where it can be breached (e.g., invariant 2 reaches the solver agent but not the proposer). (§3 delegation corollary)
- **Independent dispatches run in parallel.** The two verifiers in `stage_verify.md` are launched concurrently, since their inputs are independent. (§6)

## What is included

- `CLAUDE.md`: the orchestrator.
- `state/pipeline_state.json`: initial state.
- `docs/stage_propose.md`, `docs/stage_solve.md`, `docs/stage_verify.md`: the three stage docs. `stage_verify.md` is the representative one and exercises every §4 corollary; the other two are deliberately shorter.
- `.claude/agents/proposer.md` and `.claude/agents/solver.md`: the proposer and solver.
- `.claude/agents/verifier-structured.md` and `.claude/agents/verifier-skeptic.md`: the two verifiers, with distinct framings (§4 corollary (c)).

The example should stay as small as it can be while being real; each new file needs to earn its place.

## What this example does not exercise

A few principles don't fit this domain and are deliberately unused here. A reader should not infer coverage from silence.

- **§1 corollary (f), environmental ground truth.** The pipeline is closed-world (no external data sources, credentials, or services), so there is no data-inventory manifest to maintain.
- **§1 corollary (i), schema migration as a transition.** The state schema does not change over the run.
- **§1 corollary (j), rollback artifacts.** Partially exercised: the REJECT branch in `stage_verify.md` is an automated rollback of the committed solve artifact, and is handled implicitly by the commit message + `reject_classes` state entry (see the stage doc's teardown note). No separate teardown artifact or manual-rollback path for other stages.
- **§5 corollary (f), graceful degradation as signal.** No stage has a fallback path to a weaker input, so there is no downgrade event to record.

A second example with external data and rollback would exercise these.

The domain is synthetic. Swap "benchmark generator" for any pipeline with the same shape (dataset curation, translation review, proof-obligation discharge) and the scaffolding carries over.
