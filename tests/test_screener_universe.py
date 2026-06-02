import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock

import pandas as pd

from tradingagents.screener.config import SCREENER_CONFIG
from tradingagents.screener.universe import (
    build_screening_universe,
    _fetch_constituents_for_indexes,
)


class ScreenerUniverseTests(unittest.TestCase):
    def test_build_mvp_universe(self):
        """H1 FIX: universe must return real constituent stocks, not index codes."""
        with TemporaryDirectory() as temp_dir:
            config = {
                **SCREENER_CONFIG,
                "data_cache_dir": temp_dir,
            }
            result = build_screening_universe(mode="MVP", config=config)
        # After H1 fix: tickers should be real constituent stock codes (300 for CSI 300)
        self.assertGreaterEqual(len(result.tickers), 100)
        self.assertEqual(result.metadata["mode"], "MVP")
        # H1 FIX: source is now constituent expansion, not baseline index
        self.assertEqual(result.metadata["source"], "index_constituent_expansion")
        self.assertEqual(result.metadata["profile"], "MVP")
        self.assertEqual(result.metadata["expansion_mode"], "index_union")
        # H1 FIX: cache key reflects constituent expansion
        self.assertEqual(result.metadata["cache_key"], "mvp_constituents")
        # H1 FIX: constituent_expansion_ready must be True now
        self.assertTrue(result.metadata["constituent_expansion_ready"])
        self.assertIn("display_tickers", result.metadata)
        # H1 FIX: metadata must track which indexes were used
        self.assertIn("index_codes_used", result.metadata)
        self.assertEqual(result.metadata["index_codes_used"], ["000300", "000905"])

    def test_build_extended_universe(self):
        """H1 FIX: EXTENDED universe must return real constituent stocks."""
        with TemporaryDirectory() as temp_dir:
            config = {
                **SCREENER_CONFIG,
                "data_cache_dir": temp_dir,
            }
            result = build_screening_universe(mode="EXTENDED", config=config)
        # After H1 fix: tickers should be real constituent stock codes (300+ for CSI 300/500)
        self.assertGreaterEqual(len(result.tickers), 100)
        self.assertEqual(result.metadata["mode"], "EXTENDED")
        self.assertEqual(result.metadata["profile"], "EXTENDED")
        self.assertEqual(result.metadata["expansion_mode"], "index_union_plus_growth")
        # H1 FIX: constituent_expansion_ready must be True
        self.assertTrue(result.metadata["constituent_expansion_ready"])

    def test_build_experimental_universe(self):
        """H1 FIX: EXPERIMENTAL universe must return real constituent stocks."""
        with TemporaryDirectory() as temp_dir:
            config = {
                **SCREENER_CONFIG,
                "data_cache_dir": temp_dir,
            }
            result = build_screening_universe(mode="EXPERIMENTAL", config=config)
        self.assertGreaterEqual(len(result.tickers), 100)
        self.assertEqual(result.metadata["mode"], "EXPERIMENTAL")
        self.assertEqual(result.metadata["profile"], "EXPERIMENTAL")
        self.assertEqual(result.metadata["expansion_mode"], "experimental_index_union")
        self.assertTrue(result.metadata["constituent_expansion_ready"])

    def test_universe_cache_uses_profile_cache_key(self):
        """H1 FIX: cache file is read and returned on subsequent calls."""
        with TemporaryDirectory() as temp_dir:
            config = {
                **SCREENER_CONFIG,
                "data_cache_dir": temp_dir,
            }
            first = build_screening_universe(mode="MVP", config=config)
            # H1 FIX: cache key is now "mvp_constituents"
            cache_file = Path(temp_dir) / "screener" / "universe_mvp_constituents.json"
            self.assertTrue(cache_file.exists())

            # Mutate the cache to verify subsequent calls read from cache
            cached_text = cache_file.read_text(encoding="utf-8")
            import re
            mutated = re.sub(r'"ticker_count": \d+', '"ticker_count": 999', cached_text)
            cache_file.write_text(mutated, encoding="utf-8")

            second = build_screening_universe(mode="MVP", config=config)
            self.assertEqual(second.metadata["ticker_count"], 999)
            self.assertEqual(first.metadata["cache_key"], second.metadata["cache_key"])


class FetchConstituentsTests(unittest.TestCase):
    """P0 boundary/exception tests for _fetch_constituents_for_indexes (H1)."""

    def test_fetch_constituents_with_mock_data_access(self):
        """Mock data access returns correct constituent codes."""
        mock_df = pd.DataFrame({
            "成分券代码": ["600519", "000858", "000001"],
            "成分券名称": ["贵州茅台", "五粮液", "平安银行"],
            "权重": [8.5, 3.2, 1.1],
        })

        mock_da = MagicMock()
        mock_da.fetch_index_constituents.return_value = mock_df

        result = _fetch_constituents_for_indexes(["000300"], mock_da)
        self.assertEqual(len(result), 3)
        self.assertIn("600519", result)
        self.assertIn("000858", result)
        self.assertIn("000001", result)

    def test_fetch_constituents_merges_multiple_indexes(self):
        """Multiple indexes are merged and deduplicated."""
        mock_df1 = pd.DataFrame({"成分券代码": ["600519", "000858"]})
        mock_df2 = pd.DataFrame({"成分券代码": ["000858", "000001"]})

        mock_da = MagicMock()
        mock_da.fetch_index_constituents.side_effect = [mock_df1, mock_df2]

        result = _fetch_constituents_for_indexes(["000300", "000905"], mock_da)
        self.assertEqual(len(result), 3)  # deduplicated
        self.assertIn("600519", result)
        self.assertIn("000858", result)
        self.assertIn("000001", result)

    def test_fetch_constituents_handles_empty_df(self):
        """Empty DataFrame is skipped, returns empty list."""
        mock_da = MagicMock()
        mock_da.fetch_index_constituents.return_value = pd.DataFrame()

        result = _fetch_constituents_for_indexes(["000300"], mock_da)
        self.assertEqual(result, [])

    def test_fetch_constituents_handles_none_df(self):
        """None return is skipped, returns empty list."""
        mock_da = MagicMock()
        mock_da.fetch_index_constituents.return_value = None

        result = _fetch_constituents_for_indexes(["000300"], mock_da)
        self.assertEqual(result, [])

    def test_fetch_constituents_handles_missing_column(self):
        """DataFrame without expected column returns empty list."""
        mock_df = pd.DataFrame({"some_other_column": ["600519"]})
        mock_da = MagicMock()
        mock_da.fetch_index_constituents.return_value = mock_df

        result = _fetch_constituents_for_indexes(["000300"], mock_da)
        self.assertEqual(result, [])

    def test_fetch_constituents_handles_non_numeric_codes(self):
        """Non-numeric and empty codes are skipped."""
        mock_df = pd.DataFrame({
            "成分券代码": ["600519", "INVALID", "", "000858", None, "  "],
        })
        mock_da = MagicMock()
        mock_da.fetch_index_constituents.return_value = mock_df

        result = _fetch_constituents_for_indexes(["000300"], mock_da)
        self.assertEqual(len(result), 2)
        self.assertIn("600519", result)
        self.assertIn("000858", result)

    def test_fetch_constituents_data_access_lazy_init(self):
        """When data_access is not provided, function creates it internally."""
        # Patch where the import happens inside _fetch_constituents_for_indexes
        with patch("tradingagents.screener.data_access.ScreenerDataAccess") as MockDA:
            mock_instance = MagicMock()
            mock_df = pd.DataFrame({"成分券代码": ["600519"]})
            mock_instance.fetch_index_constituents.return_value = mock_df
            MockDA.return_value = mock_instance

            result = _fetch_constituents_for_indexes(["000300"])
            self.assertEqual(result, ["600519"])
            MockDA.assert_called_once()


    def test_build_universe_fails_loudly_when_apis_all_fail(self):
        """B-3.1: When all constituent APIs fail, universe.py must raise RuntimeError, not return ETF codes."""
        with TemporaryDirectory() as temp_dir:
            config = {
                **SCREENER_CONFIG,
                "data_cache_dir": temp_dir,
            }
            with patch(
                "tradingagents.screener.universe._fetch_constituents_for_indexes",
                return_value=[],
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    build_screening_universe(mode="MVP", config=config)
                self.assertIn("All index constituent APIs failed", str(ctx.exception))
                self.assertIn("000300", str(ctx.exception))
                self.assertIn("000905", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
