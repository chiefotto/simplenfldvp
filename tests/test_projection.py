import math
import unittest

from services.projection_service import estimate_ratio, estimate_z


class ProjectionTests(unittest.TestCase):
    def test_ratio_example_and_equal_allowance(self):
        estimate = estimate_ratio(2.10, 2.10, 1.50)
        self.assertAlmostEqual(estimate["adjusted"], 2.52)
        self.assertAlmostEqual(estimate["multiplier"], 1.20)
        self.assertEqual(estimate["method"], "ratio")
        self.assertFalse(estimate["capped"])
        same = estimate_ratio(1.90, 1.50, 1.50)
        self.assertAlmostEqual(same["adjusted"], 1.90)
        weaker = estimate_ratio(2.0, 1.0, 2.0)
        stronger = estimate_ratio(2.0, 3.0, 2.0)
        self.assertLess(weaker["adjusted"], 2.0)
        self.assertGreater(stronger["adjusted"], 2.0)

    def test_z_example(self):
        estimate = estimate_z(1.90, 2.00)
        self.assertAlmostEqual(estimate["adjusted"], 2.47)
        self.assertAlmostEqual(estimate["multiplier"], 1.30)
        self.assertEqual(estimate["method"], "z")

    def test_caps_and_invalid_inputs(self):
        high = estimate_ratio(2.0, 10.0, 1.0)
        low = estimate_ratio(2.0, 0.0, 1.0, weight=1)
        self.assertEqual(high["multiplier"], 1.50)
        self.assertTrue(high["capped"])
        self.assertEqual(low["multiplier"], 0.50)
        self.assertTrue(low["capped"])
        self.assertFalse(estimate_ratio(2.0, 0.0, 1.0)["capped"])
        for value in (None, math.nan, math.inf, "nope"):
            missing = estimate_ratio(value, 2.0, 1.0)
            self.assertIsNone(missing["adjusted"])
            self.assertIn("Not enough data", missing["reason"])
        negative = estimate_ratio(-2.0, 2.0, 1.0)
        self.assertEqual(negative["player_avg"], -2.0)
        self.assertIsNone(negative["adjusted"])
        zero = estimate_ratio(0.0, 2.0, 1.0)
        self.assertEqual(zero["adjusted"], 0.0)
        self.assertIn("zero", zero["reason"].lower())
        unavailable = estimate_ratio(2.0, 2.0, 0)
        self.assertEqual(unavailable["player_avg"], 2.0)
        self.assertIsNone(unavailable["adjusted"])
        self.assertTrue(unavailable["baseline_only"])
        self.assertIsNone(estimate_z(2.0, None)["adjusted"])
        self.assertIsNone(estimate_ratio(2.0, None, 1.5)["method"])
