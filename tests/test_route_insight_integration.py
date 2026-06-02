"""
Route Insight 集成测试。

验证 Route Insight 与现有系统的集成：
1. reflect_portfolio_manager 调用链
2. StructuredMemory 存储/检索
3. 端到端流程验证
"""

import pytest
from unittest.mock import MagicMock, Mock, patch
from datetime import datetime
from typing import Dict, List, Any

# 导入被测试的类
from tradingagents.graph.reflection import Reflector
from tradingagents.agents.utils.memory import StructuredMemory


# ============================================================================
# 测试数据 Fixtures
# ============================================================================

@pytest.fixture
def mock_llm():
    """Mock LLM用于测试."""
    llm = MagicMock()
    llm.invoke = MagicMock(return_value=MagicMock(content="Mocked LLM response"))
    return llm


@pytest.fixture
def reflector(mock_llm):
    """创建Reflector实例."""
    return Reflector(quick_thinking_llm=mock_llm)


@pytest.fixture
def complete_current_state():
    """完整的当前状态（包含所有必要字段）."""
    return {
        "orchestration": {
            "stage": "risk",
            "phase": "risk",
            "next_stage": "completed",
            "completed": True,
            "final_route": "compression_handoff",
            "final_reason": "Context exceeded threshold of 10000 tokens",
            "compression_required": True,
            "compression_notes": "Compressed market_report, sentiment_report, news_report, fundamentals_report",
            "event_trail": [
                {
                    "node": "analyst_market",
                    "stage": "analyst",
                    "phase": "analyst_market",
                    "next_stage": "research",
                    "compression_triggered": False,
                    "context_estimate": 1000,
                    "timestamp": "2025-01-01T10:00:00",
                },
                {
                    "node": "research_bull",
                    "stage": "research",
                    "phase": "research_bull",
                    "next_stage": "research",
                    "compression_triggered": True,
                    "context_estimate": 5000,
                    "timestamp": "2025-01-01T10:05:00",
                },
                {
                    "node": "research_bear",
                    "stage": "research",
                    "phase": "research_bear",
                    "next_stage": "trader",
                    "compression_triggered": True,
                    "context_estimate": 6000,
                    "timestamp": "2025-01-01T10:10:00",
                },
                {
                    "node": "trader",
                    "stage": "trader",
                    "phase": "trader",
                    "next_stage": "risk",
                    "compression_triggered": True,
                    "context_estimate": 8000,
                    "timestamp": "2025-01-01T10:15:00",
                },
                {
                    "node": "risk",
                    "stage": "risk",
                    "phase": "risk",
                    "next_stage": "completed",
                    "compression_triggered": True,
                    "context_estimate": 10000,
                    "timestamp": "2025-01-01T10:20:00",
                },
            ],
        },
        "ticker_info": {
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "segment": "cn_chinext",
            "style_bucket": "growth",
            "selected_analysts": ["fundamental", "technical"],
            "skills": ["cn_macro_news"],
            "trade_date": "2025-01-01",
        },
        "market_report": "Market is volatile today with significant fluctuations in tech sector.",
        "sentiment_report": "Sentiment is mixed with positive bias towards large-cap tech.",
        "news_report": "Tech sector showing strength with AI-related stocks outperforming.",
        "fundamentals_report": "Strong quarterly results with revenue growth of 8% YoY.",
        "investment_debate_state": {
            "bull_history": "Bull case emphasizes AI growth potential and services revenue.",
            "bear_history": "Bear case focuses on smartphone market saturation and competition.",
            "judge_decision": "Market intelligence suggests cautious optimism.",
        },
        "risk_debate_state": {
            "judge_decision": "Risk-adjusted return potential justifies moderate position.",
        },
        "trader_investment_plan": "BUY AAPL with 5% position size, target price $250.",
    }


@pytest.fixture
def portfolio_manager_memory():
    """创建Portfolio Manager记忆."""
    memory = StructuredMemory(name="test_portfolio_manager_memory")
    return memory


@pytest.fixture
def route_memory():
    """创建Route记忆."""
    memory = StructuredMemory(name="test_route_memory")
    return memory


# ============================================================================
# 测试类: reflect_portfolio_manager 调用链验证
# ============================================================================

class TestReflectPortfolioManagerIntegration:
    """测试 reflect_portfolio_manager 调用链."""

    def test_portfolio_manager_basic_flow(self, reflector, complete_current_state, portfolio_manager_memory):
        """测试 portfolio_manager 基本流程."""
        returns_losses = "Portfolio returned 5.2% over the period. Risk-adjusted return was positive."

        # 调用 reflect_portfolio_manager
        reflector.reflect_portfolio_manager(
            current_state=complete_current_state,
            returns_losses=returns_losses,
            portfolio_manager_memory=portfolio_manager_memory,
            route_memory=None,  # 暂不测试route_memory
        )

        # 验证记忆被添加
        assert len(portfolio_manager_memory.documents) == 1
        # 验证内容包含市场信息（portfolio manager关注市场分析）
        assert "Market" in portfolio_manager_memory.documents[0]

    def test_portfolio_manager_with_route_memory(self, reflector, complete_current_state, portfolio_manager_memory, route_memory):
        """测试带route_memory的portfolio_manager流程."""
        returns_losses = "Portfolio returned 3.8% with low volatility."

        # 调用 reflect_portfolio_manager（带route_memory）
        reflector.reflect_portfolio_manager(
            current_state=complete_current_state,
            returns_losses=returns_losses,
            portfolio_manager_memory=portfolio_manager_memory,
            route_memory=route_memory,
        )

        # 验证两个记忆都被添加
        assert len(portfolio_manager_memory.documents) == 1
        assert len(route_memory.documents) == 1

        # 验证route_memory包含洞察信息
        route_doc = route_memory.documents[0]
        assert "compression" in route_doc.lower() or "route" in route_doc.lower()

    def test_portfolio_manager_metadata_structure(self, reflector, complete_current_state, portfolio_manager_memory, route_memory):
        """测试metadata结构完整性."""
        returns_losses = "Portfolio returned 7.1% outperforming benchmark by 2%."

        reflector.reflect_portfolio_manager(
            current_state=complete_current_state,
            returns_losses=returns_losses,
            portfolio_manager_memory=portfolio_manager_memory,
            route_memory=route_memory,
        )

        # 验证metadata结构
        route_metadata = route_memory.metadata[0]

        # 验证必需字段
        required_fields = [
            "segment", "style_bucket", "final_route", "route_category",
            "compression_triggered", "compression_rate", "total_events",
            "bottleneck_stages", "efficiency_score",
        ]

        for field in required_fields:
            assert field in route_metadata, f"Missing field: {field}"

        # 验证数值字段类型
        assert isinstance(route_metadata["efficiency_score"], (int, float))
        assert isinstance(route_metadata["total_events"], int)
        assert isinstance(route_metadata["compression_rate"], float)

    def test_portfolio_manager_route_insight_quality(self, reflector, complete_current_state, route_memory):
        """测试路由洞察质量."""
        returns_losses = "Strong performance with 10% returns."

        reflector.reflect_portfolio_manager(
            current_state=complete_current_state,
            returns_losses=returns_losses,
            portfolio_manager_memory=MagicMock(),  # 不需要
            route_memory=route_memory,
        )

        # 获取生成的洞察
        recommendation = route_memory.recommendations[0]

        # 验证洞察不为空
        assert recommendation is not None
        assert len(recommendation) > 0

        # 验证洞察包含关键信息
        recommendation_lower = recommendation.lower()
        assert "route" in recommendation_lower or "compression" in recommendation_lower


# ============================================================================
# 测试类: StructuredMemory 存储/检索验证
# ============================================================================

class TestStructuredMemoryStorageRetrieval:
    """测试StructuredMemory存储和检索功能."""

    def test_add_situation_with_metadata(self):
        """测试添加带metadata的情况."""
        memory = StructuredMemory(name="test_memory")

        memory.add_situation(
            situation="Test situation about AAPL",
            recommendation="Buy based on strong fundamentals",
            metadata={
                "segment": "cn_chinext",
                "style_bucket": "growth",
                "final_route": "compression_handoff",
                "route_category": "complex",
                "compression_triggered": True,
                "compression_rate": 0.6,
                "decision_quality": "good",
                "trade_date": "2025-01-01",
                "ticker": "AAPL",
            },
        )

        assert len(memory.documents) == 1
        assert len(memory.metadata) == 1
        assert memory.metadata[0]["segment"] == "cn_chinext"

    def test_structured_index_creation(self):
        """测试结构化索引创建."""
        memory = StructuredMemory(name="test_memory")

        # 添加多个记忆
        for i in range(5):
            memory.add_situation(
                situation=f"Test situation {i}",
                recommendation=f"Test recommendation {i}",
                metadata={
                    "segment": f"segment_{i % 3}",
                    "style_bucket": f"style_{i % 2}",
                    "route_category": "normal",
                },
            )

        # 验证结构化索引已创建
        assert "segment" in memory._structured_index
        assert "style_bucket" in memory._structured_index
        assert "route_category" in memory._structured_index

    def test_structured_query_by_segment(self):
        """测试按segment查询."""
        memory = StructuredMemory(name="test_memory")

        # 添加不同segment的记忆
        segments = ["cn_star", "cn_chinext", "cn_star", "cn_main_board"]
        for i, seg in enumerate(segments):
            memory.add_situation(
                situation=f"Situation {i}",
                recommendation=f"Recommendation {i}",
                metadata={
                    "segment": seg,
                    "route_category": "normal",
                },
            )

        # 查询cn_star
        results = memory.get_memories(
            current_situation="test query",
            n_matches=10,
            filters={"segment": ["cn_star"]},
        )

        # 验证结果
        assert len(results) == 2
        for result in results:
            assert result["metadata"]["segment"] == "cn_star"

    def test_structured_query_by_multiple_filters(self):
        """测试多条件查询."""
        memory = StructuredMemory(name="test_memory")

        # 添加记忆
        memory.add_situation(
            situation="Situation 1",
            recommendation="Recommendation 1",
            metadata={
                "segment": "cn_star",
                "style_bucket": "growth",
                "route_category": "normal",
            },
        )
        memory.add_situation(
            situation="Situation 2",
            recommendation="Recommendation 2",
            metadata={
                "segment": "cn_star",
                "style_bucket": "value",
                "route_category": "normal",
            },
        )

        # 按segment查询
        results = memory.get_memories(
            current_situation="test",
            n_matches=10,
            filters={"segment": "cn_star"},
        )

        assert len(results) == 2

    def test_export_memories(self):
        """测试导出记忆."""
        memory = StructuredMemory(name="test_memory")

        # 添加记忆
        memory.add_situation(
            situation="Test situation",
            recommendation="Test recommendation",
            metadata={"segment": "cn_star", "route_category": "normal"},
        )

        # 导出
        exported = memory.export_memories()

        # 验证
        assert len(exported) == 1
        assert "metadata" in exported[0]
        assert exported[0]["metadata"]["segment"] == "cn_star"


# ============================================================================
# 测试类: 端到端流程验证
# ============================================================================

class TestEndToEndFlow:
    """端到端流程验证."""

    def test_full_trading_cycle_with_reflection(self, reflector, complete_current_state):
        """测试完整的交易周期包含反思."""
        # 1. 创建记忆
        portfolio_memory = StructuredMemory(name="portfolio")
        route_memory = StructuredMemory(name="route")

        # 2. 模拟交易决策
        returns_losses = "Trade completed with 4.5% profit."

        # 3. 执行反思
        reflector.reflect_portfolio_manager(
            current_state=complete_current_state,
            returns_losses=returns_losses,
            portfolio_manager_memory=portfolio_memory,
            route_memory=route_memory,
        )

        # 4. 验证记忆存储
        assert len(portfolio_memory.documents) == 1
        assert len(route_memory.documents) == 1

        # 5. 获取统计
        route_stats = route_memory.get_route_statistics()
        assert route_stats["total_memories"] == 1

        # 6. 查询历史
        insights = route_memory.get_memories(
            current_situation="AAPL trading",
            n_matches=1,
        )
        assert len(insights) == 1

    def test_multiple_trades_accumulation(self, reflector, complete_current_state):
        """测试多次交易记忆累积."""
        route_memory = StructuredMemory(name="route")
        portfolio_memory = StructuredMemory(name="portfolio")

        # 模拟多次交易
        trade_results = [
            "Trade 1: 3.2% profit",
            "Trade 2: -1.5% loss",
            "Trade 3: 5.8% profit",
        ]

        for result in trade_results:
            # 修改state中的ticker以模拟不同交易
            state = dict(complete_current_state)
            state["ticker_info"] = dict(complete_current_state["ticker_info"])

            reflector.reflect_portfolio_manager(
                current_state=state,
                returns_losses=result,
                portfolio_manager_memory=portfolio_memory,
                route_memory=route_memory,
            )

        # 验证记忆累积
        stats = route_memory.get_route_statistics()
        assert stats["total_memories"] == 3

    def test_route_pattern_learning(self, reflector, complete_current_state):
        """测试路由模式学习."""
        route_memory = StructuredMemory(name="route")

        # 添加不同压缩率的记忆
        for compression_rate in [0.0, 0.3, 0.6, 0.8, 1.0]:
            state = dict(complete_current_state)
            state["orchestration"] = dict(complete_current_state["orchestration"])

            # 模拟不同的压缩率
            for event in state["orchestration"]["event_trail"]:
                event["compression_triggered"] = compression_rate >= 0.5

            reflector.reflect_portfolio_manager(
                current_state=state,
                returns_losses=f"Result with compression {compression_rate}",
                portfolio_manager_memory=MagicMock(),
                route_memory=route_memory,
            )

        # 验证模式相关性分析
        high_compression = route_memory.get_pattern_outcome_correlation("high_compression")
        assert high_compression["count"] > 0

        direct = route_memory.get_pattern_outcome_correlation("direct")
        assert direct["count"] > 0

    def test_segment_specific_learning(self, reflector, complete_current_state):
        """测试板块特定学习."""
        route_memory = StructuredMemory(name="route")

        # 添加不同板块的记忆
        segments = ["cn_star", "cn_chinext", "cn_main_board", "cn_bse"]

        for i, segment in enumerate(segments):
            state = dict(complete_current_state)
            state["ticker_info"] = dict(complete_current_state["ticker_info"])
            state["ticker_info"]["segment"] = segment
            state["ticker_info"]["ticker"] = f"STOCK{i}"

            reflector.reflect_portfolio_manager(
                current_state=state,
                returns_losses=f"Trade result for {segment}",
                portfolio_manager_memory=MagicMock(),
                route_memory=route_memory,
            )

        # 验证按板块统计
        for segment in segments:
            stats = route_memory.get_route_statistics_by_segment(segment=segment)
            assert stats["total_memories"] == 1

    def test_historical_comparison_effectiveness(self, reflector, complete_current_state):
        """测试历史对比有效性."""
        route_memory = StructuredMemory(name="route")

        # 添加历史记忆（低效路由）
        for i in range(3):
            state = dict(complete_current_state)
            state["orchestration"]["event_trail"] = [
                {"stage": "analyst", "compression_triggered": True},
                {"stage": "research", "compression_triggered": True},
                {"stage": "research", "compression_triggered": True},
                {"stage": "trader", "compression_triggered": True},
            ]

            reflector.reflect_portfolio_manager(
                current_state=state,
                returns_losses=f"Low efficiency trade {i}",
                portfolio_manager_memory=MagicMock(),
                route_memory=route_memory,
            )

        # 获取历史对比数据
        historical = route_memory.export_memories()
        assert len(historical) == 3

        # 当前高效路由
        efficient_state = dict(complete_current_state)
        efficient_state["orchestration"]["event_trail"] = [
            {"stage": "analyst", "compression_triggered": False},
            {"stage": "research", "compression_triggered": False},
        ]

        # 验证可以生成对比洞察
        event_trail = reflector._extract_event_trail(efficient_state)
        comparison = reflector._compare_with_historical_memories(
            current_efficiency=reflector.analyze_route_efficiency(event_trail),
            current_segment="cn_chinext",
            current_style="growth",
            current_route="direct",
            historical_memories=historical,
        )

        # 验证对比结果
        assert "has_sufficient_data" in comparison


# ============================================================================
# 测试类: 错误处理和边界情况
# ============================================================================

class TestErrorHandling:
    """错误处理和边界情况测试."""

    def test_empty_event_trail_handling(self, reflector):
        """测试空事件轨道处理."""
        state = {
            "orchestration": {"event_trail": []},
            "ticker_info": {"ticker": "TEST"},
        }

        # 应该不抛出异常
        try:
            event_trail = reflector._extract_event_trail(state)
            assert event_trail == []
        except Exception as e:
            pytest.fail(f"Should not raise exception: {e}")

    def test_missing_ticker_info(self, reflector):
        """测试缺失ticker_info处理."""
        state = {
            "orchestration": {"event_trail": []},
        }

        # 应该不抛出异常
        try:
            context = reflector._extract_orchestration_context_structured(state)
            assert context is not None
        except Exception as e:
            pytest.fail(f"Should not raise exception: {e}")

    def test_invalid_metadata_handling(self):
        """测试无效metadata处理."""
        memory = StructuredMemory(name="test_memory")

        # 添加带缺失字段的metadata
        memory.add_situation(
            situation="Test",
            recommendation="Test",
            metadata={
                "segment": "cn_star",
                # 缺少其他必需字段
            },
        )

        # 应该成功添加
        assert len(memory.documents) == 1

    def test_large_event_trail_handling(self, reflector):
        """测试大量事件处理."""
        # 创建大量事件
        large_trail = [
            {
                "node": f"event_{i}",
                "stage": f"stage_{i % 5}",
                "phase": f"phase_{i}",
                "compression_triggered": i % 2 == 0,
                "context_estimate": 1000 * i,
            }
            for i in range(100)
        ]

        state = {
            "orchestration": {"event_trail": large_trail},
            "ticker_info": {"ticker": "TEST", "segment": "cn_star"},
        }

        # 应该能处理
        efficiency = reflector.analyze_route_efficiency(large_trail)
        assert efficiency["total_events"] == 100

        patterns = reflector.identify_route_patterns(large_trail)
        assert len(patterns) > 0


# ============================================================================
# 测试类: 性能基准
# ============================================================================

class TestPerformance:
    """性能基准测试."""

    def test_reflection_performance(self, reflector, complete_current_state):
        """测试反思性能."""
        import time

        route_memory = StructuredMemory(name="route")
        portfolio_memory = StructuredMemory(name="portfolio")

        start_time = time.time()

        # 执行100次反思
        for i in range(100):
            state = dict(complete_current_state)
            state["ticker_info"] = dict(complete_current_state["ticker_info"])
            state["ticker_info"]["ticker"] = f"STOCK{i}"

            reflector.reflect_portfolio_manager(
                current_state=state,
                returns_losses=f"Result {i}",
                portfolio_manager_memory=portfolio_memory,
                route_memory=route_memory,
            )

        elapsed = time.time() - start_time

        # 验证性能（100次反思应该在30秒内完成）
        assert elapsed < 30, f"Too slow: {elapsed:.2f}s for 100 iterations"

    def test_memory_query_performance(self):
        """测试记忆查询性能."""
        import time

        memory = StructuredMemory(name="test_memory")

        # 添加1000条记忆
        for i in range(1000):
            memory.add_situation(
                situation=f"Situation {i}",
                recommendation=f"Recommendation {i}",
                metadata={
                    "segment": f"segment_{i % 10}",
                    "style_bucket": f"style_{i % 5}",
                    "route_category": "normal",
                },
            )

        start_time = time.time()

        # 执行100次查询
        for i in range(100):
            memory.get_memories(
                current_situation=f"Query {i}",
                n_matches=5,
                filters={"segment": f"segment_{i % 10}"},
            )

        elapsed = time.time() - start_time

        # 验证性能
        assert elapsed < 10, f"Too slow: {elapsed:.2f}s for 100 queries"
