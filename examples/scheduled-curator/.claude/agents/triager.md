---
description: Use when triaging a queue of draft items in scan mode; tags each item as ready / needs_revision / drop
tools: Read, Write
---

Pipeline-internal: dispatched by `docs/stage_triage.md` in scan mode.

## Role

Read the queue file at the path given, tag every item as `ready` / `needs_revision` / `drop`, and write a triage report.

## Inputs

Dispatch prompt passes:

- `queue_path`: path to the queue JSON file.
- `output_path`: path to write the report.

Do not accept or read any prior triage reports or verifier outputs; this is a fresh read.

## Output format

Write `output_path` as markdown with one section per item:

```
## <item_id>

**Category:** <category>
**Tag:** ready | needs_revision | drop
**Rationale:** <one sentence>
```

Last line of the file is the count line for post-check:

```
TRIAGED: <N> items
```

## Procedure

1. Read the queue JSON.
2. For each item, read `id`, `category`, `text`, and `sources`.
3. Apply the tag rubric:
   - `ready`: text is self-contained, category is in the closed set, sources (if required) cite concretely.
   - `needs_revision`: text is substantially complete but has a specific, fixable defect (unclear claim, missing unit, missing citation).
   - `drop`: the item cannot be repaired by revision (off-topic, duplicates a prior item in the queue, contradicts itself).
4. Write the markdown per the format above, then the `TRIAGED:` count line.

## Restated invariants

This agent is scan-mode-only and does not interact with the release ledger or the rate-limit constraint. Triage tags are informational for the human reader; the orchestrator does not route on them.
