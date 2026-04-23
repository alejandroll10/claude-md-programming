# Invariants: identifying, placing, restating

Half the actual work in a real pipeline is invariants: the numbered rules in CLAUDE.md, the framing reminders in agent definitions, the "never do X" lines in stage docs. Real CLAUDE.mds carry 15-20 of them. The principles say invariants exist (§3 delegation corollary) but not how to find them, where to put them, or when to restate them.

## What counts as an invariant

A rule that must hold across more than one moment in the pipeline. "Cite the source" is an invariant if every stage that produces a claim must cite. "Today's news scan should mention earnings" is not, it is a one-time instruction. The test: would breaking this rule corrupt downstream work even if no one noticed at the time? If yes, it is an invariant. If breakage would be visible immediately, it is just an instruction.

## Where invariants come from

Three honest sources, in order of how reliable they are:

1. **Incidents.** Something broke, you traced it, you wrote a rule. token5's "no unproved mathematical claims" rule names the incident: "v1 runs showed 3/3 post-pipeline audits failed." Rules with an incident attached are load-bearing by construction. Rules without one are speculative.

2. **Structural distance preservation.** Some invariants exist because two roles must stay apart. autopilot's "macro forecasts are universe-neutral" rule keeps forecasters from seeing portfolio holdings; the rule exists because once forecasters know the holdings, scoring is corrupted. The breach is silent. These rules derive from premise 1 (self-bias) and premise 5 (path-of-least-resistance) acting across roles.

3. **Premise-5 anti-shortcuts.** When the model would default to a cheap path that satisfies the letter of the work but misses the intent, the invariant names the shortcut and bans it. autopilot's "prior analyses are references, not destinations" rule exists because the model defaults to resuming yesterday's plan. The rule is not about prior analyses; it is about the shortcut.

If you cannot trace a candidate invariant to one of these three, it is probably ornament.

## Where invariants live

The placement decision is the §3 delegation corollary made operational. Three placements, picked by *scope of breach*:

| Placement | Scope of breach | Cost |
|---|---|---|
| CLAUDE.md (always-on) | Every transition can breach it | Highest token cost; pays §2 |
| Stage doc | Only this stage's body can breach it | Loaded on demand |
| Agent or skill definition | Only when this capability runs | Loaded only when dispatched |

The test: identify every surface from which the rule can be breached, then place it at the highest-frequency surface that catches every breach. A rule about output formatting that only applies in stage X belongs in stage X's doc, not CLAUDE.md. A rule about commit atomicity that applies after every transition belongs in CLAUDE.md.

This is also the test for "does this invariant earn always-on placement?": if there exists a stage that can breach it, CLAUDE.md is the right home, even at §2 cost. If breach is only reachable from one stage, push it down.

## Multi-surface restatement

Some rules are reachable from more than one surface. The §3 delegation corollary says: restate at each surface the rule can enter from. Operationally:

- **Same rule, three layers.** autopilot's rule 12 (universe-neutral forecasts) names three enforcement layers: (a) the forecaster agent definition, (b) the forecast-verifier agent, (c) the CLAUDE.md rule itself. The rule states "preserve all three layers through future edits." When you write a multi-surface invariant, name its enforcement layers in the rule body, so future edits do not silently delete one.

- **Why three not one.** A single statement in CLAUDE.md catches biased orchestrator dispatch but not direct invocation of the agent. A statement in only the agent catches direct invocation but not orchestrator-level violations. The redundancy is not duplication; each layer catches a different breach path.

- **The bar for restatement.** Most invariants do not clear it. Restate only when the breach would be silent, cascading, and reachable from more than one surface. A rule visible only in one place stays in one place.

## Patterns worth recognizing

These shapes recur across real pipelines.

**Discrimination invariants.** A rule that forces an explicit choice between two states the model would otherwise collapse. autopilot's rule 18 (deferred-decision distinct from no-trade) exists because the model treats "we will revisit this" the same as "we have decided not to act." The invariant names both states and forces an explicit pick. Premise 5 collapses unless the discrimination is enforced.

**Boundary invariants.** A rule that defines the system's edge. autopilot's rule 7 (recommendations not executions) and "trades are announced after fills, not before" both define what the autonomous system is and is not authorized to do. These are usually short, often safety-related, and almost always always-on.

**Distance-preservation invariants.** Two roles must stay apart (rule 12, rule 13 in autopilot). The rule names the distance and the consequences of collapsing it. These are the §4-style isolation rules made specific to a domain.

**Anti-cargo-cult invariants.** A rule that bans the model's default reuse of prior work (rule 16 in autopilot). These exist because the model treats prior outputs as ground truth rather than as snapshots; the invariant names the asymmetry.

## Anti-patterns

**Speculative invariants.** Rules without an incident, structural reason, or premise-5 anti-shortcut behind them. They feel safe to write and bloat CLAUDE.md against §2.

**Ornamental rules.** "Be careful with X." "Make sure to Y." If the rule does not name what specifically must hold, it does not enforce anything; it just signals attention.

**Rules that restate the principle.** "Verify before trusting" is principle §4, not an invariant. An invariant about verification names *what* must be verified, by *whom*, *when*. The principle is the reason; the invariant is the application.

**Rules without a placement decision.** A rule written into CLAUDE.md "to be safe" when it could live in one stage doc is paying always-on cost for stage-local enforcement. Always answer "where could this be breached?" before placing.

**Multi-surface rules with one surface.** A distance-preservation rule stated only in CLAUDE.md is a rule that catches orchestrator-driven breaches and misses every direct invocation of the agent. If the rule needs three layers, write three layers.

## A short audit procedure

For an existing CLAUDE.md, walk every numbered rule and answer:

1. What incident, structural reason, or anti-shortcut does this rule trace to?
2. From which surfaces is breach reachable?
3. Does the rule appear at every reachable surface?
4. Is the rule placed at the highest-frequency surface that catches every breach, no higher?

A rule that fails (1) is decoration; consider deleting. A rule that fails (3) silently misses breach paths; add the missing surfaces. A rule placed higher than (4) requires is paying §2 cost without justification; push it down.
