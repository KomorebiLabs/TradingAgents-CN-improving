"""Offline tests for the dataflows vendor routing table."""

from __future__ import annotations

import pytest

import tradingagents.default_config as default_config
from tradingagents.dataflows import interface
from tradingagents.dataflows.config import set_config


@pytest.fixture(autouse=True)
def _reset_config():
    """Give every test a pristine default config view."""
    set_config(default_config.DEFAULT_CONFIG.copy())
    yield
    set_config(default_config.DEFAULT_CONFIG.copy())


class TestCategoryLookup:
    @pytest.mark.smoke
    def test_known_methods(self):
        assert interface.get_category_for_method("get_stock_data") == "core_stock_apis"
        assert interface.get_category_for_method("get_indicators") == "technical_indicators"
        assert interface.get_category_for_method("get_news") == "news_data"
        assert interface.get_category_for_method("get_cn_macro_data") == "cn_macro_data"
        assert interface.get_category_for_method("get_cn_limit_up_stocks") == "cn_event_data"

    def test_unknown_method_raises(self):
        with pytest.raises(ValueError):
            interface.get_category_for_method("get_nonexistent_thing")


class TestVendorNormalization:
    def test_aliases_normalize(self):
        assert interface._normalize_vendor_name("tencent") == "tencent_finance"
        assert interface._normalize_vendor_name("akshare") == "legacy_akshare"
        assert interface._normalize_vendor_name("") == ""
        assert interface._normalize_vendor_name("weird_vendor") == "weird_vendor"

    def test_default_priority_uses_canonical_names(self):
        vendors = interface.get_vendor("core_stock_apis").split(",")
        assert vendors[0] == "tencent_finance"

    def test_every_registered_vendor_method_has_category(self):
        for method in interface.VENDOR_METHODS:
            assert interface.get_category_for_method(method) is not None


class TestRouteToVendor:
    def test_unknown_method_rejected_before_any_vendor_call(self):
        with pytest.raises(ValueError):
            interface.route_to_vendor("get_nonexistent_thing", "600519")

    def test_no_screener_back_reference_in_dataflows(self):
        """dataflows must not route through ScreenerDataAccess (dead code removed)."""
        assert not hasattr(interface, "_screener_callable")
        assert not hasattr(interface, "_call_screener_data_access")

    def test_akshare_facade_covers_registry_entries(self):
        """The registry-referenced akshare functions all resolve on the facade.

        Guards the akshare_interface split: implementations moved to
        dataflows/akshare/ but VENDOR_METHODS still resolves through the
        facade by string name.
        """
        import importlib
        import re
        from pathlib import Path

        interface_src = Path(interface.__file__).read_text(encoding="utf-8")
        registered = set(re.findall(r'\.akshare_interface", "(get_akshare_[a-z_]+)"', interface_src))
        assert len(registered) >= 23, "registry unexpectedly shrank"
        facade = importlib.import_module("tradingagents.dataflows.akshare_interface")
        missing = [n for n in registered if not callable(getattr(facade, n, None))]
        assert not missing, f"facade missing: {missing}"


class TestTypedVendorErrors:
    def test_unavailable_stub_raises_typed_error(self):
        from tradingagents.dataflows.errors import VendorUnavailable

        stub = interface._raise_vendor_unavailable("baostock_data", "get_stock_data")
        with pytest.raises(VendorUnavailable):
            stub()

    def test_typed_errors_still_runtime_errors_for_compat(self):
        from tradingagents.dataflows.errors import (
            DataNotFound,
            VendorError,
            VendorRateLimited,
            VendorSchemaChanged,
            VendorUnavailable,
        )

        for exc_cls in (VendorRateLimited, VendorUnavailable, DataNotFound, VendorSchemaChanged):
            assert issubclass(exc_cls, VendorError)
            assert issubclass(exc_cls, RuntimeError)

    def test_rate_limit_detector_recognizes_typed_error(self):
        from tradingagents.dataflows.errors import VendorRateLimited

        assert interface._is_rate_limit_error(VendorRateLimited("throttled"))


class TestStage2FakeSuccessVisibility:
    """R3: placeholder/unavailable tool text must be logged (fake success visible)."""

    def test_looks_like_unavailable_matches_placeholders(self):
        assert interface._looks_like_unavailable("No fundamentals data found for symbol '600519'")
        assert interface._looks_like_unavailable("Income statement data unavailable for 600519.SH: boom")
        assert interface._looks_like_unavailable("No CN policy-sensitive macro events found around 2026-08-16")
        # real content must NOT be flagged
        assert not interface._looks_like_unavailable("# 600519 资产负债表\n\n- 资产: 100")
        assert not interface._looks_like_unavailable("date,open,close\n2026-01-01,10,11")

    def test_placeholder_text_warns(self, monkeypatch, caplog):
        import logging

        fake = lambda *a, **k: "No CN A-share data found for symbol 'sh600519' between X and Y"
        monkeypatch.setattr(interface, "_load_attr", lambda m, a: fake)
        with caplog.at_level(logging.WARNING):
            result = interface.route_to_vendor("get_stock_data", "600519", "2026-01-01", "2026-01-10")
        # contract preserved: caller still receives the text
        assert "No CN A-share data found" in result
        assert "placeholder/unavailable" in caplog.text

    def test_normal_text_no_warning(self, monkeypatch, caplog):
        import logging

        fake = lambda *a, **k: "date,open,close\n2026-01-01,10,11"
        monkeypatch.setattr(interface, "_load_attr", lambda m, a: fake)
        with caplog.at_level(logging.WARNING):
            result = interface.route_to_vendor("get_stock_data", "600519", "2026-01-01", "2026-01-10")
        assert result.startswith("date,open,close")
        assert "placeholder" not in caplog.text
