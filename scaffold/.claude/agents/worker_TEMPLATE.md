---
description: <Use when ... (trigger predicate, not a label; see `../../../subagents-best-practices.md` Layer 1)>
tools: <Read, Write, Bash, ...>  # restrict to what this role needs; tool restriction is enforcement, not advice.
# model: <haiku-4-5 | sonnet-4-6 | opus-4-7>  # optional; omit to inherit from orchestrator. Cross models to reduce correlation with verifiers.
# skills: [<skill_name>]  # optional; attach capabilities explicitly.
---

<If pipeline-internal only, state so on this line. Otherwise assume ad-hoc invocations may reach this agent.>

## Role

<One sentence. What this worker produces, and under what inputs.>

## Inputs

<The dispatch prompt will pass paths; this section names the schema. Paths, not bodies.>

## Output format

<Exact form the orchestrator parses. "Last line is `VERDICT: <V>`" or "writes `<path>` in this shape". Format drift breaks routing silently (`../../../subagents-best-practices.md` Layer 2).>

## Procedure

<Numbered steps. Underspecified paths get filled with shortcuts (premise 5); name the path, not just the goal.>

1. Read `<path>`.
2. <Step>.
3. Produce `<output>` in the format above.

## Restated invariants

<Only invariants whose breach is reachable from this agent's actions. Not all invariants. See `../../../invariants.md` "Multi-surface restatement" for when to restate.>

1. <Example: "Do not read prior verdicts or scores; the orchestrator's retry prompt never includes them.">
