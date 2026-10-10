"""Deterministic CPM scheduling and bounded recovery choice engine.

The output is a recommendation *for approval*, not a real purchase or message.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from pathlib import Path


@dataclass(frozen=True)
class Task:
    task_id: str
    task_name: str
    duration_days: int
    dependencies: tuple[str, ...]
    owner: str = ""
    status: str = ""


@dataclass(frozen=True)
class Option:
    option_id: str
    option_name: str
    task_id: str
    new_duration_days: int
    additional_cost_usd: float
    assumption: str = ""


def load_tasks(path: str | Path) -> list[Task]:
    with open(path, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    tasks = [
        Task(
            task_id=r["task_id"].strip(),
            task_name=r["task_name"].strip(),
            duration_days=int(r["duration_days"]),
            dependencies=tuple(d.strip() for d in r["dependencies"].split(";") if d.strip()),
            owner=r.get("owner", "").strip(),
            status=r.get("status", "").strip(),
        )
        for r in rows
    ]
    if not tasks:
        raise ValueError("The task file contains no tasks")
    return tasks


def load_options(path: str | Path) -> list[Option]:
    with open(path, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        Option(
            option_id=r["option_id"].strip(),
            option_name=r["option_name"].strip(),
            task_id=r["task_id"].strip(),
            new_duration_days=int(r["new_duration_days"]),
            additional_cost_usd=float(r["additional_cost_usd"]),
            assumption=r.get("assumption", "").strip(),
        )
        for r in rows
    ]


def schedule(tasks: list[Task]) -> dict:
    """Compute CPM using finish-to-start task dependencies, day 0 origin.

    All task durations are integral working days. Assumes no resource constraints,
    calendars, overlapping task execution, or probabilistic duration estimates.
    """
    lookup = {t.task_id: t for t in tasks}
    if len(lookup) != len(tasks):
        raise ValueError("Duplicate task IDs are not allowed")
    for t in tasks:
        if t.duration_days < 0:
            raise ValueError(f"Negative duration for task {t.task_id}")
        if t.task_id in t.dependencies:
            raise ValueError(f"Task {t.task_id} cannot depend on itself")
        for dep in t.dependencies:
            if dep not in lookup:
                raise ValueError(f"Task {t.task_id} has unknown dependency {dep}")

    # Kahn topological sort: dependencies before successor tasks.
    remaining = {t.task_id: set(t.dependencies) for t in tasks}
    order: list[str] = []
    while remaining:
        ready = sorted(task_id for task_id, deps in remaining.items() if not deps)
        if not ready:
            raise ValueError("Dependency cycle found; cannot schedule project")
        for task_id in ready:
            order.append(task_id)
            del remaining[task_id]
        for deps in remaining.values():
            deps.difference_update(ready)

    es: dict[str, int] = {}
    ef: dict[str, int] = {}
    for task_id in order:
        t = lookup[task_id]
        es[task_id] = max((ef[d] for d in t.dependencies), default=0)
        ef[task_id] = es[task_id] + t.duration_days
    finish = max(ef.values())

    successors: dict[str, list[str]] = {task_id: [] for task_id in order}
    for t in tasks:
        for dep in t.dependencies:
            successors[dep].append(t.task_id)

    ls: dict[str, int] = {}
    lf: dict[str, int] = {}
    for task_id in reversed(order):
        lf[task_id] = min((ls[s] for s in successors[task_id]), default=finish)
        ls[task_id] = lf[task_id] - lookup[task_id].duration_days

    rows = [
        {
            "id": task_id,
            "task": lookup[task_id].task_name,
            "duration": lookup[task_id].duration_days,
            "dependencies": ", ".join(lookup[task_id].dependencies) or "—",
            "earliest_start": es[task_id],
            "earliest_finish": ef[task_id],
            "latest_start": ls[task_id],
            "latest_finish": lf[task_id],
            "slack_days": ls[task_id] - es[task_id],
            "critical": ls[task_id] == es[task_id],
            "owner": lookup[task_id].owner,
            "status": lookup[task_id].status,
        }
        for task_id in order
    ]
    return {
        "project_duration_days": finish,
        "critical_tasks": [r["id"] for r in rows if r["critical"]],
        "tasks": rows,
    }


def apply_duration(tasks: list[Task], task_id: str, days: int) -> list[Task]:
    if days < 0:
        raise ValueError("Duration must be non-negative")
    if task_id not in {t.task_id for t in tasks}:
        raise ValueError(f"Unknown task: {task_id}")
    return [replace(t, duration_days=days) if t.task_id == task_id else t for t in tasks]


def evaluate_recovery(
    original: list[Task], options: list[Option], deadline_days: int,
    max_budget_usd: float,
) -> dict:
    """Rank supplied single-action recovery options by added cost, then finish.

    This model *only* optimizes over supplied alternatives, not every possible plan.
    Supplier availability and feasibility require human verification.
    """
    baseline = schedule(original)
    analyzed = []
    for option in options:
        variant = schedule(apply_duration(original, option.task_id, option.new_duration_days))
        row = {
            "option_id": option.option_id,
            "option_name": option.option_name,
            "cost_usd": option.additional_cost_usd,
            "duration_days": variant["project_duration_days"],
            "days_recovered_vs_no_action": 0,
            "within_budget": option.additional_cost_usd <= max_budget_usd,
            "meets_deadline": variant["project_duration_days"] <= deadline_days,
            "critical_tasks": variant["critical_tasks"],
            "assumption": option.assumption,
        }
        row["feasible"] = row["within_budget"] and row["meets_deadline"]
        analyzed.append(row)

    no_action = next((r["duration_days"] for r in analyzed if r["option_id"] == "NO_ACTION"), None)
    if no_action is not None:
        for row in analyzed:
            row["days_recovered_vs_no_action"] = no_action - row["duration_days"]
    feasible = [r for r in analyzed if r["feasible"]]
    best = min(feasible, key=lambda r: (r["cost_usd"], r["duration_days"], r["option_id"])) if feasible else None
    return {
        "baseline_duration_days": baseline["project_duration_days"],
        "deadline_days": deadline_days,
        "max_budget_usd": max_budget_usd,
        "options": analyzed,
        "recommendation": best,
        "decision_rule": "Minimum cost among options that meet budget and deadline; duration breaks ties.",
        "requires_approval": True,
    }
