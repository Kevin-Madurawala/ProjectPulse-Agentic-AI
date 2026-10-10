"""ProjectPulse Phase 6: reproducible synthetic validation and local runtime evaluation.

Usage (in the inner ProjectPulse-Starter directory):
    python phase6_evaluate.py
    python phase6_evaluate.py --repeats 30

Requires existing phase4_engine.py, phase5_engine.py, src/engine.py,
and phase5_samples/. Uses only the Python standard library for reporting.
No API calls and no purchases, communications, or real-world actions.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from phase4_engine import parse_options, parse_tasks
from phase5_engine import optimize_recovery, parse_action_policies, parse_resource_capacities

ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT / "phase5_samples"
REPORT_DIR = ROOT / "outputs" / "phase6"


@dataclass(frozen=True)
class GoldenCase:
    case_id: str
    project: str
    disrupted_task: str
    duration: int
    deadline: int
    budget: int
    max_actions: int
    expected_ids: tuple[str, ...] | None
    expected_finish: int | None
    expected_cost: int | None
    purpose: str


# Independently specified expected answers for synthetic, documented sample networks.
# None means the engine should correctly return "no feasible plan".
GOLDEN = (
    GoldenCase("WH_TWO_REQUIRED", "warehouse", "W4", 9, 17, 400, 2, ("FAST_FREIGHT", "OVERTIME"), 17, 375, "Two actions required"),
    GoldenCase("WH_SINGLE_FAIL", "warehouse", "W4", 9, 17, 400, 1, None, None, None, "Action-count limit"),
    GoldenCase("WH_RELAXED", "warehouse", "W4", 9, 18, 300, 1, ("FAST_FREIGHT",), 18, 250, "Less restrictive deadline"),
    GoldenCase("WH_BUDGET_FAIL", "warehouse", "W4", 9, 17, 300, 2, None, None, None, "Budget restriction"),
    GoldenCase("WH_FASTEST", "warehouse", "W4", 9, 16, 700, 2, ("OVERTIME", "EXPRESS"), 16, 675, "More expensive deadline"),
    GoldenCase("WH_NO_ACTION", "warehouse", "W4", 9, 20, 0, 2, (), 20, 0, "No action needed"),
    GoldenCase("RE_TWO", "recycling", "R4", 10, 22, 500, 2, ("PRIORITY_PARTS", "CALIBRATION_OVERTIME"), 22, 410, "Recycling combined recovery"),
    GoldenCase("RE_SINGLE", "recycling", "R4", 10, 23, 400, 1, ("PRIORITY_PARTS",), 23, 280, "Recycling single recovery"),
    GoldenCase("RE_BUDGET_FAIL", "recycling", "R4", 10, 21, 100, 2, None, None, None, "Recycling infeasible"),
    GoldenCase("EQ_SINGLE", "equipment", "C", 10, 15, 300, 1, ("ALTERNATE",), 15, 200, "Equipment procurement recovery"),
    GoldenCase("EQ_BUDGET_FAIL", "equipment", "C", 10, 14, 100, 2, None, None, None, "Equipment infeasible"),
    GoldenCase("EQ_CHEAPER_COMBO", "equipment", "C", 10, 14, 500, 2, ("ALTERNATE", "REASSIGN"), 14, 325, "Two actions beat expensive single action"),
)


def load_sample(slug: str):
    """Load validated sample CSVs and return inputs plus SHA-256 file fingerprints."""
    file_names = [f"{slug}_tasks.csv", f"{slug}_options.csv"]
    hashes = {}
    data = {}
    for fname in file_names:
        raw = (SAMPLES / fname).read_bytes()
        hashes[fname] = hashlib.sha256(raw).hexdigest()
        data[fname] = raw
    tasks = parse_tasks(data[file_names[0]])
    actions = parse_options(data[file_names[1]], tasks)
    policies = parse_action_policies(data[file_names[1]], actions)
    resources = SAMPLES / f"{slug}_resources.csv"
    resource_bytes = resources.read_bytes() if resources.exists() else None
    if resource_bytes is not None:
        hashes[resources.name] = hashlib.sha256(resource_bytes).hexdigest()
    caps = parse_resource_capacities(resource_bytes, policies)
    return (tasks, actions, policies, caps), hashes


def evaluate(case: GoldenCase, loaded: dict, max_actions: int | None = None):
    tasks, actions, policies, caps = loaded[case.project]
    return optimize_recovery(
        tasks, actions, case.disrupted_task, case.duration, case.deadline,
        case.budget, policies, caps,
        case.max_actions if max_actions is None else max_actions,
    )


def rec_signature(result: dict):
    rec = result["recommendation"]
    if rec is None:
        return (None, None, None)
    return (tuple(rec["plan_ids"]), rec["finish_day"], rec["cost_usd"])


def timed_call(case: GoldenCase, loaded: dict, max_actions: int, repeats: int) -> tuple[float, float]:
    """Measure optimizer-only wall time (NOT AI or Streamlit response latency)."""
    evaluate(case, loaded, max_actions)  # warm-up outside measurement
    durations_ms = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        evaluate(case, loaded, max_actions)
        durations_ms.append((time.perf_counter_ns() - start) / 1_000_000)
    durations_ms.sort()
    p95_index = min(repeats - 1, math.ceil(0.95 * repeats) - 1)
    return round(statistics.median(durations_ms), 4), round(durations_ms[p95_index], 4)


def write_csv(path: Path, records: list[dict], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def make_report(golden_rows, comparison_rows, summary, hashes) -> str:
    golden_md = "\n".join(
        f"| {r['case_id']} | {r['project']} | {r['result']} | {r['chosen_plan']} | {r['finish_day']} | {r['cost_usd']} |"
        for r in golden_rows
    )
    comparison_md = "\n".join(
        f"| {r['case_id']} | {r['one_action_feasible']} | {r['two_action_feasible']} | {r['one_action_cost']} | {r['two_action_cost']} | {r['two_action_median_ms']:.4f} |"
        for r in comparison_rows
    )
    hashes_md = "\n".join(f"| `{name}` | `{digest}` |" for name, digest in sorted(hashes.items()))
    return f"""# ProjectPulse — Phase 6 Evaluation Report

**Generated (UTC):** {summary['generated_utc']}  
**Dataset:** Three fictional engineering project networks, not real operational data.  
**Evaluation scope:** deterministic CPM and recovery optimization only; **not** a test of AI reasoning, end-to-end UI latency, or human decision time.

## Results at a glance

- **Golden scenarios:** {summary['golden_passed']}/{summary['golden_total']} passed ({summary['golden_pass_percent']:.1f}% of this **curated** set, not a general accuracy estimate).
- **Distinct sample projects:** {summary['project_count']}.
- **Matched scenario feasibility (at most one action):** {summary['matched_one_feasible']}/{summary['matched_total']}.
- **Matched scenario feasibility (at most two actions):** {summary['matched_two_feasible']}/{summary['matched_total']}.
- **Additional cases made feasible by allowing two actions:** {summary['additional_feasible_cases']} in this sample.
- **Median optimizer-only compute time:** {summary['overall_median_two_action_ms']:.4f} ms across scenario medians on the evaluation machine; **not** live API latency.
- **Constraint monotonicity checks:** {summary['monotonicity_passed']}/{summary['matched_total']} passed (a larger action limit did not worsen feasible cost or eliminate an existing feasible plan).

## Golden-case validation

These explicit expected answers are checked against each run. `None` means no feasible recovery is available under modeled constraints. The selected action is optimal *only among supplied options and permitted combinations*.

| Test case | Project | Result | Recommended option IDs | Finish day | Cost (USD) |
|---|---|---|---|---:|---:|
{golden_md}

## Controlled single-action versus two-action comparison

All rows keep the **same task disruption, deadline, budget and action candidates** and change only the maximum corrective-action count. `None` = no feasible plan. Timing uses warmed Python calls, median of {summary['timing_repeats']} measured iterations; elapsed time will differ by computer.

| Test | Single-action feasible | Two-action feasible | Single cost | Two-action cost | Two-action median (ms) |
|---|---|---|---:|---:|---:|
{comparison_md}

## What can and cannot be claimed

**Supported claims:** The optimizer reproduced the expected solutions in {summary['golden_total']} predeclared synthetic cases; multi-action planning made {summary['additional_feasible_cases']} additional test cases feasible; the program enforces its defined budget, incompatibility, and conservative shared resource-capacity rules in the existing automated tests.

**Not supported by this report:** A universal 100% accuracy claim, real cost savings, reductions in project-manager labor, changes in actual on-time delivery, reliability under uncertain supplier lead times, or any AI model's prediction accuracy. These would require additional evidence, real-world ground truth, controlled human comparison, or broader testing.

**Optimization assumptions:** Entire-task integer working days; finish-to-start precedence; one observed disruption per run; additive action costs; at most 20 actions and at most 3 selected; conservative whole-plan resource reservations instead of time-phased resource leveling; no calendar exceptions, probabilistic forecasts, or verified supplier quotes. This is not a full RCPSP solver. Plan execution always requires human and vendor verification.

## Reproduce the report

From the inner ProjectPulse folder, run:

```powershell
python -m unittest discover -s tests -v
python phase6_evaluate.py --repeats {summary['timing_repeats']}
python -m streamlit run phase6_dashboard.py
```

Outputs go into `outputs/phase6/`. This report is safe to share because it contains no API keys or confidential company data. Runtime and UTC timestamp can vary between runs.

## Input fingerprints (SHA-256)

| Sample CSV | SHA-256 |
|---|---|
{hashes_md}
"""


def run(repeats: int = 25, output_dir: Path = REPORT_DIR) -> dict:
    if not isinstance(repeats, int) or not 3 <= repeats <= 200:
        raise ValueError("repeats must be an integer from 3 to 200")
    loaded = {}
    fingerprints = {}
    for slug in sorted({case.project for case in GOLDEN}):
        loaded[slug], hashes = load_sample(slug)
        fingerprints.update(hashes)

    golden_rows = []
    for case in GOLDEN:
        result = evaluate(case, loaded)
        ids, finish, cost = rec_signature(result)
        passed = ids == case.expected_ids and finish == case.expected_finish and cost == case.expected_cost
        golden_rows.append({
            "case_id": case.case_id, "project": case.project, "purpose": case.purpose,
            "result": "PASS" if passed else "FAIL",
            "chosen_plan": ",".join(ids) if ids is not None else "None",
            "finish_day": finish if finish is not None else "None",
            "cost_usd": cost if cost is not None else "None",
            "expected_plan": ",".join(case.expected_ids) if case.expected_ids is not None else "None",
            "baseline_days": result["baseline_finish"], "disrupted_days": result["disrupted_finish"],
            "valid_plans": result["valid_plans_evaluated"],
            "feasible_plans": result["feasible_plans"],
            "excluded_conflicts": sum(result["excluded_combinations"].values()),
        })

    # Each case is one matched comparison; deduplicate repeated identical input constraints
    # if new golden cases later share inputs with a different max_actions bound.
    scenarios = {}
    for case in GOLDEN:
        key = (case.project, case.disrupted_task, case.duration, case.deadline, case.budget)
        scenarios.setdefault(key, case)
    comparison_rows = []
    monotonicity_passed = 0
    for case in scenarios.values():
        one = evaluate(case, loaded, 1)
        two = evaluate(case, loaded, 2)
        one_ids, one_finish, one_cost = rec_signature(one)
        two_ids, two_finish, two_cost = rec_signature(two)
        monotonic = (one_ids is None or (two_ids is not None and two_cost <= one_cost))
        monotonicity_passed += int(monotonic)
        m1, p95_1 = timed_call(case, loaded, 1, repeats)
        m2, p95_2 = timed_call(case, loaded, 2, repeats)
        comparison_rows.append({
            "case_id": case.case_id, "project": case.project, "deadline": case.deadline,
            "budget": case.budget, "one_action_feasible": one_ids is not None,
            "two_action_feasible": two_ids is not None,
            "one_action_plan": ",".join(one_ids) if one_ids is not None else "None",
            "two_action_plan": ",".join(two_ids) if two_ids is not None else "None",
            "one_action_cost": one_cost if one_cost is not None else "None",
            "two_action_cost": two_cost if two_cost is not None else "None",
            "one_action_finish": one_finish if one_finish is not None else "None",
            "two_action_finish": two_finish if two_finish is not None else "None",
            "one_action_median_ms": m1, "two_action_median_ms": m2,
            "one_action_p95_ms": p95_1, "two_action_p95_ms": p95_2,
            "cost_monotonic": monotonic,
        })

    golden_pass = sum(r["result"] == "PASS" for r in golden_rows)
    one_feasible = sum(r["one_action_feasible"] for r in comparison_rows)
    two_feasible = sum(r["two_action_feasible"] for r in comparison_rows)
    added = sum(r["two_action_feasible"] and not r["one_action_feasible"] for r in comparison_rows)
    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python_version": platform.python_version(),
        "project_count": len(loaded),
        "golden_total": len(golden_rows), "golden_passed": golden_pass,
        "golden_pass_percent": 100 * golden_pass / len(golden_rows),
        "matched_total": len(comparison_rows),
        "matched_one_feasible": one_feasible, "matched_two_feasible": two_feasible,
        "additional_feasible_cases": added, "monotonicity_passed": monotonicity_passed,
        "timing_repeats": repeats,
        "overall_median_two_action_ms": round(statistics.median(r["two_action_median_ms"] for r in comparison_rows), 4),
        "evaluation_type": "Synthetic deterministic engine validation; no live AI / UI / human baseline tested",
        "csv_sha256": fingerprints,
        "passed": golden_pass == len(golden_rows) and monotonicity_passed == len(comparison_rows),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "golden_scenarios.csv", golden_rows, list(golden_rows[0]))
    write_csv(output_dir / "action_limit_comparison.csv", comparison_rows, list(comparison_rows[0]))
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output_dir / "PHASE6_EVALUATION_REPORT.md").write_text(
        make_report(golden_rows, comparison_rows, summary, fingerprints), encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate ProjectPulse against documented synthetic scenarios")
    parser.add_argument("--repeats", type=int, default=25, help="Warm benchmark repetitions per case (3–200)")
    args = parser.parse_args()
    result = run(args.repeats)
    print("\nPROJECTPULSE — PHASE 6 REPRODUCIBLE EVALUATION")
    print(f"Golden scenarios: {result['golden_passed']}/{result['golden_total']} passed")
    print(f"Paired feasibility: 1 action = {result['matched_one_feasible']}/{result['matched_total']}; "
          f"2 actions = {result['matched_two_feasible']}/{result['matched_total']}")
    print(f"Additional feasible cases with 2 actions: {result['additional_feasible_cases']}")
    print(f"Monotonicity checks: {result['monotonicity_passed']}/{result['matched_total']}")
    print(f"Optimizer-only median across scenarios: {result['overall_median_two_action_ms']:.4f} ms")
    print(f"Reports written to: {REPORT_DIR}")
    if not result["passed"]:
        raise SystemExit("FAIL: Review scenario results and do not claim validation passed.")