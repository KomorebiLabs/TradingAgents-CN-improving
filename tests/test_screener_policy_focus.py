"""Tests for PolicyStrategy focus-aware concept selection (P5-focus)."""

from __future__ import annotations

import pandas as pd
from tradingagents.screener.strategies.policy import (
    PolicyStrategy,
    _FOCUS_ALIAS_KEYWORDS,
)


class TestSelectPolicyConcepts:
    """Test _select_policy_concepts with focus-aware logic."""

    def _make_concept_df(self, names):
        return pd.DataFrame({"name": names})

    def _make_news_df(self, text):
        return pd.DataFrame({"事件": [text]})

    # --- focus_aligned cases ---

    def test_focus_aligned_returns_semiconductor_concepts(self):
        """When news misses semiconductor but focus=semiconductor, selects 半导体/芯片."""
        concept_df = self._make_concept_df([
            "阿尔茨海默概念", "AI手机", "阿里巴巴概念", "半导体", "芯片"
        ])
        news_df = self._make_news_df("今日市场平稳")
        policy_focus = {"focus_type": "sector", "focus_value": "semiconductor"}

        concepts, keyword_mode, selection_mode = PolicyStrategy._select_policy_concepts(
            concept_df, news_df, policy_focus
        )

        assert selection_mode == "focus_aligned", f"Expected focus_aligned, got {selection_mode}"
        assert keyword_mode is True
        assert "半导体" in concepts
        assert "芯片" in concepts
        assert "AI手机" not in concepts

    def test_focus_aligned_unknown_focus_uses_raw_value(self):
        """When focus_value not in _FOCUS_ALIAS_KEYWORDS, falls back to raw value matching."""
        # "new_material" not in _FOCUS_ALIAS_KEYWORDS, so focus_aliases = ["new_material"]
        # match succeeds when concept name contains the raw focus_value
        concept_df = self._make_concept_df(["other_concept", "new_material_stock"])
        news_df = self._make_news_df("今日市场平稳")
        policy_focus = {"focus_type": "sector", "focus_value": "new_material"}

        concepts, keyword_mode, selection_mode = PolicyStrategy._select_policy_concepts(
            concept_df, news_df, policy_focus
        )

        assert selection_mode == "focus_aligned"
        assert keyword_mode is True
        assert "new_material_stock" in concepts

    def test_focus_aligned_empty_concept_df(self):
        """Empty concept_df returns empty list + keyword_fallback."""
        concept_df = pd.DataFrame(columns=["name"])
        news_df = self._make_news_df("半导体利好")
        policy_focus = {"focus_type": "sector", "focus_value": "semiconductor"}

        concepts, keyword_mode, selection_mode = PolicyStrategy._select_policy_concepts(
            concept_df, news_df, policy_focus
        )

        assert concepts == []
        assert selection_mode == "keyword_fallback"

    def test_focus_aligned_none_concept_df(self):
        """None concept_df returns empty list + keyword_fallback."""
        news_df = self._make_news_df("半导体利好")
        policy_focus = {"focus_type": "sector", "focus_value": "semiconductor"}

        concepts, keyword_mode, selection_mode = PolicyStrategy._select_policy_concepts(
            None, news_df, policy_focus
        )

        assert concepts == []
        assert selection_mode == "keyword_fallback"

    # --- news_matched cases (existing logic unchanged) ---

    def test_news_matched_exact_concept(self):
        """When news contains exact concept name, returns news_matched."""
        concept_df = self._make_concept_df(["半导体", "AI手机", "新能源"])
        news_df = self._make_news_df("半导体板块今日走强")

        concepts, keyword_mode, selection_mode = PolicyStrategy._select_policy_concepts(
            concept_df, news_df, None
        )

        assert selection_mode == "news_matched"
        assert keyword_mode is False
        assert "半导体" in concepts

    # --- keyword_fallback cases ---

    def test_keyword_fallback_no_focus(self):
        """When no news and no focus, returns keyword_fallback with first 5."""
        concept_df = self._make_concept_df(["阿尔茨海默概念", "AI手机", "阿里巴巴概念"])
        news_df = None

        concepts, keyword_mode, selection_mode = PolicyStrategy._select_policy_concepts(
            concept_df, news_df, None
        )

        assert selection_mode == "keyword_fallback"
        assert keyword_mode is True
        assert len(concepts) == 3

    # --- priority: news > keyword > focus > fallback ---

    def test_priority_news_over_keyword_over_focus(self):
        """Selection priority: news_matched > keyword_fallback > focus_aligned."""
        concept_df = self._make_concept_df(["半导体", "新能源"])
        news_df = self._make_news_df("半导体板块走强")
        policy_focus = {"focus_type": "sector", "focus_value": "new_energy"}

        concepts, keyword_mode, selection_mode = PolicyStrategy._select_policy_concepts(
            concept_df, news_df, policy_focus
        )

        assert selection_mode == "news_matched"


class TestBuildStockSelectionTag:
    """Test _build_stock_selection_tag with selection_mode parameter."""

    def test_focus_aligned_returns_policy_focus_aligned_tag(self):
        """When focus_aligned but not member, returns policy_focus_aligned."""
        tag = PolicyStrategy._build_stock_selection_tag(
            member_metrics={"is_member": False, "top_tier_hit": False},
            cross_hit_score=40.0,
            keyword_mode=True,
            selection_mode="focus_aligned",
        )
        assert tag == "policy_focus_aligned"

    def test_keyword_fallback_returns_keyword_fallback_tag(self):
        """When keyword_fallback and not member, returns policy_keyword_fallback."""
        tag = PolicyStrategy._build_stock_selection_tag(
            member_metrics={"is_member": False, "top_tier_hit": False},
            cross_hit_score=40.0,
            keyword_mode=True,
            selection_mode="keyword_fallback",
        )
        assert tag == "policy_keyword_fallback"

    def test_is_member_overrides_selection_mode(self):
        """When is_member=True, returns policy_core_member regardless of selection_mode."""
        tag = PolicyStrategy._build_stock_selection_tag(
            member_metrics={"is_member": True, "top_tier_hit": False},
            cross_hit_score=40.0,
            keyword_mode=True,
            selection_mode="focus_aligned",
        )
        assert tag == "policy_core_member"

    def test_top_tier_hit_overrides_everything(self):
        """When top_tier_hit=True, returns policy_top_stock."""
        tag = PolicyStrategy._build_stock_selection_tag(
            member_metrics={"is_member": False, "top_tier_hit": True},
            cross_hit_score=40.0,
            keyword_mode=True,
            selection_mode="keyword_fallback",
        )
        assert tag == "policy_top_stock"


class TestBuildTriggerReason:
    """Test _build_trigger_reason with selection_mode parameter."""

    def test_focus_aligned_returns_focus_aligned_reason(self):
        """policy_focus_aligned tag maps to policy_event_focus_aligned."""
        reason = PolicyStrategy._build_trigger_reason(
            keyword_mode=True,
            stock_selection_tag="policy_focus_aligned",
            concept_weight_bucket="concept_weight_unconfirmed",
            selection_mode="focus_aligned",
        )
        assert reason == "policy_event_focus_aligned"

    def test_keyword_fallback_returns_keyword_fallback_reason(self):
        """keyword_mode=True with keyword_fallback maps to policy_event_keyword_fallback."""
        reason = PolicyStrategy._build_trigger_reason(
            keyword_mode=True,
            stock_selection_tag="policy_keyword_fallback",
            concept_weight_bucket="concept_weight_unconfirmed",
            selection_mode="keyword_fallback",
        )
        assert reason == "policy_event_keyword_fallback"


class TestFocusAliasKeywords:
    """Test that _FOCUS_ALIAS_KEYWORDS covers expected focus values."""

    def test_semiconductor_has_expected_aliases(self):
        assert "半导体" in _FOCUS_ALIAS_KEYWORDS["semiconductor"]
        assert "芯片" in _FOCUS_ALIAS_KEYWORDS["semiconductor"]

    def test_new_energy_has_expected_aliases(self):
        assert "新能源" in _FOCUS_ALIAS_KEYWORDS["new_energy"]
        assert "光伏" in _FOCUS_ALIAS_KEYWORDS["new_energy"]

    def test_robot_has_expected_aliases(self):
        assert "机器人" in _FOCUS_ALIAS_KEYWORDS["robot"]

    def test_low_altitude_has_expected_aliases(self):
        assert "低空" in _FOCUS_ALIAS_KEYWORDS["low_altitude"]
        assert "无人机" in _FOCUS_ALIAS_KEYWORDS["low_altitude"]
