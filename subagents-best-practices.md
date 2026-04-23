# Subagents: best practices

How to author the `.claude/agents/<name>.md` files that workers and verifiers run inside. Read `principles.md` first; this doc is operational, not foundational.

A subagent definition has three layers, and most authoring mistakes come from putting content in the wrong layer.

| Layer | What it controls | Lever |
|---|---|---|
| Frontmatter (`description:`, `tools:`, `model:`, `skills:`) | What the agent *can* do and when it gets dispatched | Capability and trigger |
| System prompt | What it does *every* time | Role, invariants, output format |
| Dispatch prompt | What it does *this* time | Per-call inputs |

## Layer 1: frontmatter

**`description:` is the dispatch trigger, not a label.** The harness uses the description to decide whether to auto-route a task to this agent. Real agents write descriptions as trigger predicates ("Use when verifying a proof for mathematical errors") not human-readable names ("Math verifier"). A description that's too broad pulls the agent into work it shouldn't do; too narrow and the orchestrator never reaches it. This is the dispatch analog of `tools:`: a misconfigured description silently routes wrong, the same way a missing tool silently fails to enforce.

**Tool restriction is enforcement, not advice.** A verifier with edit access "fixes" the artifact instead of reporting it broken (premise 5, path-of-least-resistance). Writing "do not edit the file" in the system prompt is not the same as withholding the tool. Verifiers get read-only tools; workers do not get the Task tool (or other ability to spawn subagents); only the orchestrator's privileged role gets state-mutation access.

**Model choice is a correlation lever.** Premise 8 (fresh instances are less correlated, not independent) has a floor at the model-level correlation. Two verifiers on the same model share blind spots that distinct framings (§4(c)) can only partially break. Crossing models lowers the floor. If the orchestrator runs Opus, a Haiku verifier and a Sonnet verifier give a measurable correlation drop a same-model pair can't. The `model:` field is optional; omit it to inherit from the orchestrator, set it explicitly when correlation reduction matters.

**`skills:` attaches capabilities at the frontmatter layer.** When an agent needs a domain skill (math verification, market data, fact-checking), list it in `skills:` rather than expecting the agent to discover it. This makes the dependency explicit and audit-able. See `skills-best-practices.md` for skill authoring; the attachment is a frontmatter concern.

## Layer 2: system prompt

This is what the agent does on *every* invocation. If the agent is reachable from outside the pipeline (the default for any file under `.claude/agents/`), content here must be true regardless of who dispatches; see "Reusability across pipelines" below for the pipeline-internal exception.

**Role and output format.** The orchestrator has to parse a verdict to route. If the format is "last line is `VERDICT: ACCEPT|REJECT`" or "writes the verdict to `output/<id>/verdict.json`," it lives here so every dispatch produces it. Format drift breaks routing silently.

**Restated invariants (§3 delegation corollary).** Restate the invariants whose breach is reachable from *this* agent's actions, not all of them. A solver needs "never read prior verifier verdicts." A verifier needs "find errors, do not confirm." A proposer needs "do not template off rejected ideas." The agent definition is one of three surfaces an invariant can enter from (CLAUDE.md, stage doc, agent definition); restate where it can be breached, not everywhere.

**Adversarial framing for verifiers (§4(e)).** Concretely: "A pass means you exhausted attack vectors and found nothing, not that you read it and it seemed fine." Without this the verifier drifts toward confirmation. Premise 1 (self-bias) reaches the verifier through its own instructions, even in a fresh context.

**Distinct framings across verifiers (§4(c)).** Two near-duplicate verifier system prompts produce correlated outputs even when both are framed adversarially. The framings must be genuinely different postures: one does structured step-by-step re-derivation, the other does skeptical-reader holistic pass. Different rubrics on the same target, not paraphrased versions of one rubric.

## Layer 3: dispatch prompt

This is what changes per invocation. The hygiene rules apply every dispatch.

**Pass paths, not bodies (§2).** `"Verify the artifact at output/solve_42.md"`, not the artifact contents pasted in. The agent fetches.

**Pass only what this call needs.** Not the orchestrator's accumulated state, not the full verdict history, not "we've tried this three times." Premise 2 (long-context degradation) hits the agent's context the same way it hits the orchestrator's. Per-call inputs that the orchestrator already filtered are the right shape.

**Worker isolation from verifier signal (§4(a), §4(d)).** When dispatching a retry, the orchestrator must not include "the verifier said X." This is a dispatch-protocol rule, not an agent-definition rule, and lives only in the orchestrator's dispatch step. It is invisible from the agent's side, so it cannot be enforced in the agent file. Audit the dispatch code, not the agent definition.

## The split is the skill

Most authoring failures are content in the wrong layer. Three patterns to watch for:

1. **Invariants in the dispatch prompt.** Re-explained every call, drifts across calls, and silently absent when the agent is invoked outside the pipeline. Move to system prompt.

2. **Per-call inputs in the system prompt.** Becomes stale the moment the call shape changes. Move to dispatch prompt.

3. **Tool restrictions as instructions.** "Do not edit the artifact" in prose is wishful thinking under premise 5. Move to frontmatter as tool exclusion.

## Reusability across pipelines

An agent file under `.claude/agents/` is reachable by any session in the directory, including ad-hoc invocations outside the pipeline. The system prompt is the only thing that travels with the agent. If a load-bearing invariant lives only at the dispatch site (the stage doc or the orchestrator's dispatch code), it does not apply to ad-hoc invocations. If the agent is intended to be reused outside the pipeline, the invariants it must always honor belong in the system prompt, not at the dispatch site.

If the agent is pipeline-internal only, the system prompt can lean on the dispatch context. Make this explicit in the agent file's first line so a future reader does not invoke it standalone and get unexpected behavior.
