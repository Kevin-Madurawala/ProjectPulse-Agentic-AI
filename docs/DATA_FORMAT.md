# Uploading your own data

The upload interface in `app.py` reads CSV files as UTF-8. The included `phase5_samples/` files provide known-good examples. The fields below show the expected schema.

## Tasks (required)

`task_id,task_name,duration_days,dependencies,owner,status`

- Each `task_id` is unique.
- `duration_days` is the **total** planned task duration in whole working days.
- `dependencies` contains predecessor IDs separated by semicolons (leave blank for no predecessors).
- Finish-to-start dependencies must form an acyclic directed graph.

## Recovery options (optional)

`option_id,option_name,task_id,new_duration_days,additional_cost_usd,assumption,resource_id,resource_units,incompatible_with`

The last three fields are optional, retaining backwards compatibility with the Phase 4 format. Multiple incompatible option IDs can be separated by semicolons. Candidate actions describe new total task durations, not time savings. Treat costs and durations as assumptions pending external validation.

## Resource capacities (optional)

`resource_id,capacity`

If a capacity file is omitted, each named resource pool defaults to a conservative capacity of 1. These are entire-plan reservations—not a scheduling calendar.

## Reproducing one analysis

1. Run `python -m streamlit run app.py`.
2. Select **Upload my own CSV** and upload the files.
3. Select **Manual** and choose the affected task, new **total** duration, deadline, budget, and maximum actions.
4. Click Optimize and review the Gantt schedules, rejected combinations, and assumptions.
5. Optionally create a local **demo approval record**; do not interpret it as supplier confirmation or an authorization to spend.
