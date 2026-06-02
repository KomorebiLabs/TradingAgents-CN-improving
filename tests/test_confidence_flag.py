import unittest

from tradingagents.graph.propagation import Propagator


class ConfidenceFlagTests(unittest.TestCase):
    def test_confidence_flag_defaults_to_false(self):
        state = Propagator().create_initial_state("AAPL", "2026-05-05")
        self.assertFalse(state["orchestration"]["enable_confidence_score"])

    def test_confidence_flag_can_be_enabled(self):
        state = Propagator(config={"enable_confidence_score": True}).create_initial_state(
            "AAPL",
            "2026-05-05",
        )
        self.assertTrue(state["orchestration"]["enable_confidence_score"])


if __name__ == "__main__":
    unittest.main()
