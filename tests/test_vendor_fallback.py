import unittest

from tradingagents.dataflows.config import get_config, set_config
from tradingagents.dataflows.interface import VENDOR_METHODS, route_to_vendor


class VendorFallbackTests(unittest.TestCase):
    def setUp(self):
        self._original_config = get_config()

    def tearDown(self):
        set_config(self._original_config)

    def test_route_falls_back_when_akshare_dependency_missing(self):
        config = get_config()
        config["tool_vendors"]["get_stock_data"] = "akshare,yfinance"
        set_config(config)

        original_akshare = VENDOR_METHODS["get_stock_data"]["akshare"]
        original_yfinance = VENDOR_METHODS["get_stock_data"]["yfinance"]
        VENDOR_METHODS["get_stock_data"]["akshare"] = lambda *args, **kwargs: (_ for _ in ()).throw(ImportError("AkShare is required"))
        VENDOR_METHODS["get_stock_data"]["yfinance"] = lambda *args, **kwargs: "fallback-ok"

        try:
            result = route_to_vendor("get_stock_data", "000001.SZ", "2026-01-01", "2026-02-01")
        finally:
            VENDOR_METHODS["get_stock_data"]["akshare"] = original_akshare
            VENDOR_METHODS["get_stock_data"]["yfinance"] = original_yfinance

        self.assertEqual(result, "fallback-ok")

    def test_route_does_not_swallow_non_dependency_errors(self):
        config = get_config()
        config["tool_vendors"]["get_stock_data"] = "akshare"
        set_config(config)

        original_akshare = VENDOR_METHODS["get_stock_data"]["akshare"]
        VENDOR_METHODS["get_stock_data"]["akshare"] = lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("bad-symbol-shape"))

        try:
            with self.assertRaises(ValueError):
                route_to_vendor("get_stock_data", "INVALID", "2026-01-01", "2026-02-01")
        finally:
            VENDOR_METHODS["get_stock_data"]["akshare"] = original_akshare


if __name__ == "__main__":
    unittest.main()
