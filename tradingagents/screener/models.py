from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class DataFreshness(BaseModel):
    source: str
    trade_date: Optional[str] = None
    fetched_at: str
    status: Literal["fresh", "stale", "missing", "estimated"]
    notes: str = ""


class SignalEvidence(BaseModel):
    strategy: Literal["technical", "policy", "smart_money"]
    score: float
    rank_in_strategy: Optional[int] = None
    reason: str
    raw_metrics: Dict[str, Any] = Field(default_factory=dict)
    freshness: List[DataFreshness] = Field(default_factory=list)
    degraded: bool = False
    degradation_reason: str = ""


class SignalCard(BaseModel):
    ticker: str
    raw_code: str
    exchange: str
    company_name: str
    trade_date: str
    sector_tags: List[str] = Field(default_factory=list)
    concept_tags: List[str] = Field(default_factory=list)
    strategy_sources: List[str] = Field(default_factory=list)
    signal_breakdown: List[SignalEvidence] = Field(default_factory=list)
    trigger_reason: str
    initial_confidence: float
    risk_flags: List[str] = Field(default_factory=list)
    screening_score: float
    screening_rank: Optional[int] = None
    data_source_verified: bool = False
    recommendation_eligible: bool = False
    verified_modules: List[str] = Field(default_factory=list)
    missing_required_modules: List[str] = Field(default_factory=list)
    degraded_modules: List[str] = Field(default_factory=list)
    verified_strategy_count: int = 0
    latest_required_data_date: Optional[str] = None
    max_required_data_lag_days: Optional[int] = None
    stale_required_sources: List[str] = Field(default_factory=list)
    evidence_snapshot: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("initial_confidence", "screening_score")
    @classmethod
    def validate_percent_bounds(cls, value: float) -> float:
        if value < 0 or value > 100:
            raise ValueError("score values must be within 0-100")
        return value


class ScreeningResult(BaseModel):
    run_id: str
    # P5-1: Extended mode literals to include FULL/FOCUSED/CUSTOM
    mode: Literal["MVP", "EXTENDED", "EXPERIMENTAL", "FULL", "FOCUSED", "CUSTOM"]
    trade_date: str
    started_at: str
    completed_at: str
    universe_size: int
    universe_metadata: Dict[str, Any] = Field(default_factory=dict)
    candidates: List[SignalCard] = Field(default_factory=list)
    dropped_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    strategy_status: Dict[str, str] = Field(default_factory=dict)
    data_issues: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    run_status: Literal[
        "COMPLETED",
        "NO_CANDIDATE_VALID",
        "NO_CANDIDATE_DEGRADED",
        "PIPELINE_FAILED",
    ] = "COMPLETED"

    @model_validator(mode="after")
    def infer_initial_run_status(self):
        """Make status correct before JSON/Markdown artifacts are rendered."""
        if self.candidates:
            self.run_status = "COMPLETED"
        elif self.metrics.get("pipeline_failed"):
            self.run_status = "PIPELINE_FAILED"
        elif any(status != "ready" for status in self.strategy_status.values()):
            self.run_status = "NO_CANDIDATE_DEGRADED"
        else:
            self.run_status = "NO_CANDIDATE_VALID"
        return self


class DeepAnalysisResult(BaseModel):
    signal_card: SignalCard
    success: bool
    execution_status: Literal[
        "GRAPH_COMPLETED",
        "DRY_RUN_REQUESTED",
        "FALLBACK_COMPLETED",
        "FAILED",
    ] = "FAILED"
    final_decision: Optional[str] = None
    elapsed_seconds: float
    token_usage: Dict[str, int] = Field(
        default_factory=lambda: {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        description="LLM token consumption for this analysis run",
    )
    error: str = ""
    final_state_summary: Dict[str, Any] = Field(default_factory=dict)


class ScreenerMetrics(BaseModel):
    run_id: str
    # P5-1: Extended mode literals to include FULL/FOCUSED/CUSTOM
    mode: Literal["MVP", "EXTENDED", "EXPERIMENTAL", "FULL", "FOCUSED", "CUSTOM"]
    universe_size: int = 0
    strategy_a_candidates: int = 0
    strategy_b_candidates: int = 0
    strategy_c_candidates: int = 0
    final_candidates: int = 0
    api_requests_total: int = 0
    api_requests_failed: int = 0
    degraded_strategies: List[str] = Field(default_factory=list)
    elapsed_seconds_total: float = 0.0
    llm_calls_total: int = 0
    # A5: expanded fields
    threshold_snapshot: Dict[str, Any] = Field(default_factory=dict)
    conflict_priority_snapshot: Dict[str, Any] = Field(default_factory=dict)
    merger_threshold_snapshot: Dict[str, Any] = Field(default_factory=dict)
    effective_config_used: Dict[str, Any] = Field(default_factory=dict)
