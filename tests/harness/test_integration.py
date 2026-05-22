"""Tests for harness integration — full pipeline from Skills to CostTracker."""
import pytest
from tradingagents.screener.models import SignalCard, SignalEvidence
from tradingagents.harness import (
    CostTracker,
    TokenCountingCallback,
    UsageSnapshot,
    SkillInjector,
    ANALYST_SKILL_MAPPING,
    ScreenerContextInjector,
)
from tradingagents.harness.skills import load_skill_registry
from pathlib import Path


class FakeLlmOutputResponse:
    """Mock LangChain LLM response with usage metadata."""
    def __init__(self, usage_metadata):
        self.usage_metadata = usage_metadata


class FakeLlmOutputResponseLegacy:
    """Mock LangChain LLM response with llm_output (legacy)."""
    def __init__(self, llm_output):
        self.llm_output = llm_output


def test_full_pipeline_cost_tracker():
    """Verify CostTracker accumulates across simulated LLM calls."""
    tracker = CostTracker()
    cb = TokenCountingCallback(tracker)

    cb.on_llm_end(FakeLlmOutputResponse({"input_tokens": 500, "output_tokens": 250}))
    cb.on_llm_end(FakeLlmOutputResponse({"input_tokens": 300, "output_tokens": 150}))

    assert tracker.total.input_tokens == 800
    assert tracker.total.output_tokens == 400
    assert tracker.total.total_tokens == 1200


def test_usage_snapshot_model():
    """Verify UsageSnapshot calculates total_tokens correctly."""
    snapshot = UsageSnapshot(input_tokens=1000, output_tokens=500)
    assert snapshot.total_tokens == 1500


def test_skill_injector_loads_bundled_skills():
    """Verify SkillInjector loads all bundled skills correctly."""
    injector = SkillInjector()
    for analyst_type, skill_names in ANALYST_SKILL_MAPPING.items():
        section = injector.build_skill_section(analyst_type)
        if skill_names:
            assert len(section) > 0, f"No section built for analyst {analyst_type}"


def test_skill_injector_respects_analyst_mapping():
    """Verify each analyst type has correct number of skills mapped."""
    assert len(ANALYST_SKILL_MAPPING["market"]) == 4
    assert len(ANALYST_SKILL_MAPPING["news"]) == 3
    assert len(ANALYST_SKILL_MAPPING["fundamentals"]) == 3
    assert len(ANALYST_SKILL_MAPPING["social"]) == 2


def test_screener_context_injector_renders_all_scopes():
    """Verify ScreenerContextInjector renders all 5 injection scopes."""
    card = SignalCard(
        ticker="600519.SH",
        raw_code="600519",
        exchange="SH",
        company_name="贵州茅台",
        trade_date="2025-01-10",
        sector_tags=["白酒"],
        concept_tags=["政策龙头", "capital_quality_high"],
        strategy_sources=["technical", "policy", "smart_money"],
        signal_breakdown=[
            SignalEvidence(
                strategy="technical",
                score=82.0,
                reason="",
                raw_metrics={"rsi": 65, "macd_signal": "golden_cross"},
            ),
            SignalEvidence(
                strategy="smart_money",
                score=88.0,
                reason="",
                raw_metrics={"heat_quality_gap_score": 15, "capital_quality_weight": 0.9},
            ),
        ],
        evidence_snapshot={"capital_quality_tag": "capital_quality_high"},
        trigger_reason="policy_top_stock",
        initial_confidence=85.0,
        risk_flags=["trend_structure_extended"],
        screening_score=88.0,
    )
    injector = ScreenerContextInjector()
    ctx = injector.build_context(card)

    # Scope 1: Ticker
    assert "600519.SH" in ctx
    # Scope 2: Score
    assert "88" in ctx
    # Scope 3: Tags
    assert "白酒" in ctx
    assert "政策龙头" in ctx
    # Scope 4: Technical Metrics
    assert "Technical Metrics" in ctx
    assert "rsi" in ctx
    # Scope 5: Capital Quality
    assert "Capital Quality" in ctx
    assert "capital_quality_high" in ctx
    # Scope 6: Risk Flags
    assert "Risk Flags" in ctx
    assert "trend_structure_extended" in ctx


def test_screener_context_injector_handles_empty_card():
    """Verify ScreenerContextInjector handles minimal SignalCard gracefully."""
    card = SignalCard(
        ticker="000001.SZ",
        raw_code="000001",
        exchange="SZ",
        company_name="平安银行",
        trade_date="2025-01-10",
        sector_tags=[],
        concept_tags=[],
        strategy_sources=[],
        signal_breakdown=[],
        trigger_reason="",
        initial_confidence=50.0,
        risk_flags=[],
        screening_score=50.0,
    )
    injector = ScreenerContextInjector()
    ctx = injector.build_context(card)
    assert "Screener Scan Results" in ctx
    assert "000001" in ctx


def test_combined_skill_and_context_in_prompt():
    """Verify Skill + Screener Context can be combined into a single prompt."""
    # Build Screener Context
    card = SignalCard(
        ticker="300750.SZ",
        raw_code="300750",
        exchange="SZ",
        company_name="CATL",
        trade_date="2025-01-10",
        sector_tags=["xin-nengyuan"],
        concept_tags=["dongli-dianchi"],
        strategy_sources=["technical", "smart_money"],
        signal_breakdown=[
            SignalEvidence(
                strategy="technical",
                score=80.0,
                reason="",
                raw_metrics={"rsi": 70, "bollinger_position": 0.8},
            ),
        ],
        trigger_reason="technical_breakout",
        initial_confidence=75.0,
        risk_flags=[],
        screening_score=80.0,
    )
    sc_injector = ScreenerContextInjector()
    sc_ctx = sc_injector.build_context(card)

    # Build Skill Section
    skill_injector = SkillInjector()
    skill_section = skill_injector.build_skill_section("market")

    # Combine into prompt
    base_prompt = "You are a market analyst."
    combined = base_prompt + "\n\n" + sc_ctx + "\n\n" + skill_section

    assert "You are a market analyst." in combined
    assert "300750" in combined
    assert "Screener Scan Results" in combined
    assert "Technical Metrics" in combined
    assert len(skill_section) > 0


def test_cost_tracker_with_legacy_llm_output():
    """Verify TokenCountingCallback handles legacy LangChain llm_output format."""
    tracker = CostTracker()
    cb = TokenCountingCallback(tracker)

    response = FakeLlmOutputResponseLegacy(
        llm_output={"usage": {"prompt_tokens": 800, "completion_tokens": 400}}
    )
    cb.on_llm_end(response)
    assert tracker.total.input_tokens == 800
    assert tracker.total.output_tokens == 400


def test_load_skill_registry_finds_all_bundled_skills():
    """Verify bundled skill registry contains all expected skills via name lookup."""
    bundled_dir = Path(__file__).parent.parent.parent / "tradingagents" / "harness" / "skills" / "bundled"
    if not bundled_dir.exists():
        pytest.skip("bundled skills directory not found")

    registry = load_skill_registry(bundled_dir)
    skills = registry.list_skills()

    # Verify all skill names in ANALYST_SKILL_MAPPING can be found by name
    all_mapped_names = set()
    for names in ANALYST_SKILL_MAPPING.values():
        all_mapped_names.update(names)

    found_by_name = registry.get_skills_by_names(list(all_mapped_names))
    assert len(found_by_name) == len(all_mapped_names), (
        f"Expected all {len(all_mapped_names)} mapped skills to be found by name, "
        f"but only found {len(found_by_name)}. Missing: {all_mapped_names - {s.name for s in found_by_name}}"
    )
