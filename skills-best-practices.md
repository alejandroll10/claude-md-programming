# Skills: best practices

How to author the `.claude/skills/<name>/SKILL.md` files (and their scripts) that workers and the orchestrator load on trigger. Read `principles.md` first; this doc is operational, not foundational.

A skill is a self-contained capability the harness loads when triggered. Per §3, it lands in whoever is currently running, so the placement question is: which agent or stage actually needs it, and does the skill's description trigger only there?

## The spectrum

Skills span a real range. Pick the shape from the failure modes the skill must prevent, not from a default template.

| Shape | Example | Body content | When to use |
|---|---|---|---|
| Thin wrapper | One-line invocation of a script | Minimal: "run this with the user's query" | Tool whose misuse has no real cost |
| Tool with guidance | Script plus when/how to invoke, anti-triggers | Usage examples, "when NOT to use," output format | Tool the model would otherwise misuse or skip |
| Workflow | All prose, no script | Step-by-step procedure, scoped invariants | Judgment-heavy task with side effects or invariants |

A thin wrapper that should have been a workflow leaks failure modes the skill exists to prevent. A workflow that should have been a thin wrapper bloats the consumer's context with prose the model already knows.

## Frontmatter: enforcement, not advice

Three levers, ordered by how strongly they restrict invocation:

- **`disable-model-invocation: true`.** The skill cannot auto-trigger. Only the user fires it explicitly. Right answer for skills with side effects the model should not initiate (posting, sending, executing trades). Premise 5 (path-of-least-resistance) would otherwise let the model decide on its own to invoke.
- **`user-invocable: false`.** Hides the skill from explicit user `/skill` invocation; only consumers (agents, the orchestrator) dispatch it. Use for internal layers in a pipeline whose direct invocation by the user would skip preconditions.
- **`allowed-tools: ...`.** Capability scoping, same lever as for subagents. A workflow skill that orchestrates reads should not have `Write` access; the prose may say "do not edit" but premise 5 ignores it.

Combine as defense in depth. A workflow skill with side effects often gets `disable-model-invocation: true` *and* `allowed-tools` restriction.

## Body content patterns

Patterns that earn their place in real pipelines.

**Trust calibration baked in.** When the skill's underlying tool is unreliable in non-obvious ways, declare the reliability profile in the SKILL.md so consumers do not over-trust. Example: codex-math opens with "produces false positives at ~50% rate. Treat every output as a lead, not a verdict." This is premise 4 (stochastic error) localized to one capability. Skip when the tool is straightforward (a price lookup does not need a trust section).

**Hierarchy across overlapping skills.** When multiple skills could answer the same question, the model picks heuristically and drifts. State the hierarchy in the skill that is *not* primary. Example: stocknews-api opens with "Confirmation layer, not primary research" and orders itself relative to web search and Grok. The skill that loses the contest names the contest, so its peers do not need to.

**"When NOT to use" sections.** Premise 5 makes the model reach for any available tool. Anti-trigger lists resist that. Example: yfinance says "NOT for deep fundamentals"; codex-math says "Do not use for routine algebra." Each named anti-trigger is a failure mode the author has seen.

**Resist-the-cheap-default in defaults.** When the skill exposes a parameter with a cheap-but-bad default and an expensive-but-correct one, name the asymmetry and pick the right default. Example: codex-math says "always use high reasoning effort for hard problems; cost is small, missing a proof is large." Without this the model picks low to save tokens (premise 5 again).

**Scripts for deterministic ops; prose for judgment.** All script-backed skills push the operation into the script and keep the SKILL.md focused on *when* and *how to invoke*. Match the split: code that always runs the same way for the same inputs goes in the script; the model's discretion about when to call it goes in the prose. If the prose says the script is optional, premise 5 makes the model re-derive from scratch.

## Where skill-scoped invariants live

Some invariants fire only when one capability is exercised: "never preview trades in a Twitter reply," "always cite Codex outputs as leads, not verdicts." These do not belong in CLAUDE.md (would tax every step), do not belong in subagent definitions (the skill is not a dispatched agent), and do not belong at the call site (would drift across calls and miss user-direct invocations).

The skill itself is the right home. The skill is the only surface that travels with the capability. If the invariant must hold whenever this capability is used, write it in the SKILL.md.

This is the §3 delegation corollary applied to skills: restate the invariant at the surface where breach is reachable. For skill-scoped invariants, that surface is the skill.

## What this doc does not cover

Claude Code skill mechanics (file layout, frontmatter syntax, allowed-tools enumeration, harness loading rules) belong in the Claude Code docs, not here. This doc covers the pattern-specific choices: what content goes in the skill, how to bound its invocation, and how to resist the failure modes premise 5 keeps producing.
