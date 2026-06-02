import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tradingagents.screener.data_access import ScreenerDataAccess
from tradingagents.screener.http_spoof import patch_requests_browser_headers


class ScreenerDataAccessTests(unittest.TestCase):
    def test_validate_interface_assumptions_returns_probe_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            access = ScreenerDataAccess(
                config={
                    "data_cache_dir": tmpdir,
                    "a0_probe": {
                        "enable_live_probes": False,
                        "cache_ttl_minutes": 60,
                    },
                }
            )
            summary = access.validate_interface_assumptions(trade_date="2026-05-07")
            self.assertTrue(summary["validated"])
            self.assertIn("warnings", summary)
            self.assertIn("trade_date", summary)

    def test_probe_cache_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            access = ScreenerDataAccess(
                config={
                    "data_cache_dir": tmpdir,
                    "a0_probe": {
                        "enable_live_probes": False,
                        "cache_ttl_minutes": 60,
                    },
                }
            )
            summary = access.validate_interface_assumptions(trade_date="2026-05-07")
            # New cache file name
            cache_file = Path(tmpdir) / "screener" / "a0_probe_summary_v2.json"
            self.assertTrue(cache_file.exists())
            payload = json.loads(cache_file.read_text(encoding="utf-8"))
            self.assertIn("validated", payload)
            self.assertEqual(payload["trade_date"], "2026-05-07")

    def test_summary_contains_request_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            access = ScreenerDataAccess(
                config={
                    "data_cache_dir": tmpdir,
                    "a0_probe": {
                        "enable_live_probes": False,
                        "cache_ttl_minutes": 60,
                    },
                }
            )
            summary = access.validate_interface_assumptions(trade_date="2026-05-07")
            self.assertIn("request_stats", summary)
            # New field names
            self.assertIn("hist_primary_vendor", summary)
            self.assertIn("spot_primary_vendor", summary)
            self.assertIn("concept_primary_vendor", summary)
            self.assertIn("industry_primary_vendor", summary)
            self.assertIn("fund_flow_primary_vendor", summary)
            self.assertIn("spot_snapshot_verified", summary)
            self.assertIn("hist_fetch_verified", summary)
            self.assertIn("concept_list_verified", summary)
            self.assertIn("industry_list_verified", summary)
            self.assertIn("fund_flow_verified", summary)
            self.assertIn("index_spot_verified", summary)
            self.assertIn("tick_data_verified", summary)
            # Library status
            self.assertIn("baostock_importable", summary)
            self.assertIn("py_mini_racer_importable", summary)
            self.assertIn("tushare_importable", summary)
            self.assertIn("akshare_importable", summary)
            # Legacy aliases must remain available for current strategies/report
            self.assertIn("fund_flow_bulk_verified", summary)
            self.assertIn("tencent_hist_verified", summary)
            self.assertIn("yfinance_hist_verified", summary)
            self.assertIn("hist_fetch_fallback_vendor", summary)

    def test_probe_call_can_patch_browser_like_headers(self):
        """Test that browser-like headers are injected into requests."""
        fake_response = MagicMock()

        with patch("requests.sessions.Session.request", return_value=fake_response) as mock_request:
            with patch_requests_browser_headers():
                __import__("requests").get("https://example.com")

        _, kwargs = mock_request.call_args
        self.assertIn("headers", kwargs)
        self.assertIn("Mozilla/5.0", kwargs["headers"]["User-Agent"])

    def test_ticker_normalization(self):
        """Test ticker format normalization for different sources."""
        access = ScreenerDataAccess()
        # Sina
        self.assertEqual(access._normalize_ticker_for_sina("600519"), "sh600519")
        self.assertEqual(access._normalize_ticker_for_sina("000001"), "sz000001")
        self.assertEqual(access._normalize_ticker_for_sina("sh600519"), "sh600519")
        self.assertEqual(access._normalize_ticker_for_sina("sz000001"), "sz000001")
        # Tencent
        code, exch = access._normalize_ticker_for_tencent("600519")
        self.assertEqual((code, exch), ("600519", "sh"))
        code, exch = access._normalize_ticker_for_tencent("000001")
        self.assertEqual((code, exch), ("000001", "sz"))
        code, exch = access._normalize_ticker_for_tencent("sh600519")
        self.assertEqual((code, exch), ("600519", "sh"))
        code, exch = access._normalize_ticker_for_tencent("sz000001")
        self.assertEqual((code, exch), ("000001", "sz"))
        # Baostock
        self.assertEqual(access._normalize_ticker_for_baostock("sh600519"), "sh.600519")
        self.assertEqual(access._normalize_ticker_for_baostock("sz000001"), "sz.000001")
        self.assertEqual(access._normalize_ticker_for_baostock("sh.600519"), "sh.600519")
        # yfinance
        self.assertEqual(access._normalize_ticker_for_yfinance("sh600519"), "600519.SS")
        self.assertEqual(access._normalize_ticker_for_yfinance("sz000001"), "000001.SZ")

    def test_library_detection(self):
        """Test that library detection returns a complete status map."""
        access = ScreenerDataAccess()
        libs = access._check_libraries()
        self.assertIn("akshare", libs)
        self.assertIn("baostock", libs)
        self.assertIn("py_mini_racer", libs)
        self.assertIn("tushare", libs)
        for value in libs.values():
            self.assertIsInstance(value, bool)

    def test_default_vendors_config(self):
        """Test that default vendors config is applied."""
        access = ScreenerDataAccess()
        vendors = access._vendors_config()
        self.assertEqual(vendors["hist_primary"], "tencent_direct")
        self.assertEqual(vendors["spot_primary"], "tencent_direct")
        self.assertEqual(vendors["concept_primary"], "ths")
        self.assertEqual(vendors["industry_primary"], "ths")
        self.assertEqual(vendors["fund_flow_primary"], "ths")
        self.assertEqual(vendors["index_primary"], "tencent_direct")

    def test_capability_summary_exposes_vendor_baseline_and_strategy_capabilities(self):
        access = ScreenerDataAccess(
            config={
                "a0_probe": {
                    "enable_live_probes": False,
                }
            }
        )
        summary = access.validate_interface_assumptions(trade_date="2026-05-07")

        self.assertIn("vendor_baseline", summary)
        self.assertEqual(summary["vendor_baseline"]["history"]["primary"], "tencent_direct")
        self.assertEqual(summary["vendor_baseline"]["history"]["eastmoney_role"], "compatibility_only")
        self.assertIn("strategy_capabilities", summary)
        self.assertEqual(summary["strategy_capabilities"]["policy"]["primary_dependencies"]["concept_list"], "ths")
        self.assertEqual(summary["strategy_capabilities"]["smart_money"]["primary_dependencies"]["hist_fetch"], "tencent_direct")


class FundFlowFallbackChainTests(unittest.TestCase):
    """P0 boundary tests for H4: fund_flow fallback chain THS → em (was baostock → None)."""

    def test_fund_flow_fetches_from_em_when_ths_fails(self):
        """H4 FIX: when THS returns None/empty, should try AkShare EastMoney."""
        import pandas as pd

        access = ScreenerDataAccess(config={"vendors": {"fund_flow_primary": "ths", "fund_flow_secondary": "em"}})
        mock_df = pd.DataFrame({"股票代码": ["000001"], "主力净流入": [1e8]})

        # THS fails, EM succeeds
        with patch.object(access, "_fetch_fund_flow_ths", return_value=None):
            with patch.object(access, "_fetch_fund_flow_em", return_value=mock_df) as mock_em:
                result = access.fetch_fund_flow(symbol="即时")
                mock_em.assert_called_once()
                self.assertFalse(result.empty)

    def test_fund_flow_em_fetch_is_available(self):
        """H4 FIX: _fetch_fund_flow_em method exists and is callable."""
        access = ScreenerDataAccess()
        self.assertTrue(hasattr(access, "_fetch_fund_flow_em"))
        self.assertTrue(callable(getattr(access, "_fetch_fund_flow_em")))

    def test_fund_flow_vendor_baseline_reports_em_as_secondary(self):
        """H4 FIX: vendor_baseline.fund_flow.secondary should be 'em', not 'baostock'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            access = ScreenerDataAccess(
                config={
                    "data_cache_dir": tmpdir,
                    "vendors": {"fund_flow_primary": "ths", "fund_flow_secondary": "em"},
                    "a0_probe": {"enable_live_probes": False},
                }
            )
            summary = access.validate_interface_assumptions()
            self.assertEqual(
                summary["vendor_baseline"]["fund_flow"]["secondary"], "em",
                "fund_flow.secondary should be 'em', not 'baostock' (H4 fix)",
            )


if __name__ == "__main__":
    unittest.main()
