import unittest
from pathlib import Path
from src.engine import Task, load_tasks, load_options, apply_duration, schedule, evaluate_recovery

ROOT = Path(__file__).resolve().parents[1]


class TestEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks = load_tasks(ROOT / "data/project_tasks.csv")
        cls.options = load_options(ROOT / "data/recovery_options.csv")

    def test_baseline_duration_and_critical_path(self):
        result = schedule(self.tasks)
        self.assertEqual(result["project_duration_days"], 14)
        self.assertEqual(result["critical_tasks"], ["A", "B", "D", "E", "F"])

    def test_supplier_disruption(self):
        result = schedule(apply_duration(self.tasks, "C", 10))
        self.assertEqual(result["project_duration_days"], 17)
        self.assertEqual(result["critical_tasks"], ["A", "C", "E", "F"])

    def test_recovery_recommendation(self):
        result = evaluate_recovery(self.tasks, self.options, 14, 500)
        self.assertEqual(result["recommendation"]["option_id"], "EXPEDITE")
        self.assertEqual(result["recommendation"]["days_recovered_vs_no_action"], 3)

    def test_insufficient_budget_escalates(self):
        result = evaluate_recovery(self.tasks, self.options, 14, 300)
        self.assertIsNone(result["recommendation"])

    def test_cyclic_dependencies_rejected(self):
        tasks = [Task("A", "A", 1, ("B",)), Task("B", "B", 1, ("A",))]
        with self.assertRaisesRegex(ValueError, "cycle"):
            schedule(tasks)

    def test_unknown_dependency_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown dependency"):
            schedule([Task("A", "A", 1, ("Z",))])


if __name__ == "__main__":
    unittest.main()