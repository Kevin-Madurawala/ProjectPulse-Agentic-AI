"""Run from your existing ProjectPulse project: python -m unittest discover -s tests -v"""
import unittest
from pathlib import Path

from phase4_engine import assess_project, parse_options, parse_tasks

DATA = Path(__file__).resolve().parents[1] / "sample_projects"


def load(slug):
    tasks = parse_tasks((DATA / f"{slug}_tasks.csv").read_bytes())
    opts = parse_options((DATA / f"{slug}_options.csv").read_bytes(), tasks)
    return tasks, opts


class TestPhase4(unittest.TestCase):
    def test_equipment_baseline_and_recovery(self):
        tasks, opts = load("equipment")
        result = assess_project(tasks, opts, "C", 10, 15, 300)
        self.assertEqual(result["baseline"]["project_duration_days"], 14)
        self.assertEqual(result["disrupted"]["project_duration_days"], 17)
        self.assertEqual(result["recommendation"]["option_id"], "ALTERNATE")
        self.assertEqual(result["recommendation"]["finish_day"], 15)
        self.assertEqual(result["recommendation"]["days_recovered"], 2)
        self.assertEqual(result["proposed"]["critical_tasks"], ["A", "C", "E", "F"])

    def test_warehouse_sample(self):
        tasks, opts = load("warehouse")
        result = assess_project(tasks, opts, "W4", 9, 18, 300)
        self.assertEqual(result["baseline"]["project_duration_days"], 17)
        self.assertEqual(result["disrupted"]["project_duration_days"], 20)
        self.assertEqual(result["recommendation"]["option_id"], "FAST_FREIGHT")
        self.assertEqual(result["recommendation"]["finish_day"], 18)

    def test_no_feasible_option(self):
        tasks, opts = load("equipment")
        result = assess_project(tasks, opts, "C", 10, 14, 100)
        self.assertIsNone(result["recommendation"])
        self.assertIsNone(result["proposed"])

    def test_no_action_when_deadline_achievable(self):
        tasks, opts = load("equipment")
        result = assess_project(tasks, opts, "C", 10, 20, 1000)
        self.assertEqual(result["recommendation"]["option_id"], "NO_ACTION")

    def test_arbitrary_task_can_be_disrupted(self):
        tasks, opts = load("warehouse")
        result = assess_project(tasks, opts, "W2", 12, 22, 300)
        self.assertEqual(result["disrupted_total_days"], 12)
        self.assertGreater(result["disrupted"]["project_duration_days"], result["baseline"]["project_duration_days"])

    def test_option_can_shortcut_another_task(self):
        tasks, opts = load("equipment")
        result = assess_project(tasks, opts, "C", 10, 16, 130)
        self.assertEqual(result["recommendation"]["option_id"], "REASSIGN")
        self.assertEqual(result["recommendation"]["finish_day"], 16)

    def test_cyclic_network_rejected(self):
        bad = ("task_id,task_name,duration_days,dependencies,owner,status\n"
               "A,One,2,B,,\nB,Two,2,A,,\n").encode()
        with self.assertRaisesRegex(ValueError, "cycle"):
            parse_tasks(bad)

    def test_unknown_dependency_rejected(self):
        bad = ("task_id,task_name,duration_days,dependencies,owner,status\n"
               "A,One,2,X,,\n").encode()
        with self.assertRaisesRegex(ValueError, "unknown dependency"):
            parse_tasks(bad)

    def test_duplicate_ids_rejected(self):
        bad = ("task_id,task_name,duration_days,dependencies,owner,status\n"
               "A,One,2,,,\nA,Two,1,,,\n").encode()
        with self.assertRaisesRegex(ValueError, "Duplicate task"):
            parse_tasks(bad)

    def test_negative_and_nonfinite_values_rejected(self):
        tasks, _ = load("equipment")
        for bad_duration in ("-1", "1.5", "nan"):
            bad = ("task_id,task_name,duration_days,dependencies,owner,status\n"
                   f"A,One,{bad_duration},,,\n").encode()
            with self.assertRaises(ValueError):
                parse_tasks(bad)
        option_data = ("option_id,option_name,task_id,new_duration_days,additional_cost_usd,assumption\n"
                       "X,Option,C,3,NaN,\n").encode()
        with self.assertRaises(ValueError):
            parse_options(option_data, tasks)

    def test_wrong_option_task_and_duplicate_option_rejected(self):
        tasks, _ = load("equipment")
        bad = ("option_id,option_name,task_id,new_duration_days,additional_cost_usd,assumption\n"
               "X,Option,INVALID,3,10,\n").encode()
        with self.assertRaisesRegex(ValueError, "unknown task"):
            parse_options(bad, tasks)
        bad2 = ("option_id,option_name,task_id,new_duration_days,additional_cost_usd,assumption\n"
                "X,Option,C,3,10,\nX,Second,C,3,20,\n").encode()
        with self.assertRaisesRegex(ValueError, "option_id"):
            parse_options(bad2, tasks)

    def test_missing_option_file_is_allowed(self):
        tasks, _ = load("warehouse")
        self.assertEqual(parse_options(None, tasks), [])
        result = assess_project(tasks, [], "W4", 9, 18, 300)
        self.assertIsNone(result["recommendation"])


if __name__ == "__main__":
    unittest.main()