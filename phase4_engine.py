"""ProjectPulse Phase 4: generic, deterministic project recovery engine.

Works with any validated, acyclic task network supplied as CSV data.
All times are relative *working-day durations*, not calendar dates.
Recovery choices are single-action alternatives; no changes are executed.
"""
from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass

from src.engine import Task, apply_duration, schedule

TASK_HEADERS = ("task_id", "task_name", "duration_days", "dependencies", "owner", "status")
OPTION_HEADERS = ("option_id", "option_name", "task_id", "new_duration_days", "additional_cost_usd", "assumption")
MAX_CSV_BYTES = 1_000_000
MAX_TASKS = 200
MAX_OPTIONS = 100
MAX_DAYS = 3650
MAX_BUDGET = 10_000_000


@dataclass(frozen=True)
class RecoveryAction:
    option_id: str
    option_name: str
    task_id: str
    new_duration_days: int
    additional_cost_usd: float
    assumption: str


def _read_rows(data: bytes, required: tuple[str, ...], label: str, limit: int) -> list[dict]:
    if not data:
        raise ValueError(f"{label} CSV is empty")
    if len(data) > MAX_CSV_BYTES:
        raise ValueError(f"{label} CSV must be smaller than 1 MB")
    try:
        content = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} CSV must be UTF-8 encoded") from exc
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        raise ValueError(f"{label} CSV needs a header row")
    cols = [c.strip() if c is not None else None for c in reader.fieldnames]
    if len(cols) != len(set(cols)):
        raise ValueError(f"{label} CSV contains duplicate columns")
    missing = sorted(set(required) - set(cols))
    if missing:
        raise ValueError(f"{label} CSV is missing columns: {', '.join(missing)}")
    reader.fieldnames = cols
    rows = []
    for idx, row in enumerate(reader, start=2):
        if all(v is None or not str(v).strip() for v in row.values()):
            continue
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f"{label} CSV row {idx} has the wrong number of fields")
        if len(rows) >= limit:
            raise ValueError(f"{label} CSV supports at most {limit} rows")
        rows.append({k: v.strip() for k, v in row.items()})
    return rows


def _nonnegative_int(value: str, field: str, row: int) -> int:
    try:
        if not value.isdigit():
            raise ValueError
        n = int(value)
    except ValueError as exc:
        raise ValueError(f"Row {row}: {field} must be a non-negative whole number") from exc
    if n > MAX_DAYS:
        raise ValueError(f"Row {row}: {field} cannot exceed {MAX_DAYS} days")
    return n


def _cost(value: str, row: int) -> float:
    try:
        amount = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Row {row}: additional_cost_usd must be numeric") from exc
    if not math.isfinite(amount) or amount < 0 or amount > MAX_BUDGET:
        raise ValueError(f"Row {row}: additional_cost_usd must be finite and between 0 and {MAX_BUDGET}")
    return round(amount, 2)


def parse_tasks(data: bytes) -> list[Task]:
    rows = _read_rows(data, TASK_HEADERS, "Tasks", MAX_TASKS)
    if not rows:
        raise ValueError("Tasks CSV contains no tasks")
    tasks = []
    for index, row in enumerate(rows, start=2):
        tid, name = row["task_id"], row["task_name"]
        if not tid or not name or len(tid) > 40 or len(name) > 150:
            raise ValueError(f"Row {index}: supply a task_id (max 40) and task_name (max 150)")
        deps = tuple(d.strip() for d in row["dependencies"].split(";") if d.strip())
        if len(deps) != len(set(deps)):
            raise ValueError(f"Row {index}: duplicate dependencies are not allowed")
        tasks.append(Task(tid, name, _nonnegative_int(row["duration_days"], "duration_days", index), deps,
                          row["owner"][:150], row["status"][:100]))
    schedule(tasks)  # validates duplicate IDs, cycles and missing dependencies
    return tasks


def parse_options(data: bytes | None, tasks: list[Task]) -> list[RecoveryAction]:
    if data is None:
        return []
    rows = _read_rows(data, OPTION_HEADERS, "Recovery options", MAX_OPTIONS)
    task_ids = {task.task_id for task in tasks}
    seen: set[str] = set()
    actions = []
    for index, row in enumerate(rows, start=2):
        oid = row["option_id"]
        tid = row["task_id"]
        if not oid or oid.upper() == "NO_ACTION" or oid in seen or len(oid) > 40:
            raise ValueError(f"Row {index}: option_id must be unique, nonempty, <=40 characters and not NO_ACTION")
        seen.add(oid)
        if tid not in task_ids:
            raise ValueError(f"Row {index}: recovery action references unknown task_id {tid!r}")
        name = row["option_name"]
        if not name or len(name) > 150:
            raise ValueError(f"Row {index}: option_name is required (max 150 characters)")
        new_days = _nonnegative_int(row["new_duration_days"], "new_duration_days", index)
        actions.append(RecoveryAction(oid, name, tid, new_days,
                                      _cost(row["additional_cost_usd"], index), row["assumption"][:400]))
    return actions


def assess_project(tasks: list[Task], recovery_options: list[RecoveryAction],
                   disrupted_task_id: str, disrupted_total_days: int,
                   deadline_days: int, recovery_budget_usd: float) -> dict:
    """Evaluate one disruption and zero/one recovery action, using CPM for every variant.

    Minimize incremental cost among feasible options, then project finish time.
    A recovery action changes only its named task's total duration, not the disrupted task automatically.
    """
    if not isinstance(disrupted_total_days, int) or isinstance(disrupted_total_days, bool) or not 0 <= disrupted_total_days <= MAX_DAYS:
        raise ValueError(f"Disrupted total duration must be an integer between 0 and {MAX_DAYS}")
    if not isinstance(deadline_days, int) or isinstance(deadline_days, bool) or not 0 <= deadline_days <= MAX_DAYS:
        raise ValueError(f"Deadline must be a whole number between 0 and {MAX_DAYS}")
    if not isinstance(recovery_budget_usd, (int, float)) or isinstance(recovery_budget_usd, bool) or not math.isfinite(recovery_budget_usd) or not 0 <= recovery_budget_usd <= MAX_BUDGET:
        raise ValueError("Budget must be a non-negative finite amount")
    baseline = schedule(tasks)
    original = {t.task_id: t for t in tasks}
    if disrupted_task_id not in original:
        raise ValueError(f"Unknown disrupted task: {disrupted_task_id}")
    disrupted_tasks = apply_duration(tasks, disrupted_task_id, disrupted_total_days)
    disrupted = schedule(disrupted_tasks)
    disrupted_lookup = {t.task_id: t for t in disrupted_tasks}
    raw_actions: list[RecoveryAction | None] = [None] + list(recovery_options)
    names = {"NO_ACTION"}
    for action in recovery_options:
        if action.option_id in names:
            raise ValueError("Duplicate recovery option ID")
        names.add(action.option_id)
        if action.task_id not in disrupted_lookup:
            raise ValueError(f"Recovery option {action.option_id} has unknown task {action.task_id}")
        if action.new_duration_days > MAX_DAYS or action.new_duration_days < 0:
            raise ValueError("Recovery duration out of bounds")
        if not math.isfinite(action.additional_cost_usd) or not 0 <= action.additional_cost_usd <= MAX_BUDGET:
            raise ValueError("Recovery costs must be finite and non-negative")
    rows = []
    schedules = {}
    for action in raw_actions:
        if action is None:
            s = disrupted
            row = {"option_id": "NO_ACTION", "option_name": "Do nothing", "task_id": disrupted_task_id,
                   "new_duration_days": disrupted_total_days, "cost_usd": 0.0,
                   "assumption": "No corrective action taken"}
        else:
            s = schedule(apply_duration(disrupted_tasks, action.task_id, action.new_duration_days))
            row = {"option_id": action.option_id, "option_name": action.option_name,
                   "task_id": action.task_id, "new_duration_days": action.new_duration_days,
                   "cost_usd": action.additional_cost_usd, "assumption": action.assumption}
        row.update({"finish_day": s["project_duration_days"],
                    "days_recovered": disrupted["project_duration_days"] - s["project_duration_days"],
                    "within_budget": row["cost_usd"] <= recovery_budget_usd,
                    "meets_deadline": s["project_duration_days"] <= deadline_days,
                    "critical_tasks": s["critical_tasks"]})
        row["feasible"] = row["within_budget"] and row["meets_deadline"]
        rows.append(row)
        schedules[row["option_id"]] = s
    feasible = [r for r in rows if r["feasible"]]
    selected = min(feasible, key=lambda r: (r["cost_usd"], r["finish_day"], r["option_id"])) if feasible else None
    return {"baseline": baseline, "disrupted": disrupted,
            "disrupted_task_id": disrupted_task_id, "disrupted_total_days": disrupted_total_days,
            "disruption_delta_days": disrupted_total_days - original[disrupted_task_id].duration_days,
            "deadline_days": deadline_days, "budget_usd": recovery_budget_usd,
            "options": rows, "recommendation": selected,
            "proposed": schedules[selected["option_id"]] if selected else None,
            "decision_rule": "Cheapest supplied single-action option that meets both constraints; earliest finish breaks ties.",
            "limitations": "Relative working days, finish-to-start precedence, no resource leveling or real calendar. Assumes durations and costs supplied by the user. Actions are single-option only; availability and feasibility are not verified."}