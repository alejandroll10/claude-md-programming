# claude-md-programming

Principles and vocabulary for designing autonomous, multi-stage Claude Code pipelines: a repository's CLAUDE.md, subagents, skills, and state files treated as a coherent program.

## Scope

Long-running, unattended pipelines (hours to days without a human at the terminal). Overkill for short interactive sessions.

There is no human in the loop, so there is no conventional test cycle either: the pipeline must verify its own work as it runs. The principles' verification gates (§4) and mechanical termination (§5) replace what tests would do in a dev loop. Pre-launch sanity (schema validates, scripts parse, sandboxed dry-run completes one cycle) is normal software engineering on the deterministic scaffolding, not part of this pattern.

## Runner

The orchestrator is a single long-running Claude Code session (typically launched with `claude --dangerously-skip-permissions`) that reads state, dispatches, commits, and continues across turns within that session. The `while` loop in `principles.md` is the model's behavior given CLAUDE.md, not an external scheduler invoking Claude per stage.

## Start here

- [`principles.md`](principles.md): the design pattern. Begin with the premises; every principle derives from at least one.
- [`checklist.md`](checklist.md): the short-form setup checklist for starting a new pipeline, mapped to the principles.
- [`glossary.md`](glossary.md): one-line definitions for the terms used across the other docs.
- [`subagents-best-practices.md`](subagents-best-practices.md): operational guidance for authoring `.claude/agents/*.md` workers and verifiers.
- [`skills-best-practices.md`](skills-best-practices.md): operational guidance for authoring `.claude/skills/*/SKILL.md` capabilities.
- [`state-schema-patterns.md`](state-schema-patterns.md): patterns for shaping the routing-state JSON, distilled from real pipelines.
- [`examples/benchmark-generator/`](examples/benchmark-generator/): a worked example translating the principles into concrete CLAUDE.md, state, stage docs, and agent definitions.

## Status

Early. Intentionally short. We expand only as the principles prove themselves against real projects.
