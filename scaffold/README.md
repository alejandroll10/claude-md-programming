# Scaffold

Copy-paste starter for a new pipeline following this repo's design pattern. Not a worked example; a blank frame.

## What is here

```
scaffold/
├── CLAUDE.md                         # orchestrator stub
├── state/pipeline_state.json         # initial valid state (status=running, current_stage=STAGE_A)
├── docs/stage_TEMPLATE.md            # one stage doc, fill in per stage
└── .claude/agents/
    ├── worker_TEMPLATE.md            # worker agent stub
    └── verifier_TEMPLATE.md          # verifier agent stub (adversarial framing)
```

Every placeholder is wrapped in angle brackets: `<topic>`, `<verdict_space>`, `<stage_a>`, etc. Search-and-replace them with your domain before the first run.

## How to use

1. Copy the whole directory into your pipeline repo.
2. Rename placeholders in `CLAUDE.md` (topic, target, stage names, verdict spaces).
3. For each stage in your pipeline, copy `docs/stage_TEMPLATE.md` to `docs/stage_<name>.md` and fill in.
4. For each agent role (worker, verifier), copy the relevant template to `.claude/agents/<role>.md` and fill in.
5. Walk the `checklist.md` top to bottom. The scaffold covers the skeleton; the checklist names the design decisions the skeleton cannot make for you (verdict spaces, termination thresholds, invariants derived from your incidents).

## What the scaffold does *not* decide for you

- The stage list and transition table (you own this).
- The verdict space per stage (declare in each stage doc).
- Load-bearing invariants (derive from incidents, system properties, structural distance, or premise-5 anti-shortcuts per `invariants.md`).
- Termination thresholds (absolute cap, budget cap, or delta trigger per `principles.md` §5 corollary (b)).
- Whether the pipeline is single-mode (like `examples/benchmark-generator`) or multi-mode (see `state-schema-patterns.md`, "Mode or variant flag").

## Next step after copying

Read `checklist.md` and fill the scaffold in against it. The scaffold is a skeleton, not a complete design.
