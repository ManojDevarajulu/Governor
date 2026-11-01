import unittest

from src.evaluator import Evaluator
from src.interceptors import ProtocolType


class TestReproducibility(unittest.TestCase):
    def test_deterministic_episode_replay(self):
        evaluator1 = Evaluator()
        evaluator2 = Evaluator()

        # Run 20 episodes on baseline
        rep1 = evaluator1.evaluate_protocol(ProtocolType.UNMONITORED_BASELINE, seeds_per_cell=5)
        rep2 = evaluator2.evaluate_protocol(ProtocolType.UNMONITORED_BASELINE, seeds_per_cell=5)

        self.assertEqual(rep1.total_episodes, rep2.total_episodes)
        self.assertEqual(rep1.overall_bvr.proportion, rep2.overall_bvr.proportion)
        self.assertEqual(rep1.overall_bvr.ci_lower, rep2.overall_bvr.ci_lower)
        self.assertEqual(rep1.overall_bvr.ci_upper, rep2.overall_bvr.ci_upper)


if __name__ == "__main__":
    unittest.main()
