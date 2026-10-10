"""ProjectPulse Phase 5: bounded, deterministic multi-action recovery optimization.

Model: one disruption, finish-to-start CPM, at most 3 distinct-task actions,
additive recovery costs and conservatively reserved resource-pool capacities.
No calendar/resource-leveling optimization or real operational actions.
"""
from __future__ import annotations

import csv
import io
import itertools
import math
from dataclasses import dataclass

from phase4_engine import (
    MAX_BUDGET, MAX_DAYS, RecoveryAction, assess_project,
)
from src.engine import Task, apply_duration, schedule

MAX_ACTION_CANDIDATES = 20
MAX_COMBINED_ACTIONS = 3
MAX_POLICY_FILE_BYTES = 1_000_000


@dataclass(frozen=True)
class ActionPolicy:
    resource_id: str = ""
    resource_units: int = 0
    incompatible_with: frozenset[str] = frozenset()


def _rows_from_bytes(data: bytes, required: set[str], label: str) -> list[dict[str, str]]:
    if not data or len(data) > MAX_POLICY_FILE_BYTES:
        raise ValueError(f"{label}: file must be nonempty and <=1 MB")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label}: CSV must be UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError(f"{label}: missing header row")
    fields = [c.strip() for c in reader.fieldnames]
    if len(fields) != len(set(fields)) or not required.issubset(fields):
        raise ValueError(f"{label}: invalid, duplicate, or missing required column headers: {sorted(required)}")
    reader.fieldnames = fields
    result = []
    for i, row in enumerate(reader, start=2):
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f"{label}: malformed row {i}")
        if all(not v.strip() for v in row.values()):
            continue
        result.append({key: val.strip() for key, val in row.items()})
        if len(result) > 100:
            raise ValueError(f"{label}: too many rows")
    return result


def parse_action_policies(options_csv: bytes | None, actions: list[RecoveryAction]) -> dict[str, ActionPolicy]:
    """Read optional Phase 5 columns from a Phase 4-compatible actions CSV.

    resource_id (string), resource_units (positive integer if resource set),
    incompatible_with (semicolon-separated option IDs). Old CSVs still work.
    """
    defaults = {action.option_id: ActionPolicy() for action in actions}
    if options_csv is None or not actions:
        return defaults
    rows = _rows_from_bytes(options_csv, {"option_id"}, "Action policies")
    valid_ids = set(defaults)
    seen: set[str] = set()
    for i, row in enumerate(rows, start=2):
        oid = row["option_id"]
        if oid not in valid_ids or oid in seen:
            raise ValueError(f"Action policies: unknown or duplicate option_id {oid!r} on row {i}")
        seen.add(oid)
        resource = row.get("resource_id", "")
        raw_units = row.get("resource_units", "")
        if len(resource) > 50:
            raise ValueError(f"Action policies: resource_id too long on row {i}")
        if resource:
            if not raw_units.isdigit() or not 1 <= int(raw_units) <= 100:
                raise ValueError(f"Action policies: resource_units must be an integer 1–100 on row {i}")
            units = int(raw_units)
        else:
            if raw_units and raw_units != "0":
                raise ValueError(f"Action policies: resource_units without resource_id on row {i}")
            units = 0
        incompat = [x.strip() for x in row.get("incompatible_with", "").split(";") if x.strip()]
        if len(incompat) != len(set(incompat)) or oid in incompat or any(x not in valid_ids for x in incompat):
            raise ValueError(f"Action policies: invalid incompatible_with on row {i}")
        defaults[oid] = ActionPolicy(resource, units, frozenset(incompat))
    if seen != valid_ids:
        raise ValueError("Action policies: option_id rows do not match the recovery options")
    return defaults


def parse_resource_capacities(capacities_csv: bytes | None, policies: dict[str, ActionPolicy]) -> dict[str, int]:
    groups = {p.resource_id for p in policies.values() if p.resource_id}
    capacities = {rid: 1 for rid in groups}  # conservative default, no file required
    if capacities_csv is None:
        return capacities
    rows = _rows_from_bytes(capacities_csv, {"resource_id", "capacity"}, "Resource capacities")
    seen: set[str] = set()
    for i, row in enumerate(rows, start=2):
        rid, raw = row["resource_id"], row["capacity"]
        if not rid or rid not in groups or rid in seen or not raw.isdigit() or not 1 <= int(raw) <= 100:
            raise ValueError(f"Resource capacities: invalid or duplicate row {i}")
        seen.add(rid)
        capacities[rid] = int(raw)
    return capacities


def _valid_combo(combo: tuple[RecoveryAction, ...], policies: dict[str, ActionPolicy],
                 capacities: dict[str, int]) -> str | None:
    # A total task duration cannot simultaneously take two different values.
    task_ids = [a.task_id for a in combo]
    if len(set(task_ids)) < len(task_ids):
        return "same_task"
    selected_ids = {a.option_id for a in combo}
    for action in combo:
        if policies[action.option_id].incompatible_with & selected_ids:
            return "explicit_exclusion"
    used = {rid: 0 for rid in capacities}
    for action in combo:
        policy = policies[action.option_id]
        if policy.resource_id:
            used[policy.resource_id] += policy.resource_units
            if used[policy.resource_id] > capacities[policy.resource_id]:
                return "resource_capacity"
    return None


def optimize_recovery(tasks: list[Task], actions: list[RecoveryAction], disrupted_task_id: str,
                      disrupted_total_days: int, deadline_days: int, recovery_budget_usd: float,
                      policies: dict[str, ActionPolicy] | None = None,
                      capacities: dict[str, int] | None = None,
                      max_actions: int = 2) -> dict:
    """Exhaustively choose cheapest feasible subset, within the explicit action-count cap.

    Capacity is a conservative reservation *per selected action*, not dynamic
    time-phased crew allocation. Options with the same task_id cannot combine.
    """
    if not isinstance(max_actions, int) or isinstance(max_actions, bool) or not 1 <= max_actions <= MAX_COMBINED_ACTIONS:
        raise ValueError("max_actions must be an integer from 1 to 3")
    if len(actions) > MAX_ACTION_CANDIDATES:
        raise ValueError(f"Phase 5 supports at most {MAX_ACTION_CANDIDATES} recovery options to bound the search")
    # Reuse Phase 4's validated baseline/disruption/constraints.
    phase4 = assess_project(tasks, actions, disrupted_task_id, disrupted_total_days,
                            deadline_days, recovery_budget_usd)
    ids = [a.option_id for a in actions]
    if len(ids) != len(set(ids)):
        raise ValueError("Recovery actions must have unique IDs")
    policies = policies if policies is not None else {id_: ActionPolicy() for id_ in ids}
    if set(policies) != set(ids):
        raise ValueError("Action policy IDs must match recovery action IDs")
    for p in policies.values():
        if p.resource_id and (not isinstance(p.resource_units, int) or p.resource_units <= 0):
            raise ValueError("Resource assignment needs a positive integer unit count")
        if any(x not in ids for x in p.incompatible_with):
            raise ValueError("Unknown exclusion action ID")
    capacities = capacities if capacities is not None else {p.resource_id: 1 for p in policies.values() if p.resource_id}
    required = {p.resource_id for p in policies.values() if p.resource_id}
    if set(capacities) != required or any(type(value) is not int or value <= 0 for value in capacities.values()):
        raise ValueError("Resource capacities must match the assigned resource groups and be positive integers")
    for a in actions:
        p = policies[a.option_id]
        if p.resource_id and p.resource_units > capacities[p.resource_id]:
            # Valid action but its entire resource claim is impossible: leave as excluded plan.
            pass
    disrupted_tasks = apply_duration(tasks, disrupted_task_id, disrupted_total_days)
    baseline_finish = phase4["baseline"]["project_duration_days"]
    disrupted_finish = phase4["disrupted"]["project_duration_days"]
    all_rows: list[dict] = []
    variants: dict[tuple[str, ...], dict] = {}
    skipped = {"same_task": 0, "resource_capacity": 0, "explicit_exclusion": 0}
    for n in range(0, min(max_actions, len(actions)) + 1):
        for combo in itertools.combinations(actions, n):
            problem = _valid_combo(combo, policies, capacities)
            if problem:
                skipped[problem] += 1
                continue
            variant = disrupted_tasks
            for action in combo:
                variant = apply_duration(variant, action.task_id, action.new_duration_days)
            sched = schedule(variant)
            cents = sum(round(a.additional_cost_usd * 100) for a in combo)
            cost = cents / 100.0
            finish = sched["project_duration_days"]
            row = {
                "plan_ids": tuple(a.option_id for a in combo),
                "plan_name": " + ".join(a.option_name for a in combo) if combo else "No action",
                "action_count": len(combo),
                "cost_usd": cost,
                "finish_day": finish,
                "days_recovered": disrupted_finish - finish,
                "meets_deadline": finish <= deadline_days,
                "within_budget": cents <= round(recovery_budget_usd * 100),
                "critical_tasks": sched["critical_tasks"],
                "assumptions": [a.assumption for a in combo if a.assumption],
                "resources_reserved": {rid: sum(policies[a.option_id].resource_units for a in combo if policies[a.option_id].resource_id == rid)
                                       for rid in capacities if any(policies[a.option_id].resource_id == rid for a in combo)},
            }
            row["feasible"] = row["meets_deadline"] and row["within_budget"]
            all_rows.append(row)
            variants[row["plan_ids"]] = sched
    feasible = [r for r in all_rows if r["feasible"]]
    best = min(feasible, key=lambda r: (r["cost_usd"], r["finish_day"], r["action_count"], r["plan_ids"])) if feasible else None
    all_rows.sort(key=lambda r: (not r["feasible"], r["cost_usd"], r["finish_day"], r["action_count"], r["plan_ids"]))
    return {
        "baseline": phase4["baseline"],
        "disrupted": phase4["disrupted"],
        "proposed": variants[best["plan_ids"]] if best else None,
        "baseline_finish": baseline_finish,
        "disrupted_finish": disrupted_finish,
        "disrupted_task_id": disrupted_task_id,
        "disrupted_total_days": disrupted_total_days,
        "deadline_days": deadline_days,
        "budget_usd": recovery_budget_usd,
        "max_actions": max_actions,
        "plans": all_rows,
        "recommendation": best,
        "valid_plans_evaluated": len(all_rows),
        "feasible_plans": len(feasible),
        "excluded_combinations": skipped,
        "decision_rule": f"Exhaustive cheapest feasible combination with at most {max_actions} actions; earlier finish breaks ties.",
        "limitations": "One disruption; whole working days; finish-to-start CPM. Resource units are conservatively reserved for the entire plan, not allocated over time; no calendars, stochastic risks or real resource leveling. Actions on the same task or expressly conflicting actions cannot combine. Only supplied and verified-in-principle recovery candidates, at most 20 options / 3 actions. Costs are additive; vendor quotes and feasibility require confirmation. No real-world actions executed.",
    }