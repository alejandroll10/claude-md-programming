# Skills: best practices

How to author the `.claude/skills/<name>/SKILL.md` files (and their scripts) that workers and the orchestrator load on trigger. Read `principles.md` first; this doc is operational, not foundational.

A skill is a self-contained capability the harness loads when triggered. Per §3, it lands in whoever is currently running, so the placement question is: which agent or stage needs it, and does the skill's description trigger only there?

## The spectrum

Skills span a wide range of shapes:

| Shape | Example | Body content | When to use |
|---|---|---|---|
| Thin wrapper | One-line invocation of a script | Minimal: "run this with the user's query" | Tool whose misuse has no significant cost |
| Tool with guidance | Script plus when/how to invoke, anti-triggers | Usage examples, "when NOT to use," output format | Tool the model would otherwise misuse or skip |
| Workflow | All prose, no script | Step-by-step procedure, scoped invariants | Judgment-heavy task with side effects or invariants |

The shapes mix in practice. A workflow can terminate in a deterministic script call (a reply-generation skill orchestrates context-loading and drafting in prose, then ends with a publish script). The split that matters is per-section: judgment in prose, deterministic ops in scripts. Pick the dominant shape from the failure modes the skill must prevent.

A thin wrapper that should have been a workflow leaks failure modes the skill exists to prevent. A workflow that should have been a thin wrapper bloats the consumer's context with prose the model already knows.

## Frontmatter: enforcement, not advice

The frontmatter controls *when* the skill loads and *what* it can do. Both matter; neither can be enforced from prose.

**`description:` is the trigger predicate.** The harness reads the description and decides whether to auto-load the skill based on whether it matches what the model is currently doing. Effective descriptions are written as predicates ("Use when you need real-time social-media sentiment", "Use to confirm a claim from web search with a precise timestamp"), not as labels ("Social-media search tool"). Too broad and the skill loads in contexts where it does not apply (the orchestrator's read-state-and-route turn pulls it in for no reason). Too narrow and the consumer never reaches it. Treat the description as the most important field in the file.

**`argument-hint: ...`.** Tells the harness what arguments the skill expects when invoked, surfacing them in the user's `/skill` autocomplete. Use whenever the skill takes a positional argument (a query, a file path, an identifier). Without it, the user has to read the SKILL.md to know what to type.

**`disable-model-invocation: true`.** The skill cannot auto-trigger. Only the user fires it explicitly. Right answer for skills with side effects the model should not initiate on its own (publishing, sending, irreversible external calls). Premise 5 (path-of-least-resistance) would otherwise let the model decide on its own to invoke.

**`user-invocable: false`.** Hides the skill from explicit user `/skill` invocation; only consumers (agents, the orchestrator) dispatch it. Use for internal layers in a pipeline whose direct invocation by the user would skip preconditions.

**`allowed-tools: ...`.** Capability scoping, same lever as for subagents (see `subagents-best-practices.md`: tool restriction is enforcement, not advice). A workflow skill that orchestrates reads should not have `Write` access; the prose may say "do not edit" but premise 5 ignores it.

Combine as defense in depth. A workflow skill with side effects often gets `disable-model-invocation: true` *and* `allowed-tools` restriction.

## Body content patterns

Patterns that earn their place in production pipelines.

**Trust calibration baked in.** When the skill's underlying tool is unreliable in non-obvious ways, declare the reliability profile in the SKILL.md so consumers do not over-trust. A math-verification skill backed by an external model that produces false positives ~50% of the time should open with "treat every output as a lead, not a verdict." This is premise 4 (stochastic error) localized to one capability. Skip when the tool is straightforward (a price lookup does not need a trust section).

**Hierarchy across overlapping skills.** When multiple skills could answer the same question, the model picks heuristically and drifts. State the hierarchy in the skill that is *not* primary. A timestamp-confirmation skill that is meant to verify claims from a primary search tool, not replace it, should open with "confirmation layer, not primary research" and order itself relative to its peers. The skill that loses the contest names the contest, so its peers do not need to.

**"When NOT to use" sections.** Premise 5 makes the model reach for any available tool. Anti-trigger lists resist that. A quick price-lookup skill should say "NOT for deep fundamentals"; a math-verification skill should say "do not use for routine algebra." Each named anti-trigger is a failure mode the author has seen.

**Resist-the-cheap-default in defaults.** When the skill exposes a parameter with a cheap-but-bad default and an expensive-but-correct one, name the asymmetry and pick the right default. A reasoning-effort knob with `low | medium | high` options should default to `high` for hard problems if the cost asymmetry is small in money but large in correctness. Without an explicit override the model picks low to save tokens (premise 5 again).

**Scripts for deterministic ops; prose for judgment.** All script-backed skills push the operation into the script and keep the SKILL.md focused on *when* and *how to invoke*. Match the split: code that always runs the same way for the same inputs goes in the script; the model's discretion about when to call it goes in the prose. If the prose says the script is optional, premise 5 makes the model re-derive from scratch.

## Where skill-scoped invariants live

Some invariants fire only when one capability is exercised: "never preview an upcoming action in a public-facing reply generated by this skill," "always cite this skill's outputs as leads, not verdicts." These do not belong in CLAUDE.md (would tax every step), do not belong in subagent definitions (the skill is not a dispatched agent), and do not belong at the call site (would drift across calls and miss user-direct invocations).

The skill itself is the right home. The skill is the only surface that travels with the capability. If the invariant must hold whenever this capability is used, write it in the SKILL.md.

A skill-scoped invariant is single-surface: the skill is the only surface from which it can be breached. Place it there and nowhere else. The §3 delegation corollary's multi-surface restatement does not apply, because there is only one surface.

## What this doc does not cover

Claude Code harness internals (file layout on disk, loading order, full frontmatter schema) belong in the Claude Code docs, not here. This doc covers the pattern-specific choices: what content goes in the skill, which frontmatter fields earn the author's attention, and how to resist the failure modes premise 5 keeps producing.
