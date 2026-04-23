# Glossary

One-line definitions for terms used across `principles.md`, `checklist.md`, and the examples. Cross-references point to the section that introduces each term.

## Architecture

- **Orchestrator.** The always-on LLM session with `CLAUDE.md` loaded. Reads state, dispatches stages, updates state, commits. Does not do stage-level work, with exceptions for decisions that depend on information only it has (§1 corollary (d)).
- **Transition.** One step of the orchestrator loop: read state, dispatch stage, receive verdict, update state, commit (§1).
- **Dispatch.** The orchestrator launching a stage's worker (usually a fresh-context agent) with the inputs the stage doc specifies (§1, §3).
- **Stage.** One unit of pipeline work, typically a single subagent dispatch, with a declared verdict space (§1).
- **Stage doc.** Per-stage document under `docs/`. Owns the local procedure, the stage's outgoing edges, and the invariants the stage must preserve (§1 corollary (b), §3).
- **Gate.** A stage whose only output is a verdict that decides whether another stage's work is accepted. Verification gates are the canonical case (§4).
- **Pipeline graph.** The stage list, gates, main loops, and top-level transition table. Lives in `CLAUDE.md` (§1 corollary (b)).
- **Markov property.** A pipeline has it when each stage's behavior depends only on the committed state, not on accumulated session history. Forced by §1.

## State and artifacts

- **Routing state.** The compact JSON the orchestrator reads and writes each transition. Never contains transcripts, logs, or observability content (§1, §2).
- **State schema.** The declared JSON shape of routing state, committed alongside the pipeline graph. Schema changes are their own transition, not a side effect of a stage (§1 corollary (i)).
- **Observability.** Human-facing artifacts (JSONL logs, dashboards, commit messages) written for monitoring and post-hoc review. The orchestrator never reads them for routing (§1 corollary (e)).
- **Reference artifact.** The file that captures environmental ground truth: data sources, credentials, service availability. Written once at pipeline entry; every stage reads it, nothing routes on it (§1 corollary (f)).
- **Environmental ground truth.** The external-world facts a reference artifact carries. Distinct from routing state and observability (§1 corollary (f)).
- **Teardown artifact.** Record of what was deleted and what was preserved when a committed stage is intentionally rolled back. Lets resume distinguish stale orphans from reusable upstream outputs (§1 corollary (j)).
- **Freshness check (freshness marker).** Per-stage test that an intermediate input is current for this run (mtime against pipeline-start, or an explicit marker written at entry). Without it, a resumed run silently consumes prior-run outputs (§1 corollary (a)).
- **Atomic commit.** State, artifacts, and observability log committed together in one durable write per stage transition, so a crash leaves the resume point unambiguous (§1 corollary (g)). On runs that may resume on a different machine, "durable" includes visibility to the other machines (push, shared store), not just local persistence.
- **Domain ledger.** Append-only file of domain facts stages both write to and read from for constraint queries (rolling-window budgets, catalyst presence, consecutive-decision rules). Fourth artifact class alongside routing state, observability, and reference artifacts (`state-schema-patterns.md`).
- **Preflight / post-check.** The two mechanical gates bookending every stage body: preflight verifies upstream inputs are fresh and well-formed before dispatch; post-check verifies this stage's outputs before the transition commits (`patterns.md`).
- **Mode.** Routing-state field selecting which top-level transition table applies, when one CLAUDE.md serves multiple flows. Set once per run, never changed mid-run (`state-schema-patterns.md`, "Mode or variant flag").
- **User-input stage.** Declared stage that blocks for a human-supplied value and records it (with provenance) to routing state. Not a side-effect of another stage (`patterns.md`).

## Delegation vehicles

- **Doc.** Content the orchestrator reads on demand. Lands in the current context. Cheapest, zero isolation (§3).
- **Script.** Deterministic code invoked directly by the orchestrator or an agent. No model tokens during execution; no coherence drift inside the call (§3).
- **Skill.** Self-contained module (instructions plus tools or scripts) loaded by the harness on trigger. Lands in whoever is currently running (§3).
- **Agent (fresh-context subagent).** Sub-conversation with its own system prompt, whose context starts empty apart from that prompt and its inputs. Substantial (not total) context isolation from the parent: samples are less correlated, not independent (§3, premise 8).
- **Worker.** Generic term for the agent dispatched to do a stage's work, as distinct from verifier agents. A solver, proposer, or any producer of the stage's artifact (§3).

## Verification

- **Verifier.** The agent the orchestrator dispatches to evaluate a worker's artifact. Framed adversarially, isolated from the worker (the worker has no visibility into the verifier or its framing), returns a structured verdict and free-form critique to the orchestrator, never to the worker (§4, §4 corollary (a)).
- **Verdict.** The structured, enumerated output of a stage that the orchestrator routes on (`PASS`/`FAIL`, `ACCEPT`/`REJECT`, etc.). Introduced in §1's pseudocode; efficiency tradeoff in §5 corollary (d).
- **Verdict space.** The closed set of verdicts a stage can emit. Declared in the stage doc. Every verdict space includes an `ERROR` entry that routes to terminate.
- **Structured verdict vs. free-form critique.** The structured verdict is cheap to route on; the free-form critique is harder to game and carries qualitative content. Ship both (§4 corollary (d)).
- **Adversarial framing.** A verifier instructed to find errors, not to evaluate correctness. Counteracts self-bias, which reaches the verifier through its own instructions even in a fresh context (§4 corollary (e)).
- **Distinct framings.** Different postures, phrasings, or rubrics across verifiers, so their samples are less correlated than identical instructions would produce. Framing is the floor; different models, tools, or context sizes reduce correlation further (§4 corollary (c)).

## Failure and termination

- **Mechanical predicate.** A branch condition evaluated by numeric rules over the state JSON (counter, threshold, equality). Contrast with LLM-judged predicates; termination paths must have at least one mechanical branch (§5, §5 corollary (a)).
- **Signal failure.** A task-level failure (verifier REJECT, solver gave up, malformed model output). Feeds the termination counter (§5 corollary (c)).
- **Noise failure.** An infrastructure failure (tool timeout, rate limit, network blip). Retried at the dispatch layer, never charged to the termination counter (§5 corollary (c)).
- **Fallback / graceful degradation.** A stage substituting a weaker input for a missing one. Must be recorded in state as a signal event, not hidden in logs (§5 corollary (f)).
- **Absolute cap.** Conservative counter-based termination set tight, used when the loop is new and you have no history and no reliable per-iteration signal (§5 corollary (b), strategy (i)).
- **Budget cap.** Counter-based termination set at the count where marginal value historically saturates for this loop, once runs exist to fit it on (§5 corollary (b), strategy (ii)).
- **Delta trigger.** Termination predicate that fires when the next iteration is unlikely to add marginal value (e.g., two consecutive REJECT rounds with structurally equal feedback) (§5 corollary (b), strategy (iii)).
- **Self-recovery.** Cheap in-pipeline retry paths that run before termination fires: fresh-instance retry, framing swap, coarser fallback (§5 corollary (e)).
- **Escalation.** Handoff out of the autonomous loop to a human or higher-level system. The backstop, not the first response (§5 corollary (e)).

## Doctrine

- **Load-bearing invariant.** A rule whose breach is silent, cascading, and reachable from more than one surface. Restated at each surface the rule can enter from (§3 delegation corollary).
