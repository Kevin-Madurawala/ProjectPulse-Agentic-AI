"""Phase 5 regression tests: python -m unittest discover -s tests -v"""
import unittest
from pathlib import Path

from phase4_engine import parse_options, parse_tasks
from phase5_engine import (
    ActionPolicy, optimize_recovery, parse_action_policies, parse_resource_capacities,
)

SAMPLES = Path(__file__).resolve().parents[1] / "phase5_samples"


def load(slug):
    tasks_csv = (SAMPLES / f"{slug}_tasks.csv").read_bytes()
    options_csv = (SAMPLES / f"{slug}_options.csv").read_bytes()
    resources_path = SAMPLES / f"{slug}_resources.csv"
    tasks = parse_tasks(tasks_csv)
    actions = parse_options(options_csv, tasks)
    policies = parse_action_policies(options_csv, actions)
    capacities = parse_resource_capacities(resources_path.read_bytes() if resources_path.exists() else None, policies)
    return tasks, actions, policies, capacities


class TestPhase5(unittest.TestCase):
    def test_two_actions_recover_warehouse(self):
        tasks, actions, policies, caps = load("warehouse")
        r = optimize_recovery(tasks, actions, "W4", 9, 17, 400, policies, caps, 2)
        self.assertEqual((r["baseline_finish"], r["disrupted_finish"]), (17, 20))
        self.assertEqual(r["recommendation"]["plan_ids"], ("FAST_FREIGHT", "OVERTIME"))
        self.assertEqual(r["recommendation"]["cost_usd"], 375)
        self.assertEqual(r["recommendation"]["finish_day"], 17)
        self.assertEqual(r["recommendation"]["days_recovered"], 3)

    def test_one_action_is_not_enough_for_warehouse(self):
        tasks, actions, policies, caps = load("warehouse")
        r = optimize_recovery(tasks, actions, "W4", 9, 17, 400, policies, caps, 1)
        self.assertIsNone(r["recommendation"])

    def test_warehouse_deadline_relaxed_selects_cheapest(self):
        tasks, actions, policies, caps = load("warehouse")
        r = optimize_recovery(tasks, actions, "W4", 9, 18, 400, policies, caps, 2)
        self.assertEqual(r["recommendation"]["plan_ids"], ("FAST_FREIGHT",))

    def test_recycling_two_action_plan(self):
        tasks, actions, policies, caps = load("recycling")
        r = optimize_recovery(tasks, actions, "R4", 10, 22, 500, policies, caps, 2)
        self.assertEqual((r["baseline_finish"], r["disrupted_finish"]), (21, 25))
        self.assertEqual(r["recommendation"]["plan_ids"], ("PRIORITY_PARTS", "CALIBRATION_OVERTIME"))
        self.assertEqual(r["recommendation"]["cost_usd"], 410)
        self.assertEqual(r["recommendation"]["finish_day"], 22)

    def test_phase4_csv_without_resource_columns_still_supported(self):
        tasks, actions, policies, caps = load("equipment")
        self.assertFalse(caps)
        r = optimize_recovery(tasks, actions, "C", 10, 15, 300, policies, caps, 2)
        self.assertEqual(r["recommendation"]["plan_ids"], ("ALTERNATE",))

    def test_reserve_crew_capacity_excludes_double_booking(self):
        tasks, actions, policies, caps = load("warehouse")
        r = optimize_recovery(tasks, actions, "W4", 9, 17, 400, policies, caps, 2)
        ids = [set(row["plan_ids"]) for row in r["plans"]]
        self.assertNotIn({"OVERTIME", "PREP_CREW"}, ids)
        self.assertGreater(r["excluded_combinations"]["resource_capacity"], 0)

    def test_double_action_same_task_excluded(self):
        tasks, actions, policies, caps = load("warehouse")
        r = optimize_recovery(tasks, actions, "W4", 9, 17, 1000, policies, caps, 2)
        ids = [set(row["plan_ids"]) for row in r["plans"]]
        self.assertNotIn({"FAST_FREIGHT", "EXPRESS"}, ids)
        self.assertGreater(r["excluded_combinations"]["same_task"], 0)

    def test_no_action_is_cheapest_when_deadline_already_met(self):
        tasks, actions, policies, caps = load("warehouse")
        r = optimize_recovery(tasks, actions, "W4", 9, 21, 400, policies, caps, 2)
        self.assertEqual(r["recommendation"]["plan_ids"], ())
        self.assertEqual(r["recommendation"]["cost_usd"], 0)

    def test_insufficient_budget_returns_none(self):
        tasks, actions, policies, caps = load("warehouse")
        r = optimize_recovery(tasks, actions, "W4", 9, 17, 100, policies, caps, 2)
        self.assertIsNone(r["recommendation"])

    def test_explicit_exclusions_across_separate_tasks(self):
        tasks, actions, policies, caps = load("warehouse")
        policies = dict(policies)
        policies["FAST_FREIGHT"] = ActionPolicy("freight", 1, frozenset({"OVERTIME"}))
        r = optimize_recovery(tasks, actions, "W4", 9, 17, 400, policies, caps, 2)
        self.assertIsNone(r["recommendation"])
        self.assertGreater(r["excluded_combinations"]["explicit_exclusion"], 0)

    def test_capacity_two_allows_both_crew_actions(self):
        tasks, actions, policies, caps = load("warehouse")
        caps = {**caps, "crew": 2}
        r = optimize_recovery(tasks, actions, "W4", 9, 17, 600, policies, caps, 3)
        self.assertIn({"OVERTIME", "PREP_CREW"}, [set(row["plan_ids"]) for row in r["plans"]])

    def test_duplicate_or_invalid_capacity_rejected(self):
        _, _, policies, _ = load("warehouse")
        with self.assertRaises(ValueError):
            parse_resource_capacities(b"resource_id,capacity\ncrew,1\ncrew,2\n", policies)
        with self.assertRaises(ValueError):
            parse_resource_capacities(b"resource_id,capacity\nunknown,1\n", policies)
        with self.assertRaises(ValueError):
            parse_resource_capacities(b"resource_id,capacity\ncrew,0\n", policies)

    def test_resource_metadata_validation(self):
        tasks, actions, _, _ = load("warehouse")
        bad = ("option_id,resource_id,resource_units\n"
               "FAST_FREIGHT,crew,abc\nOVERTIME,,\nPREP_CREW,,\nEXPRESS,,\n").encode()
        with self.assertRaises(ValueError):
            parse_action_policies(bad, actions)
        bad2 = ("option_id,incompatible_with\n"
                "FAST_FREIGHT,NOT_AN_OPTION\nOVERTIME,\nPREP_CREW,\nEXPRESS,\n").encode()
        with self.assertRaises(ValueError):
            parse_action_policies(bad2, actions)

    def test_max_action_bounds(self):
        tasks, actions, policies, caps = load("warehouse")
        for invalid in (0, 4, 1.5, True):
            with self.assertRaises(ValueError):
                optimize_recovery(tasks, actions, "W4", 9, 17, 400, policies, caps, invalid)

    def test_more_than_twenty_options_rejected(self):
        tasks, actions, policies, caps = load("equipment")
        too_many = actions * 8
        with self.assertRaisesRegex(ValueError, "at most 20"):
            optimize_recovery(tasks, too_many, "C", 10, 15, 300, policies, caps)

    def test_third_action_search_consistent(self):
        tasks, actions, policies, caps = load("warehouse")
        two = optimize_recovery(tasks, actions, "W4", 9, 17, 400, policies, caps, 2)
        three = optimize_recovery(tasks, actions, "W4", 9, 17, 400, policies, caps, 3)
        self.assertEqual(two["recommendation"]["plan_ids"], three["recommendation"]["plan_ids"])
        self.assertGreaterEqual(three["valid_plans_evaluated"], two["valid_plans_evaluated"])


if __name__ == "__main__":
    unittest.main()