# ProjectPulse — portfolio case study

**Type:** Self-directed Industrial Engineering / Project Management / AI engineering portfolio project  
**Dataset:** Fictional equipment installation, warehouse automation, and recycling-line upgrade task networks  
**Status:** Functional local prototype with deterministic optimization, optional AI interpretation, and an evaluation report

## The problem

Project coordinators often need to respond to delivery delays with incomplete information and limited recovery budgets. A schedule delay does not necessarily equal a project delay, since some activities have slack, and the cheapest feasible recovery can require multiple changes across dependent activities.

## My approach

I structured the solution as a project-control workflow: capture a change -> validate task dependencies -> compute CPM -> generate permitted corrective-action combinations -> enforce budget and resource constraints -> compare outcomes -> submit a proposal for human review. I separated deterministic calculations from AI-generated explanations so the model cannot override the scheduling arithmetic.

## Demonstration result

In the warehouse automation test case, a simulated shelving delay moved project completion from day 17 to day 20. Neither priority freight alone (day 18, $250) nor installation overtime alone (day 19, $125) met the day-17 deadline. Combining both met day 17 for $375 within the $400 test budget. The optimizer excludes conflicting interventions and enforces its defined shared-resource reservations.

## Evaluation

The deterministic engine reproduced the expected outcome in all 12 curated fictional scenarios. In 11 paired comparisons, increasing the maximum selected actions from one to two increased feasible cases from 6 to 8. Results demonstrate correctness **within the test set**, not general AI accuracy or realized industry cost savings.

## Skills demonstrated

Industrial Engineering: CPM, critical path, slack, feasibility, cost-constrained decision-making, scenario analysis.  
Software: Python, CSV validation, automated testing, Streamlit, API function calling, structured results, local audit records.  
Project Management: exception handling, assumptions register, human approval gates, stakeholder-ready outputs.

## Resume-ready bullets (only use after personally reviewing the work)

- Developed **ProjectPulse**, a Python/Streamlit project-recovery prototype combining critical-path scheduling, AI-assisted project updates, and budget-constrained corrective-action optimization across three synthetic engineering projects.
- Implemented a multi-action recovery optimizer with dependency, resource-capacity, and compatibility checks; validated **12/12 predefined scenarios** and increased feasibility from **6 to 8 of 11** matched synthetic cases when allowing two actions.

## Caveats

All included operational scenarios are synthetic. No claims of actual employer impact, supplier communication, real approval, or reduced project-manager labor are made.
