# claude-md-programming

Principles and vocabulary for designing autonomous, multi-stage Claude Code pipelines: a repository's CLAUDE.md, subagents, skills, and state files treated as a coherent program.

## Scope

Long-running, unattended pipelines (hours to days without a human at the terminal). Overkill for short interactive sessions.

## Runner

The orchestrator is a single long-running Claude Code session (typically launched with `claude --dangerously-skip-permissions`) that reads state, dispatches, commits, and continues across turns within that session. The `while` loop in `principles.md` is the model's behavior given CLAUDE.md, not an external scheduler invoking Claude per stage.

## Start here

- [`principles.md`](principles.md): the design pattern. Begin with the premises; every principle derives from at least one.
- [`checklist.md`](checklist.md): the short-form setup checklist for starting a new pipeline, mapped to the principles.
- [`glossary.md`](glossary.md): one-line definitions for the terms used across the other docs.
- [`examples/benchmark-generator/`](examples/benchmark-generator/): a worked example translating the principles into concrete CLAUDE.md, state, stage docs, and agent definitions.

## Status

Early. Intentionally short. We expand only as the principles prove themselves against real projects.
