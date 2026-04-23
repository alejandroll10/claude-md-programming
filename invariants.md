# Invariants: identifying, placing, restating

Half the work in a production pipeline is invariants: the numbered rules in CLAUDE.md, the framing reminders in agent definitions, the "never do X" lines in stage docs. Mature CLAUDE.mds carry 15-20 of them. The principles say invariants exist (§3 delegation corollary) but not how to find them, where to put them, or when to restate them.

## Definitions

An **invariant** is a rule that must hold across more than one moment in the pipeline, whose breach would corrupt downstream work even if no one noticed at the time. The breach is *silent* (no immediate error) and *cascading* (downstream stages consume the corruption).

A **load-bearing invariant** is the subset whose breach is silent, cascading, *and* reachable from more than one surface. The third condition is what triggers multi-surface restatement (§3 delegation corollary, glossary). Most invariants are not load-bearing; they live in one place. The bar for restatement is high.

## Where invariants come from

Four honest sources, in order of how reliable they are:

1. **Incidents.** Something broke, you traced it, you wrote a rule. Rules with an incident attached are load-bearing by construction. Example: a research pipeline whose post-pipeline math audits keep failing learns to require an audit gate before any post-pipeline math edit. The rule names the incident in its body.

2. **System-property invariants.** Rules that enforce a mechanical property the pattern itself requires: commit atomicity (§1(g)), input freshness (§1(a)), schema integrity (§1(i)). These trace to principle corollaries, not to incidents or model behavior. They look generic ("commit after every transition", "verify input mtime against pipeline-start") because the property they enforce is generic. Interface contracts between components (output JSON validity, verdict-format conformance) belong here too: they are schema integrity at the dispatch boundary.

3. **Structural distance preservation.** Two roles must stay apart. A scoring stage that learns which candidates the selection stage already favors begins scoring *to confirm* those candidates; the scores are no longer independent and downstream selection is silently corrupted. The rule keeps the roles apart. These rules derive from premise 1 (self-bias) and premise 5 (path-of-least-resistance) acting across roles.

4. **Premise-5 anti-shortcuts.** When the model would default to a cheap path that satisfies the letter of the work but misses the intent, the invariant names the shortcut and bans it. A pipeline whose model defaults to resuming yesterday's plan rather than re-deriving on fresh data needs a rule naming "prior outputs are references, not destinations." The rule is not about prior outputs; it is about the shortcut.

If a candidate rule fits none of these four, it is probably ornament.

## Where invariants live

Three placements, picked by *scope of breach*:

| Placement | Scope of breach | Cost |
|---|---|---|
| CLAUDE.md (always-on) | Every transition can breach it | Highest token cost; pays §2 |
| Stage doc | Only this stage's body can breach it | Loaded on demand |
| Agent or skill definition | Only when this capability runs | Loaded only when dispatched |

The test: identify every surface from which the rule can be breached, then place it at the highest-frequency surface that catches every breach. If breach is reachable only from one stage, push the rule into that stage's doc. If every transition can breach it, CLAUDE.md is the right home, even at §2 cost.

**Mandate vs procedure.** A common pattern: the *mandate* belongs in CLAUDE.md ("verify input freshness before every step"), the *procedure* belongs per stage ("the freshness check for stage X reads files A, B, C and compares mtime against pipeline-start"). These are not duplicates; the mandate creates the obligation, the procedure operationalizes it for a specific stage. CLAUDE.md says what must hold; the stage doc says how this stage holds it. Pure-mandate rules with no per-stage procedure (boundary rules like "outputs are recommendations, not executions") have no procedure counterpart and live only in CLAUDE.md.

## Multi-surface restatement

Some load-bearing invariants are reachable from more than one entry surface. The §3 delegation corollary's instruction is precise: restate at each surface the rule can *enter* from. Not every surface that *touches* the invariant.

- **Entry surface vs detection surface.** If the orchestrator dispatches the worker, the orchestrator and the worker are entry surfaces (either can breach). A verifier that checks the worker's output is a detection surface, not an entry surface. The verifier does not breach the rule; it catches breaches. Detection surfaces do not need the rule restated.

- **Three layers, three breach paths.** A distance-preservation rule (e.g., "forecasts must not reference current holdings") restated only in CLAUDE.md catches orchestrator-driven breaches but misses direct invocations of the forecaster agent. Restated only in the agent it catches direct invocations but misses orchestrator framing. Three layers handle three breach paths: CLAUDE.md (orchestrator dispatch), agent definition (any invocation), and a verifier (detection of breaches the prior layers missed). When you write a multi-surface invariant, name its enforcement layers in the rule body, so future edits do not silently delete one.

- **The bar.** Restate only when the breach would be silent, cascading, *and* reachable from more than one entry surface. A rule reachable from one entry stays in one place.

## Patterns worth recognizing

These shapes recur.

**Discrimination invariants.** A rule that forces an explicit choice between two states the model would otherwise collapse. Example: distinguishing "we have decided not to act this cycle" from "we are deferring action to a higher-information moment." The invariant names both states and forces an explicit pick. Premise 5 collapses them unless the discrimination is enforced.

**Boundary invariants.** A rule that defines the system's edge. "Outputs are recommendations, not executions." "Publish results only after the side effect has confirmed." These are usually short, often safety-related, and always-on (their whole purpose is bounding what the autonomous system is authorized to do).

**Distance-preservation invariants.** Two roles must stay apart. The rule names the distance and the consequences of collapsing it. These are §4-style isolation rules made specific to a domain.

**Anti-cargo-cult invariants.** A rule that bans the model's default reuse of prior work. These exist because the model treats prior outputs as ground truth rather than as snapshots; the invariant names the asymmetry.

**System-property invariants.** Rules that enforce the pattern's own correctness conditions: commit atomicity, input freshness, schema integrity. Often look like restatements of principle corollaries because they are.

## Anti-patterns

**Speculative invariants.** Rules without an incident, system property, structural reason, or premise-5 anti-shortcut behind them. They feel safe to write and bloat CLAUDE.md against §2.

**Ornamental rules.** "Be careful with X." "Make sure to Y." If the rule does not name what specifically must hold, it does not enforce anything; it just signals attention.

**Rules that restate the principle.** "Verify before trusting" is principle §4, not an invariant. An invariant about verification names *what* must be verified, by *whom*, *when*. The principle is the reason; the invariant is the application.

**Rules without a placement decision.** A rule written into CLAUDE.md "to be safe" when it could live in one stage doc is paying always-on cost for stage-local enforcement. Always answer "where could this be breached?" before placing.

**Multi-surface rules with one surface.** A distance-preservation rule stated only in CLAUDE.md catches orchestrator-driven breaches and misses every direct invocation of the agent. If breach is reachable from three entry surfaces, write three layers.

## A short audit procedure

For an existing CLAUDE.md, walk every numbered rule and answer:

1. Which of the four sources does this rule trace to (incident, system property, structural distance, premise-5 anti-shortcut)?
2. From which entry surfaces is breach reachable?
3. Does the rule appear at every reachable entry surface?
4. Is the rule placed at the highest-frequency surface that catches every breach, and not higher than that? "Not higher" means: if every breach path is reachable from one stage, the rule belongs in that stage's doc, not in CLAUDE.md. If the mandate is always-on but the procedure is stage-specific, are both pieces in their right homes?

A rule that fails (1) is decoration; consider deleting. A rule that fails (3) silently misses breach paths; add the missing surfaces. A rule placed higher than (4) requires is paying §2 cost without justification; push it down.
