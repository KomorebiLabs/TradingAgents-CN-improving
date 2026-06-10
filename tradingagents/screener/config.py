from copy import deepcopy
from dataclasses import dataclass
import os
from typing import Any, Dict

from tradingagents.default_config import DEFAULT_CONFIG

# Load .env as early as possible so all downstream imports see correct env vars
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


# Map .env keys -> config keys (env var name -> (config_key, default))
_ENV_LLM_MAPPING = {
    "LLM_PROVIDER": ("llm_provider", "openai"),
    "DEEPSEEK_API_KEY": ("llm_api_key", None),
    "DEEPSEEK_API_BASE": ("backend_url", "https://api.deepseek.com"),
    "DEEP_THINK_LLM": ("deep_think_llm", "deepseek-v4-flash"),
    "QUICK_THINK_LLM": ("quick_think_llm", "deepseek-v4-flash"),
}


def _load_llm_config_from_env() -> Dict[str, Any]:
    """Load LLM config from environment variables, overriding defaults."""
    result = {}
    for env_key, (config_key, default) in _ENV_LLM_MAPPING.items():
        value = os.environ.get(env_key)
        if value is not None:
            result[config_key] = value.strip()
        elif config_key not in result:
            result[config_key] = default
    return result


SCREENER_UNIVERSE: Dict[str, Dict[str, Any]] = {
    # Legacy modes (keep for backward compatibility)
    "MVP": {
        "profile": "MVP",
        "source": "index_universe_baseline",
        "index_codes": ["000300", "000905"],
        "expansion_mode": "index_union",
        "cache_key": "mvp_index_union",
        "source_signature": "index_universe_baseline:000300,000905:index_union",
        "constituent_expansion_ready": False,
        "stagea_max_input": 1000,
        "stageb_max_input": 200,
    },
    "EXTENDED": {
        "profile": "EXTENDED",
        "source": "index_universe_growth",
        "index_codes": ["000300", "000905", "399006", "000688"],
        "expansion_mode": "index_union_plus_growth",
        "cache_key": "extended_index_union_plus_growth",
        "source_signature": "index_universe_growth:000300,000905,399006,000688:index_union_plus_growth",
        "constituent_expansion_ready": False,
        "stagea_max_input": 2000,
        "stageb_max_input": 300,
    },
    "EXPERIMENTAL": {
        "profile": "EXPERIMENTAL",
        "source": "index_universe_experimental",
        "index_codes": ["000300", "000905", "399006", "000688", "000852"],
        "expansion_mode": "experimental_index_union",
        "cache_key": "experimental_index_union",
        "source_signature": "index_universe_experimental:000300,000905,399006,000688,000852:experimental_index_union",
        "constituent_expansion_ready": True,
        "stagea_max_input": 3000,
        "stageb_max_input": 400,
    },
    # New Plan 5 modes
    "FULL": {
        "profile": "FULL",
        "source": "index_universe_full",
        "index_codes": ["000300", "000905", "399006", "000688", "000852"],
        "expansion_mode": "full_index_union",
        "cache_key": "full_index_union",
        "source_signature": "index_universe_full:000300,000905,399006,000688,000852:full_index_union",
        "constituent_expansion_ready": True,
        "stagea_max_input": 4000,
        "stageb_max_input": 500,
    },
    "FOCUSED": {
        "profile": "FOCUSED",
        "source": "focused_universe",
        "focus_type": "index",
        "focus_value": "000300",
        "expansion_mode": "focused",
        "cache_key": "focused_universe",
        "source_signature": "focused_universe:index:000300:focused",
        "constituent_expansion_ready": False,
        "stagea_max_input": 500,
        "stageb_max_input": 100,
    },
    "CUSTOM": {
        "profile": "CUSTOM",
        "source": "custom_tickers",
        "expansion_mode": "custom",
        "cache_key": "custom_tickers",
        "source_signature": "custom_tickers:user_input:custom",
        "constituent_expansion_ready": False,
        "stagea_max_input": 100,
        "stageb_max_input": 50,
    },
}


SCREENER_CONFIG: Dict[str, Any] = {
    "mode": "MVP",
    "run_time": {
        "earliest": "16:30",
        "latest_next_day": "09:00",
        "allow_weekend": False,
        "allow_non_trading_day_override": False,
        "allow_experimental_intraday": True,
        "max_data_age_days": 2,
    },
    "universe": {
        "profile": "MVP",
        "mode_profile_map": {
            # Legacy modes
            "MVP": "MVP",
            "EXTENDED": "EXTENDED",
            "EXPERIMENTAL": "EXPERIMENTAL",
            # New Plan 5 modes
            "FULL": "FULL",
            "FOCUSED": "FOCUSED",
            "CUSTOM": "CUSTOM",
        },
        # Default stage limits (can be overridden by CLI)
        "stagea_max_input_default": 1000,
        "stageb_max_input_default": 200,
    },
    "candidates": {
        "max_output": 3,
        "max_output_extended": 5,
        "same_sector_limit": 2,
    },
    "anti_ban": {
        "base_interval": 1.0,
        "burst_threshold": 10,
        "burst_pause": 2.0,
        "failure_penalty": 1.5,
        "soft_rpm_limit": 30,
    },
    "vendors": {
        "hist_primary": "tencent",
        "hist_secondary": "sina",
        "hist_tertiary": "baostock",
        "spot_primary": "tencent",
        "spot_secondary": "sina",
        "concept_primary": "ths",
        "concept_secondary": "sina",
        "industry_primary": "ths",
        "fund_flow_primary": "ths",
        "fund_flow_secondary": "em",  # H4: was baostock which returned None; now use AkShare EastMoney
        "index_primary": "sina",
        "index_secondary": "tencent",
        "spoof_browser_headers": True,
        "enable_yfinance_backup": True,
    },
    "strategies": {
        "technical": {
            "lookback_days": 100,
            "top_candidates_for_history": 100,
            "top_output": 200,  # No artificial cap — pass all scored cards to merger
            "weight": 0.40,
            "allow_yfinance_fallback": True,
            "thresholds": {
                "signal_consistency_low": 45.0,
                # --- scoring bases ---
                "trend_alignment_base": 40.0,
                "structure_risk_base": 68.0,
                "volume_confirmation_base": 42.0,
                "breakout_quality_base": 38.0,
                "volume_divergence_base": 62.0,
                "signal_consistency_base": 40.0,
                "hist_rows_minimum": 30,
                # --- scoring weights ---
                "trend_alignment_weight": 0.22,
                "momentum_weight": 0.18,
                "drawdown_resilience_weight": 0.14,
                "volatility_weight": 0.10,
                "trend_consistency_weight": 0.12,
                "structure_risk_weight": 0.11,
                "volume_confirmation_weight": 0.07,
                "breakout_quality_weight": 0.04,
                "divergence_weight": 0.02,
                # --- score limits ---
                "score_ceiling": 95.0,
                "score_floor": 20.0,
                # --- fund-flow bonus ---
                "fund_flow_bonus": 3.0,
                "hist_rows_penalty": 10.0,
            },
        },
        "policy": {
            "max_concepts": 5,
            "max_stocks_per_concept": 50,
            "weight": 0.30,
            "thresholds": {
                "concept_conviction_low": 52.0,
                # --- scoring bases ---
                "concept_heat_base": 50.0,
                "concept_heat_per_hit": 8.0,
                "stock_strength_base": 50.0,
                "board_leadership_base": 55.0,
                "relative_rank_base": 42.0,
                "relative_rank_fallback": 40.0,
                "liquidity_base": 68.0,
                "liquidity_floor": 40.0,
                "liquidity_decrement_per_rank": 2.0,
                # --- inline scores ---
                "cross_hit_in_universe": 85.0,
                "cross_hit_not_in_universe": 40.0,
                "source_quality_news": 75.0,
                "source_quality_no_news": 45.0,
                # --- composite value ---
                "member_composite_base": 45.0,
                "member_composite_floor": 20.0,
                "member_composite_ceiling": 100.0,
            },
        },
        "smart_money": {
            "institutional_days": ["5", "10", "30"],
            "north_flow_limit": 50,
            "earnings_growth_min": 50,
            "top_output": 200,  # No artificial cap — pass all scored cards to merger
            "weight": 0.30,
            "thresholds": {
                "quality_stability_low": 48.0,
                # --- risk flag thresholds (A2: configurable) ---
                "hist_rows_minimum": 20,
                "deep_drawdown_pct": 22.0,
                "high_volatility_pct": 55.0,
                "overheated_valuation_mismatch_popularity": 80.0,
                "overheated_valuation_mismatch_valuation": 45.0,
                "heat_quality_gap_wide": 22.0,
                "flow_continuity_weak": 50.0,
                "continuity_fragile": 48.0,
                # --- scoring bases ---
                "tick_base": 45.0,
                "tick_no_type_base": 50.0,
                "tick_large_trade_threshold": 100.0,
                "tick_large_trade_bonus_per": 2.0,
                "popularity_base": 45.0,
                "popularity_no_value_base": 50.0,
                "tick_persistence_base": 45.0,
                "tick_persistence_no_type_base": 50.0,
                "tick_persistence_streak_mult": 4.0,
                "valuation_neutral": 55.0,
                "institutional_base": 45.0,
                "institutional_no_match_base": 48.0,
                "lhbc_base": 42.0,
                "joint_quality_base": 45.0,
                "multi_day_base": 42.0,
                "risk_constraint_base": 62.0,
                "lookback_days": 140,
            },
        },
    },
    "cache": {
        "enabled": True,
        "cache_ttl_minutes": 720,  # 12 hours = 720 minutes; unified unit (P-5.1 fix)
    },
    "a0_probe": {
        "enable_live_probes": True,
        "cache_ttl_minutes": 60,
        "sample_symbol": "000001",
        "sample_hist_start": "20250101",
        "sample_hist_end": "20250110",
    },
    "deep_analyzer": {
        "enable_real_deep_analysis": True,  # H3 FIX: real analysis enabled by default
        "max_stocks": 3,
        "delay_between_stocks": 2.0,
        "retry_on_failure": True,
        "max_retries": 1,
    },
    "fallbacks": {
        "prefer_cn_primary": True,
        "enable_yfinance_backup": True,
    },
    "conflict_priority": {
        # --- spread tiers ---
        "aligned_spread_max": 6.0,
        "moderate_spread_max": 12.0,
        "high_spread_max": 20.0,
        # --- severity thresholds ---
        "technical_veto_min_severity": 4,
        "weak_policy_stress_min_severity": 3,
        "speculative_technical_min_severity": 3,
        # --- tier-specific integer bonus/penalty ---
        "aligned_bonus_int": 2,
        "moderate_penalty_int": 1,
        "high_penalty_int": 2,
        "severe_penalty_int": 3,
        # --- conflict-rule bias ---
        "technical_veto_bias": -4,
        "semantic_consensus_bias": 3,
        "weak_policy_stress_bias": -3,
        "speculative_flow_bias": -2,
        "aligned_support_bias": 1,
        "severe_conflict_bias": -2,
    },
    # --- merger scoring multipliers (A2: moved from hardcoded to config) ---
    "merger_thresholds": {
        "resonance_bonus_per_source": 5,
        "confidence_all_verified_bonus": 5,
        "risk_flag_penalty_mult": 3,
        "score_confidence_mult": 0.85,
        "semantic_bonus_mult": 1.5,
        "conflict_penalty_mult": 1.5,
    },
}


SCREENER_THRESHOLDS: Dict[str, Any] = {
    "low_turnover_rate": 2.0,
    "low_float_market_cap_billion": 30.0,
    "near_limit_up_pct": 9.9,  # P5-3: extreme price anomaly upper bound
    "near_limit_down_pct": -9.9,
    "extreme_pe_upper": 150.0,
    # --- merger drop-score floors (A2: migrated from hardcoded in merger.py) ---
    "drop_speculative_score_floor": 78.0,
    "drop_policy_speculative_floor": 82.0,
    "drop_weak_policy_floor": 72.0,
    "drop_weak_policy_stress_floor": 74.0,
    "drop_technical_veto_floor": 84.0,
    "drop_weak_policy_confidence_floor": 70.0,
}


@dataclass
class DeepAnalyzerConfig:
    max_stocks: int = 3
    delay_between_stocks: float = 2.0
    retry_on_failure: bool = True
    max_retries: int = 1


def build_graph_config(overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Build a TradingAgentsGraph-compatible config dict.

    LLM settings are loaded from environment variables (DEEPSEEK_API_KEY,
    DEEPSEEK_API_BASE, LLM_PROVIDER, etc.) so that the deep_analyzer
    uses the same provider as the rest of the project.
    """
    config = deepcopy(DEFAULT_CONFIG)
    # Override LLM settings from environment
    config.update(_load_llm_config_from_env())
    if overrides:
        config.update(overrides)
    return config
