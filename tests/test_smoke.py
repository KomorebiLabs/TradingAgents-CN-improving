"""
TradingAgents Smoke Tests.

Smoke tests验证当前 Tencent-first 架构下最关键的功能路径：
1. 新的数据流入口可以加载
2. 工具模块可以导入
3. RAG 保持 optional，不被 legacy vendor 依赖拖死
"""

import pytest
import os
import sys
import importlib

from tests.strategies.conftest import smoke, SmokeTestRunner
from tests.fakes import FakeEmbeddingModel, FakeNewsData


@pytest.mark.smoke
class TestRAGSmoke:
    """RAG模块冒烟测试."""

    def test_rag_module_imports(self):
        try:
            from tradingagents.agents.utils.rag import (
                VectorStore,
                EmbeddingModel,
                Retriever,
                Reranker,
                CNNewsRetriever,
            )
        except ImportError as e:
            pytest.fail(f"Failed to import RAG modules: {e}")

    def test_config_module_imports(self):
        """测试配置模块可以导入."""
        try:
            from tradingagents.agents.utils.rag import (
                RAGConfig,
                CNNewsRetrievalConfig,
                VectorStoreConfig,
                EmbeddingModelConfig,
            )
        except ImportError as e:
            pytest.fail(f"Failed to import config modules: {e}")

    def test_middleware_imports(self):
        """测试中间件可以导入."""
        try:
            from tradingagents.agents.utils.rag import (
                RAGMiddleware,
                MergeStrategy,
                get_middleware,
            )
        except ImportError as e:
            pytest.fail(f"Failed to import middleware: {e}")

    def test_performance_module_imports(self):
        """测试性能模块可以导入."""
        try:
            from tradingagents.agents.utils.rag import (
                ModelPreloader,
                PreloadConfig,
                LoadStatus,
            )
        except ImportError as e:
            pytest.fail(f"Failed to import performance module: {e}")


@pytest.mark.smoke
class TestToolsSmoke:
    """工具模块冒烟测试."""

    def test_news_tools_import(self):
        """测试新闻工具可以导入，不应被 legacy vendor 强绑定拖死."""
        try:
            from tradingagents.agents.utils.news_data_tools import (
                get_news,
                get_global_news,
                get_cn_policy_news,
            )
        except ImportError as e:
            pytest.fail(f"Failed to import news tools: {e}")

    def test_sector_tools_import(self):
        """测试行业工具可以导入."""
        try:
            from tradingagents.agents.utils.cn_sector_news_tools import (
                get_cn_tech_sector_news,
                get_cn_new_energy_news,
                get_cn_pharma_news,
                get_sector_for_ticker,
            )
        except ImportError as e:
            pytest.fail(f"Failed to import sector tools: {e}")

    def test_tool_decorator(self):
        """测试工具装饰器工作正常."""
        from langchain_core.tools import tool
        from typing import Annotated

        @tool
        def test_tool(param: Annotated[str, "Test param"]) -> str:
            """A test tool."""
            return f"Test: {param}"

        # 验证工具可以调用
        result = test_tool.invoke({"param": "value"})
        assert "Test" in result


@pytest.mark.smoke
class TestDataFlowSmoke:
    """数据流冒烟测试."""

    def test_interface_imports(self):
        """测试 Tencent-first 接口模块可以导入."""
        try:
            from tradingagents.dataflows.interface import route_to_vendor, VENDOR_LIST
        except ImportError as e:
            pytest.fail(f"Failed to import interface: {e}")
        assert "tencent_finance" in VENDOR_LIST
        assert "ths_data" in VENDOR_LIST

    def test_route_to_vendor_function_exists(self):
        """测试路由函数存在."""
        from tradingagents.dataflows.interface import route_to_vendor, get_vendor

        assert callable(route_to_vendor)
        assert "tencent_finance" in get_vendor("core_stock_apis")

    def test_legacy_vendors_are_optional_not_import_time_blockers(self):
        """旧数据源可以缺失，但 interface 仍应可导入并暴露新基线路由."""
        from tradingagents.dataflows.interface import get_vendor

        core_vendors = get_vendor("core_stock_apis")
        news_vendors = get_vendor("news_data")
        assert core_vendors.startswith("tencent_finance")
        assert "legacy_yfinance" in core_vendors
        assert news_vendors.startswith("ths_data")


@pytest.mark.smoke
class TestFakesSmoke:
    """Fake实现冒烟测试."""

    def test_fake_embedding(self):
        """测试Fake嵌入模型."""
        model = FakeEmbeddingModel()
        result = model.embed("test")

        assert result.shape == (1, 384)
        assert result.dtype == "float32"

    def test_fake_news(self):
        """测试Fake新闻数据."""
        news = FakeNewsData.generate_news(ticker="TEST")
        assert "TEST" in news
        assert len(news) > 50


@pytest.mark.smoke
class TestConfigurationSmoke:
    """配置冒烟测试."""

    def test_default_config(self):
        """测试默认配置已经切到 Tencent-first 基线."""
        from tradingagents.default_config import DEFAULT_CONFIG

        assert DEFAULT_CONFIG["data_vendors"]["core_stock_apis"].startswith("tencent_finance")
        assert DEFAULT_CONFIG["data_vendors"]["news_data"].startswith("ths_data")

    def test_env_config(self):
        """测试 RAG 环境变量配置保持可用."""
        # 设置环境变量
        os.environ["TRADINGAGENTS_RAG_ENABLED"] = "false"

        from tradingagents.agents.utils.rag import RAGMiddlewareConfig

        config = RAGMiddlewareConfig.from_env()
        assert config.enabled == False

        # 清理
        os.environ.pop("TRADINGAGENTS_RAG_ENABLED", None)


# ============================================================================
# Smoke Test Runner
# ============================================================================

def test_run_all_smoke_tests():
    """
    运行所有冒烟测试（用于CI/CD）。

    这个测试总是通过，除非有冒烟测试失败。
    """
    runner = SmokeTestRunner()

    # 测试1: 模块导入
    def test_imports():
        from tradingagents.dataflows.interface import route_to_vendor, get_vendor
        assert callable(route_to_vendor)
        assert "tencent_finance" in get_vendor("core_stock_apis")
    runner.run("Module imports", test_imports)

    # 测试2: Fake组件
    def test_fake():
        model = FakeEmbeddingModel()
        model.embed("test")
    runner.run("Fake components", test_fake)

    # 测试3: 配置
    def test_config():
        from tradingagents.default_config import DEFAULT_CONFIG
        assert DEFAULT_CONFIG["data_vendors"]["core_stock_apis"].startswith("tencent_finance")
    runner.run("Configuration", test_config)

    # 输出报告
    print("\n" + runner.report())

    # 检查结果
    failed = [name for name, r in runner.results.items() if r["status"] == "failed"]

    if failed:
        pytest.fail(f"Smoke tests failed: {', '.join(failed)}")
