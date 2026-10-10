"""Supplementary Phase 6 regression tests. Run with existing Phase 1–5 tests."""
import tempfile
import unittest
from pathlib import Path

from phase6_evaluate import GOLDEN, evaluate, load_sample, rec_signature, run


class TestPhase6(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loaded = {p: load_sample(p)[0] for p in {case.project for case in GOLDEN}}

    def test_golden_answers(self):
        for case in GOLDEN:
            with self.subTest(case=case.case_id):
                result = evaluate(case, self.loaded)
                self.assertEqual(rec_signature(result), (case.expected_ids, case.expected_finish, case.expected_cost))

    def test_action_limit_does_not_make_feasible_solutions_disappear(self):
        for case in GOLDEN:
            with self.subTest(case=case.case_id):
                a = rec_signature(evaluate(case, self.loaded, 1))
                b = rec_signature(evaluate(case, self.loaded, 2))
                if a[0] is not None:
                    self.assertIsNotNone(b[0])
                    self.assertLessEqual(b[2], a[2])

    def test_no_action_case(self):
        case = next(c for c in GOLDEN if c.case_id == 'WH_NO_ACTION')
        self.assertEqual(rec_signature(evaluate(case, self.loaded)), ((), 20, 0))

    def test_phase6_report_is_generated(self):
        with tempfile.TemporaryDirectory() as d:
            result = run(3, Path(d))
            self.assertTrue(result['passed'])
            self.assertTrue((Path(d) / 'summary.json').is_file())
            self.assertTrue((Path(d) / 'golden_scenarios.csv').is_file())
            self.assertTrue((Path(d) / 'PHASE6_EVALUATION_REPORT.md').is_file())

    def test_invalid_benchmark_iteration_count(self):
        with self.assertRaises(ValueError):
            run(0)


if __name__ == '__main__':
    unittest.main()
