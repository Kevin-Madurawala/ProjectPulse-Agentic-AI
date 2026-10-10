# ProjectPulse: engineering methodology

## Project objective
Help a project coordinator assess the consequences of one task disruption, compare user-supplied corrective actions, and identify the lowest-cost feasible plan under a deadline, budget, action-count limit, and conservative resource-capacity rules. All included project data are synthetic.

## Scheduling method

The deterministic Python engine implements the Critical Path Method (CPM) over a directed, acyclic finish-to-start dependency graph. It calculates earliest starts/finishes, latest starts/finishes, slack, critical tasks, and overall project duration. In this demonstration, every task uses a nonnegative integer working-day duration, and days are relative to project start rather than actual calendar dates.

A disruption replaces the **total duration** of one task, rather than adding the value to the existing total. The project schedule is then recomputed.

## Recovery optimization

Candidates in the recovery-options CSV specify an affected task, new total duration, additional cost, and assumption. The Phase 5 engine exhaustively enumerates permitted action sets up to the selected cardinality limit (maximum 3 selected actions and up to 20 candidates). For each set it:

1. Rejects multiple candidate changes to the same task, explicit incompatible actions, and shared-resource reservations exceeding the modeled capacity.
2. Applies allowed task-duration changes on top of the disrupted schedule.
3. Recomputes CPM and total incremental recovery cost.
4. Marks a plan feasible only if it meets the required completion day and budget.
5. Selects the **lowest-cost feasible plan**, using earlier completion as a tie-breaker.

These constraints apply only to **supplied** options and resource pools; the solver does not autonomously invent vendor capabilities or quotations. Whole-plan resource reservation is deliberately conservative and is **not** time-phased resource leveling or a full resource-constrained project scheduling problem (RCPSP).

## Agent integration and human approval

In AI mode, the user writes a natural-language update. The AI model interprets it and may invoke one strict-parameter tool call to the deterministic optimizer. The calculated result remains authoritative; the AI narrative is an explanation, not a replacement for the calculation. The agent cannot purchase equipment, send communications, or change a real project.

The approval control appends **fictional demonstration decisions** to a local log under `outputs/`, which `.gitignore` excludes. Vendors and resource allocations must still be verified by people.

## Validation design

Unit tests cover critical-path arithmetic, bad task networks, resource-capacity conflicts, incompatible actions, and schedule feasibility. The evaluation script compares 12 predefined expected-output cases across equipment installation, warehouse automation, and recycling-line upgrade samples. It also performs 11 matched comparisons (same project disruption, budget, deadline, and candidate actions), varying only whether up to one or two corrective actions are allowed.

In the reference synthetic evaluation:

| Metric | Value | Interpretation |
|---|---:|---|
| Curated golden-case checks | 12/12 | Matching predefined expected solutions, not general accuracy |
| Matched cases feasible with up to 1 action | 6/11 | Under chosen synthetic constraints |
| Matched cases feasible with up to 2 actions | 8/11 | Two additional cases feasible |
| Constraint monotonicity | 11/11 | Allowing more actions did not remove a previously feasible solution |

Optimizer-only timing is measured using repeated warmed calls; it excludes Streamlit rendering, network latency, language-model time, and human review. Reproduction across machines can produce different runtimes.

## Limitations

- Synthetic data and estimates only; no verified business savings or improved actual delivery.
- Models one disruption per analysis; no uncertainty or Monte Carlo schedule risk.
- Finish-to-start dependencies and integer relative working days; no business-day calendars, holidays, partial shifts, or shared crew calendars.
- Resource constraints are coarse reservations across the plan, not temporal resource scheduling.
- Exhaustive combination enumeration is deliberately bounded; not designed for enterprise-scale planning without more efficient optimization.
- AI tool interpretation was demonstrated manually, but no independent large-scale language-model accuracy evaluation was conducted.
- Procurement feasibility, quotations, resource allocation, and approvals require humans.