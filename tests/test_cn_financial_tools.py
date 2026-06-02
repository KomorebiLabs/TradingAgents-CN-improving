"""
Tests for CN A-share financial statement tools.

Tests the new A-share balance sheet, cash flow, and income statement
implementations using AkShare.
"""

import pytest
import pandas as pd

# Import the functions to test
from tradingagents.dataflows.akshare_interface import (
    _prepare_financial_statement,
    _render_financial_statement,
    _render_bullets,
    AkShareRateLimitError,
    DataSourceError,
    DataNotFoundError,
    InvalidParameterError,
    _check_rate_limit,
    _reset_rate_limit_state,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_balance_sheet_df():
    """Mock balance sheet data."""
    return pd.DataFrame({
        "报告日期": ["2024-09-30", "2024-06-30"],
        "流动资产合计": [1000000, 950000],
        "非流动资产合计": [2000000, 1900000],
        "资产总计": [3000000, 2850000],
        "流动负债合计": [800000, 750000],
        "非流动负债合计": [500000, 480000],
        "负债合计": [1300000, 1230000],
        "所有者权益合计": [1700000, 1620000],
    })


@pytest.fixture
def mock_cashflow_df():
    """Mock cash flow data."""
    return pd.DataFrame({
        "报告日期": ["2024-09-30", "2024-06-30"],
        "经营活动产生的现金流量净额": [150000, 120000],
        "投资活动产生的现金流量净额": [-80000, -60000],
        "筹资活动产生的现金流量净额": [-30000, -20000],
    })


@pytest.fixture
def mock_income_df():
    """Mock income statement data."""
    return pd.DataFrame({
        "报告日期": ["2024-09-30", "2024-06-30"],
        "营业总收入": [5000000, 3500000],
        "营业总成本": [4200000, 2900000],
        "净利润": [600000, 450000],
        "基本每股收益": [0.85, 0.63],
    })


# ============================================================================
# Test: Financial Statement Helpers
# ============================================================================

class TestFinancialStatementHelpers:
    """Test helper functions for financial statements."""

    def test_prepare_financial_statement_empty(self):
        """Test preparing empty dataframe."""
        df = pd.DataFrame()
        result = _prepare_financial_statement(df, "test", 10)
        assert result.empty

    def test_prepare_financial_statement_with_data(self, mock_balance_sheet_df):
        """Test preparing non-empty dataframe."""
        result = _prepare_financial_statement(mock_balance_sheet_df, "balance_sheet", 2)
        assert len(result) == 2

    def test_render_bullets_filters_empty(self):
        """Test _render_bullets filters empty lines."""
        lines = ["Line 1", "", "Line 2", None, "Line 3"]
        result = _render_bullets(lines)
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result

    def test_render_financial_statement_empty(self):
        """Test rendering empty statement."""
        df = pd.DataFrame()
        result = _render_financial_statement(df, "Balance Sheet", "TEST")
        assert "No" in result and "Balance Sheet" in result

    def test_render_financial_statement_with_data(self, mock_balance_sheet_df):
        """Test rendering non-empty statement."""
        result = _render_financial_statement(
            mock_balance_sheet_df.head(1), "Balance Sheet", "TEST"
        )
        assert "TEST" in result
        assert "Balance Sheet" in result

    def test_render_financial_statement_numeric_formatting(self, mock_balance_sheet_df):
        """Test numeric values are properly formatted."""
        result = _render_financial_statement(
            mock_balance_sheet_df.head(1), "Balance Sheet", "TEST"
        )
        # Check that large numbers are formatted with commas
        assert "1,000,000" in result or "1000000" in result


# ============================================================================
# Test: Rate Limiting
# ============================================================================

class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_check_rate_limit_first_call(self):
        """Test first call has no delay."""
        import time
        _reset_rate_limit_state()

        start = time.time()
        _check_rate_limit("akshare")
        elapsed = time.time() - start

        assert elapsed < 0.05

    def test_check_rate_limit_enforced(self):
        """Test rate limit is enforced."""
        import time
        _reset_rate_limit_state()

        _check_rate_limit("akshare")

        start = time.time()
        _check_rate_limit("akshare")
        elapsed = time.time() - start

        assert elapsed >= 0.09

    def test_reset_rate_limit_state(self):
        """Test resetting rate limit state."""
        import time
        _reset_rate_limit_state()

        _check_rate_limit("akshare")
        _reset_rate_limit_state()

        start = time.time()
        _check_rate_limit("akshare")
        elapsed = time.time() - start

        assert elapsed < 0.05

    def test_rate_limit_alpha_vantage(self):
        """Test rate limit for Alpha Vantage (longer interval)."""
        import time
        _reset_rate_limit_state()

        _check_rate_limit("alpha_vantage")

        start = time.time()
        _check_rate_limit("alpha_vantage")
        elapsed = time.time() - start

        # Alpha Vantage should have longer interval
        assert elapsed >= 11.9

    def test_rate_limit_unknown_vendor(self):
        """Test rate limit for unknown vendor (no delay)."""
        import time
        _reset_rate_limit_state()

        start = time.time()
        _check_rate_limit("unknown_vendor")
        elapsed = time.time() - start

        # Unknown vendors should not have delay
        assert elapsed < 0.05


# ============================================================================
# Test: Error Classes
# ============================================================================

class TestErrorClasses:
    """Test custom error classes."""

    def test_akshare_rate_limit_error(self):
        """Test AkShareRateLimitError."""
        error = AkShareRateLimitError("Rate limit exceeded")
        assert "Rate limit" in str(error)

    def test_akshare_rate_limit_error_with_cause(self):
        """Test AkShareRateLimitError with cause."""
        original_error = Exception("Original error")
        try:
            raise original_error
        except Exception as e:
            error = AkShareRateLimitError(str(e))
            assert "Original error" in str(error)

    def test_data_source_error(self):
        """Test DataSourceError."""
        error = DataSourceError("Generic data source error")
        assert "Generic" in str(error)

    def test_data_source_error_with_cause(self):
        """Test DataSourceError with cause."""
        try:
            raise Exception("Original error")
        except Exception as e:
            error = DataSourceError(str(e))
            assert "Original error" in str(error)

    def test_data_not_found_error(self):
        """Test DataNotFoundError."""
        error = DataNotFoundError("Data not found")
        assert "not found" in str(error)

    def test_invalid_parameter_error(self):
        """Test InvalidParameterError."""
        error = InvalidParameterError("Invalid parameter")
        assert "Invalid" in str(error)

    def test_error_inheritance(self):
        """Test error class inheritance."""
        assert issubclass(AkShareRateLimitError, Exception)
        assert issubclass(DataSourceError, Exception)
        assert issubclass(DataNotFoundError, DataSourceError)
        assert issubclass(InvalidParameterError, DataSourceError)


# ============================================================================
# Test: Symbol Normalization (via interface imports)
# ============================================================================

class TestSymbolNormalization:
    """Test CN symbol normalization."""

    def test_normalize_shanghai_symbol(self):
        """Test Shanghai symbol normalization."""
        from tradingagents.dataflows.akshare_interface import _normalize_cn_symbol
        code, exchange = _normalize_cn_symbol("600519.SH")
        assert code == "600519"
        assert exchange == "sh"

    def test_normalize_shanghai_symbol_xshg(self):
        """Test Shanghai symbol with XSHG suffix."""
        from tradingagents.dataflows.akshare_interface import _normalize_cn_symbol
        code, exchange = _normalize_cn_symbol("600519.XSHG")
        assert code == "600519"
        assert exchange == "sh"

    def test_normalize_shenzhen_symbol(self):
        """Test Shenzhen symbol normalization."""
        from tradingagents.dataflows.akshare_interface import _normalize_cn_symbol
        code, exchange = _normalize_cn_symbol("000001.SZ")
        assert code == "000001"
        assert exchange == "sz"

    def test_normalize_shenzhen_symbol_xshe(self):
        """Test Shenzhen symbol with XSHE suffix."""
        from tradingagents.dataflows.akshare_interface import _normalize_cn_symbol
        code, exchange = _normalize_cn_symbol("000001.XSHE")
        assert code == "000001"
        assert exchange == "sz"

    def test_normalize_bj_symbol(self):
        """Test Beijing Stock Exchange symbol."""
        from tradingagents.dataflows.akshare_interface import _normalize_cn_symbol
        code, exchange = _normalize_cn_symbol("830999.BJ")
        assert code == "830999"
        assert exchange == "bj"

    def test_normalize_infer_shanghai_from_6_prefix(self):
        """Test Shanghai inferred from 6 prefix."""
        from tradingagents.dataflows.akshare_interface import _normalize_cn_symbol
        code, exchange = _normalize_cn_symbol("600519")
        assert code == "600519"
        assert exchange == "sh"

    def test_normalize_infer_shenzhen_from_0_prefix(self):
        """Test Shenzhen inferred from 0 prefix."""
        from tradingagents.dataflows.akshare_interface import _normalize_cn_symbol
        code, exchange = _normalize_cn_symbol("000001")
        assert code == "000001"
        assert exchange == "sz"

    def test_normalize_infer_bj_from_8_prefix(self):
        """Test Beijing inferred from 8 prefix."""
        from tradingagents.dataflows.akshare_interface import _normalize_cn_symbol
        code, exchange = _normalize_cn_symbol("830999")
        assert code == "830999"
        assert exchange == "bj"

    def test_normalize_invalid_symbol_raises(self):
        """Test invalid symbol raises ValueError."""
        from tradingagents.dataflows.akshare_interface import _normalize_cn_symbol
        with pytest.raises(ValueError):
            _normalize_cn_symbol("INVALID")
