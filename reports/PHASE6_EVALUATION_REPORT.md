# ProjectPulse — Phase 6 Evaluation Report

**Generated (UTC):** 2026-10-10T00:53:18+00:00  
**Dataset:** Three fictional engineering project networks, not real operational data.  
**Evaluation scope:** deterministic CPM and recovery optimization only; **not** a test of AI reasoning, end-to-end UI latency, or human decision time.

## Results at a glance

- **Golden scenarios:** 12/12 passed (100.0% of this **curated** set, not a general accuracy estimate).
- **Distinct sample projects:** 3.
- **Matched scenario feasibility (at most one action):** 6/11.
- **Matched scenario feasibility (at most two actions):** 8/11.
- **Additional cases made feasible by allowing two actions:** 2 in this sample.
- **Median optimizer-only compute time:** 0.4911 ms across scenario medians on the evaluation machine; **not** live API latency.
- **Constraint monotonicity checks:** 11/11 passed (a larger action limit did not worsen feasible cost or eliminate an existing feasible plan).

## Golden-case validation

These explicit expected answers are checked against each run. `None` means no feasible recovery is available under modeled constraints. The selected action is optimal *only among supplied options and permitted combinations*.

| Test case | Project | Result | Recommended option IDs | Finish day | Cost (USD) |
|---|---|---|---|---:|---:|
| WH_TWO_REQUIRED | warehouse | PASS | FAST_FREIGHT,OVERTIME | 17 | 375.0 |
| WH_SINGLE_FAIL | warehouse | PASS | None | None | None |
| WH_RELAXED | warehouse | PASS | FAST_FREIGHT | 18 | 250.0 |
| WH_BUDGET_FAIL | warehouse | PASS | None | None | None |
| WH_FASTEST | warehouse | PASS | OVERTIME,EXPRESS | 16 | 675.0 |
| WH_NO_ACTION | warehouse | PASS |  | 20 | 0.0 |
| RE_TWO | recycling | PASS | PRIORITY_PARTS,CALIBRATION_OVERTIME | 22 | 410.0 |
| RE_SINGLE | recycling | PASS | PRIORITY_PARTS | 23 | 280.0 |
| RE_BUDGET_FAIL | recycling | PASS | None | None | None |
| EQ_SINGLE | equipment | PASS | ALTERNATE | 15 | 200.0 |
| EQ_BUDGET_FAIL | equipment | PASS | None | None | None |
| EQ_CHEAPER_COMBO | equipment | PASS | ALTERNATE,REASSIGN | 14 | 325.0 |

## Controlled single-action versus two-action comparison

All rows keep the **same task disruption, deadline, budget and action candidates** and change only the maximum corrective-action count. `None` = no feasible plan. Timing uses warmed Python calls, median of 25 measured iterations; elapsed time will differ by computer.

| Test | Single-action feasible | Two-action feasible | Single cost | Two-action cost | Two-action median (ms) |
|---|---|---|---:|---:|---:|
| WH_TWO_REQUIRED | False | True | None | 375.0 | 0.4911 |
| WH_RELAXED | True | True | 250.0 | 250.0 | 0.4923 |
| WH_BUDGET_FAIL | False | False | None | None | 0.4744 |
| WH_FASTEST | False | True | None | 675.0 | 0.4805 |
| WH_NO_ACTION | True | True | 0.0 | 0.0 | 0.5212 |
| RE_TWO | True | True | 450.0 | 410.0 | 0.6724 |
| RE_SINGLE | True | True | 280.0 | 280.0 | 0.6261 |
| RE_BUDGET_FAIL | False | False | None | None | 0.6156 |
| EQ_SINGLE | True | True | 200.0 | 200.0 | 0.2590 |
| EQ_BUDGET_FAIL | False | False | None | None | 0.2703 |
| EQ_CHEAPER_COMBO | True | True | 450.0 | 325.0 | 0.2625 |

## What can and cannot be claimed

**Supported claims:** The optimizer reproduced the expected solutions in 12 predeclared synthetic cases; multi-action planning made 2 additional test cases feasible; the program enforces its defined budget, incompatibility, and conservative shared resource-capacity rules in the existing automated tests.

**Not supported by this report:** A universal 100% accuracy claim, real cost savings, reductions in project-manager labor, changes in actual on-time delivery, reliability under uncertain supplier lead times, or any AI model's prediction accuracy. These would require additional evidence, real-world ground truth, controlled human comparison, or broader testing.

**Optimization assumptions:** Entire-task integer working days; finish-to-start precedence; one observed disruption per run; additive action costs; at most 20 actions and at most 3 selected; conservative whole-plan resource reservations instead of time-phased resource leveling; no calendar exceptions, probabilistic forecasts, or verified supplier quotes. This is not a full RCPSP solver. Plan execution always requires human and vendor verification.

## Reproduce the report

From the inner ProjectPulse folder, run:

```powershell
python -m unittest discover -s tests -v
python phase6_evaluate.py --repeats 25
python -m streamlit run phase6_dashboard.py
```

Outputs go into `outputs/phase6/`. This report is safe to share because it contains no API keys or confidential company data. Runtime and UTC timestamp can vary between runs.

## Input fingerprints (SHA-256)

| Sample CSV | SHA-256 |
|---|---|
| `equipment_options.csv` | `9bfddae549a7989656090bdf7dafb4e40e92127cc770fdc1fcf9263b409b6fa3` |
| `equipment_tasks.csv` | `3ca35c6599d507ea85245b167130329d5c65d819e9f0df1362006bf014e55225` |
| `recycling_options.csv` | `8239f104fcfd84713702bc3af984a794e2a71a8325a51b3731da793f9aab860b` |
| `recycling_resources.csv` | `216614b0a47a0151cc91744323fd72bddf0e8dc535098321a214767bda219da1` |
| `recycling_tasks.csv` | `2073431341c29e5bcb6f8594fad634ab2c5104124e3e96d7a714930a4028e57c` |
| `warehouse_options.csv` | `3d40e64b3d1d58e1b18ba1dff787d2d686a6809bab7b708d2d16af0cb5826ff9` |
| `warehouse_resources.csv` | `da42739378472298569625ee06e82721f4ff5c3d1a86c8cb02a68d087892d4d9` |
| `warehouse_tasks.csv` | `15d760e88d5d64fc2da42c9eae16ddd71e2deb61c18f55580e62318c7852a56c` |
