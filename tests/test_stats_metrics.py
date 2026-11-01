import unittest

from src.metrics import compute_wilson_ci, fit_bvr_logistic_regression


class TestStatsMetrics(unittest.TestCase):
    def test_wilson_ci_bounds(self):
        # 0 of 100
        ci_zero = compute_wilson_ci(0, 100)
        self.assertEqual(ci_zero.proportion, 0.0)
        self.assertEqual(ci_zero.ci_lower, 0.0)
        self.assertGreater(ci_zero.ci_upper, 0.0)
        self.assertLess(ci_zero.ci_upper, 0.05)

        # 50 of 100
        ci_half = compute_wilson_ci(50, 100)
        self.assertEqual(ci_half.proportion, 0.5)
        self.assertAlmostEqual(ci_half.ci_lower, 0.4038, places=2)
        self.assertAlmostEqual(ci_half.ci_upper, 0.5962, places=2)

        # 100 of 100
        ci_full = compute_wilson_ci(100, 100)
        self.assertEqual(ci_full.proportion, 1.0)
        self.assertEqual(ci_full.ci_upper, 1.0)
        self.assertGreater(ci_full.ci_lower, 0.95)

    def test_logistic_regression_fit(self):
        # Synthetic dataset where higher depth & lag reliably causes violations
        samples = []
        for d in [0, 3, 6, 10]:
            for l in [0, 2, 5]:
                # True probability increases with depth and lag
                prob = 0.1 + (0.06 * d) + (0.05 * l)
                for i in range(10):
                    y = (i / 10.0) < prob
                    samples.append((d, l, y))

        res = fit_bvr_logistic_regression(samples)
        self.assertIsNotNone(res)
        self.assertTrue(res.converged)
        # Depth coefficient should be positive (odds ratio > 1)
        self.assertGreater(res.coef_depth, 0.0)
        self.assertGreater(res.odds_ratio_depth(), 1.0)


if __name__ == "__main__":
    unittest.main()
