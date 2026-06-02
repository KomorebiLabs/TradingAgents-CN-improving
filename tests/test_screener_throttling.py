import unittest

from tradingagents.screener.throttling import AntiBanConfig, ThrottledRequester


class ScreenerThrottlingTests(unittest.TestCase):
    def test_requester_collects_stats(self):
        requester = ThrottledRequester(
            AntiBanConfig(base_interval=0.0, burst_threshold=100, burst_pause=0.0, failure_penalty=0.0)
        )

        result = requester.request(lambda: "ok")
        stats = requester.get_stats()

        self.assertEqual(result, "ok")
        self.assertEqual(stats["total_requests"], 1)
        self.assertEqual(stats["failed_requests"], 0)

    def test_requester_handles_failure(self):
        requester = ThrottledRequester(
            AntiBanConfig(base_interval=0.0, burst_threshold=100, burst_pause=0.0, failure_penalty=0.0)
        )

        def boom():
            raise RuntimeError("failure")

        result = requester.request(boom)
        stats = requester.get_stats()

        self.assertIsNone(result)
        self.assertEqual(stats["failed_requests"], 1)
        self.assertIn("RuntimeError", requester.get_last_error_detail())


if __name__ == "__main__":
    unittest.main()
