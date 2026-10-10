"""Read-only Streamlit view of locally generated Phase 6 evaluation metrics.

Start: python -m streamlit run evaluation_dashboard.py
Generate first: python phase6_evaluate.py
"""
from __future__ import annotations

import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

OUT = Path(__file__).resolve().parent / "outputs" / "phase6"
st.set_page_config(page_title="ProjectPulse | Evaluation", layout="wide")
st.title("ProjectPulse · Phase 6 Evaluation")
st.caption("Reproducible validation of synthetic project scheduling and recovery scenarios")
st.info("These are offline Python-engine tests. They do NOT measure AI prediction accuracy, real-world schedule savings, or human coordinator productivity.")
if not (OUT / "summary.json").exists():
    st.warning("No evaluation report found yet. In VS Code, run: python phase6_evaluate.py")
    st.stop()

summary = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
golden = pd.read_csv(OUT / "golden_scenarios.csv", keep_default_na=False)
comparison = pd.read_csv(OUT / "action_limit_comparison.csv", keep_default_na=False)

cols = st.columns(4)
cols[0].metric("Golden cases passed", f"{summary['golden_passed']}/{summary['golden_total']}")
cols[1].metric("Feasible with one action", f"{summary['matched_one_feasible']}/{summary['matched_total']}")
cols[2].metric("Feasible with two actions", f"{summary['matched_two_feasible']}/{summary['matched_total']}")
cols[3].metric("Newly feasible test cases", summary["additional_feasible_cases"])

st.subheader("Golden-case validation")
st.dataframe(golden[["case_id", "project", "purpose", "result", "chosen_plan", "finish_day", "cost_usd"]],
             use_container_width=True, hide_index=True)

st.subheader("Controlled action-limit comparison")
st.caption("Identical disruptions, deadlines, budgets and candidate actions. Only maximum actions changes from 1 to 2.")
view = comparison[["case_id", "one_action_feasible", "two_action_feasible", "one_action_cost", "two_action_cost",
                   "one_action_median_ms", "two_action_median_ms"]].copy()
st.dataframe(view, use_container_width=True, hide_index=True)

st.subheader("Feasibility across matched scenarios")
# Use an explicit zero baseline: auto-scaled bars can visually hide the 6-to-8 difference.
matched_total = int(summary["matched_total"])
feasibility_frame = pd.DataFrame({
    "strategy": ["Up to 1 action", "Up to 2 actions"],
    "feasible": [int(summary["matched_one_feasible"]), int(summary["matched_two_feasible"])],
})
feasibility_frame["display"] = feasibility_frame["feasible"].astype(str) + f" of {matched_total}"
chart_base = alt.Chart(feasibility_frame).encode(
    x=alt.X("strategy:N", title=None, sort=["Up to 1 action", "Up to 2 actions"],
            axis=alt.Axis(labelAngle=0)),
    y=alt.Y("feasible:Q", title="Feasible scenarios",
            scale=alt.Scale(domain=[0, max(matched_total + 1, 10)])),
    tooltip=[alt.Tooltip("strategy:N", title="Maximum actions"),
             alt.Tooltip("display:N", title="Feasible cases")],
)
bars = chart_base.mark_bar(size=125, color="#78b5ed", cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
counts = chart_base.mark_text(dy=-11, fontSize=14).encode(text="display:N")
st.altair_chart((bars + counts).properties(height=330), use_container_width=True)
st.caption(f"Fixed scenario set: {matched_total} matched synthetic cases. Axes start at zero.")

with st.expander("Timing methodology, checks, and limitations"):
    st.write("Compute times use warmed, repeated calls to Python's deterministic optimizer. API requests, UI updates, parsing and user interactions are not timed.")
    st.write(f"{summary['timing_repeats']} measured repetitions per scenario; median of two-action scenario medians: "
             f"{summary['overall_median_two_action_ms']:.4f} ms on the evaluation machine.")
    st.write(f"Monotonicity checks: {summary['monotonicity_passed']}/{summary['matched_total']}.")
    st.write("Constraints use whole-plan resource reservations, not actual time-phased crew scheduling; recovery prices and durations are fictional assumptions.")
    st.write(f"Generated at {summary['generated_utc']} UTC with Python {summary['python_version']}.")

st.download_button("Download evaluation report (Markdown)",
                   data=(OUT / "PHASE6_EVALUATION_REPORT.md").read_text(encoding="utf-8"),
                   file_name="PHASE6_EVALUATION_REPORT.md", mime="text/markdown")
st.download_button("Download golden cases (CSV)", data=(OUT / "golden_scenarios.csv").read_bytes(),
                   file_name="golden_scenarios.csv", mime="text/csv")
