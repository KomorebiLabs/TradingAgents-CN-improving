"""
TradingAgents 测试策略框架。

本模块提供分层测试基础设施，解决Mock过度使用问题。

测试金字塔:
┌─────────────────────────────────────────┐
│  E2E Tests (端到端)                     │
│  - 真实API调用，真实数据库                │
│  - 标记: @pytest.mark.e2e               │
│  - 运行: CI/CD Pipeline                 │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│  Integration Tests (集成测试)            │
│  - 真实组件，Fake外部依赖                │
│  - 标记: @pytest.mark.integration       │
│  - 运行: 每次PR                        │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│  Unit Tests (单元测试)                   │
│  - Mock/Stub 隔离依赖                   │
│  - 标记: @pytest.mark.unit              │
│  - 运行: 每次Commit                     │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│  Smoke Tests (冒烟测试)                  │
│  - 最关键路径验证                       │
│  - 标记: @pytest.mark.smoke            │
│  - 运行: 每次部署前                      │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│  Contract Tests (契约测试)                │
│  - 验证组件接口兼容性                   │
│  - 标记: @pytest.mark.contract         │
│  - 运行: 每周                            │
└─────────────────────────────────────────┘

Fake vs Mock:
- Fake: 有实现的测试替身（可复用、跨测试）
  例: FakeVectorStore, FakeEmbeddingModel
- Mock: 代码生成的模拟对象（一次性）
  例: unittest.mock.Mock()

原则:
1. 底层测试使用Fake
2. Mock仅用于不可Mock的外部依赖
3. 集成测试使用真实组件组合
"""

import pytest
import os
import sys
from typing import Generator, Callable
from dataclasses import dataclass, field
from pathlib import Path

# 测试配置
TEST_CONFIG_ENV_PREFIX = "TRADINGAGENTS_TEST_"

# 外部依赖配置
AKSHARE_AVAILABLE = True  # 假设可用
YFINANCE_AVAILABLE = True


def pytest_configure(config):
    """Pytest配置钩子."""
    # 注册自定义标记
    config.addinivalue_line(
        "markers", "unit: Unit tests with mocked dependencies"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests with real components"
    )
    config.addinivalue_line(
        "markers", "e2e: End-to-end tests with real APIs"
    )
    config.addinivalue_line(
        "markers", "smoke: Critical path smoke tests"
    )
    config.addinivalue_line(
        "markers", "contract: Contract tests for API compatibility"
    )
    config.addinivalue_line(
        "markers", "slow: Slow running tests (may be skipped in CI)"
    )


def pytest_collection_modifyitems(config, items):
    """根据环境变量修改测试收集."""
    skip_slow = os.environ.get(f"{TEST_CONFIG_ENV_PREFIX}SKIP_SLOW", "false").lower() in ("true", "1")
    run_e2e = os.environ.get(f"{TEST_CONFIG_ENV_PREFIX}RUN_E2E", "false").lower() in ("true", "1")
    run_integration = os.environ.get(f"{TEST_CONFIG_ENV_PREFIX}RUN_INTEGRATION", "true").lower() in ("true", "1")

    for item in items:
        # 跳过慢速测试（除非明确运行）
        if "slow" in item.keywords and skip_slow:
            item.add_marker(pytest.mark.skip(reason="Skipped by SKIP_SLOW env var"))

        # 跳过E2E测试（除非明确运行）
        if "e2e" in item.keywords and not run_e2e:
            item.add_marker(pytest.mark.skip(reason="E2E tests disabled. Set TRADINGAGENTS_TEST_RUN_E2E=true to enable"))

        # 跳过集成测试（如果配置禁用）
        if "integration" in item.keywords and not run_integration:
            item.add_marker(pytest.mark.skip(reason="Integration tests disabled"))


@dataclass
class TestContext:
    """测试上下文，传递测试间共享数据."""
    data_dir: Path = field(default_factory=lambda: Path("./test_data"))
    config: dict = field(default_factory=dict)
    fixtures: dict = field(default_factory=dict)

    def ensure_data_dir(self):
        """确保数据目录存在."""
        self.data_dir.mkdir(parents=True, exist_ok=True)


# 全局测试上下文
_test_context: TestContext = None


def get_test_context() -> TestContext:
    """获取全局测试上下文."""
    global _test_context
    if _test_context is None:
        _test_context = TestContext()
    return _test_context


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def test_data_dir(tmp_path_factory) -> Path:
    """创建临时测试数据目录."""
    return tmp_path_factory.mktemp("test_data")


@pytest.fixture(scope="session")
def test_context(test_data_dir) -> TestContext:
    """创建测试上下文."""
    ctx = get_test_context()
    ctx.data_dir = test_data_dir
    ctx.ensure_data_dir()
    return ctx


@pytest.fixture
def enable_rag():
    """启用RAG功能."""
    original = os.environ.get("TRADINGAGENTS_RAG_ENABLED", "false")
    os.environ["TRADINGAGENTS_RAG_ENABLED"] = "true"
    yield
    os.environ["TRADINGAGENTS_RAG_ENABLED"] = original


@pytest.fixture
def disable_rag():
    """禁用RAG功能."""
    original = os.environ.get("TRADINGAGENTS_RAG_ENABLED", "true")
    os.environ["TRADINGAGENTS_RAG_ENABLED"] = "false"
    yield
    os.environ["TRADINGAGENTS_RAG_ENABLED"] = original


@pytest.fixture
def mock_external_apis(monkeypatch):
    """Mock外部API调用（用于快速测试）."""
    import requests

    class FakeResponse:
        def __init__(self, json_data, status_code=200):
            self._json = json_data
            self.status_code = status_code

        def json(self):
            return self._json

        def raise_for_status(self):
            pass

    def fake_get(*args, **kwargs):
        return FakeResponse({"data": "mocked"})

    def fake_post(*args, **kwargs):
        return FakeResponse({"result": "mocked"})

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)

    return {"get": fake_get, "post": fake_post}


# ============================================================================
# Test Markers
# ============================================================================

def is_unit_test(func) -> bool:
    """检查是否为单元测试."""
    return hasattr(func, "__unit__") or "test_" in func.__name__


def is_integration_test(func) -> bool:
    """检查是否为集成测试."""
    return hasattr(func, "__integration__")


def is_e2e_test(func) -> bool:
    """检查是否为E2E测试."""
    return hasattr(func, "__e2e__")


def unit(func):
    """标记为单元测试."""
    return pytest.mark.unit(func)


def integration(func):
    """标记为集成测试."""
    return pytest.mark.integration(func)


def e2e(func):
    """标记为E2E测试."""
    return pytest.mark.e2e(func)


def smoke(func):
    """标记为冒烟测试."""
    return pytest.mark.smoke(func)


def slow(func):
    """标记为慢速测试."""
    return pytest.mark.slow(func)


# ============================================================================
# 测试辅助函数
# ============================================================================

def assert_similar_results(result1: str, result2: str, similarity: float = 0.8):
    """
    断言两个结果内容相似（用于验证Fake实现与真实实现一致性）.

    Args:
        result1: 第一个结果
        result2: 第二个结果
        similarity: 最小相似度 (0-1)
    """
    import difflib

    seq = difflib.SequenceMatcher(None, result1, result2)
    ratio = seq.ratio()

    assert ratio >= similarity, (
        f"Results not similar enough: {ratio:.2%} < {similarity:.0%}\n"
        f"Result1: {result1[:200]}...\n"
        f"Result2: {result2[:200]}..."
    )


def measure_latency(func: Callable, *args, **kwargs) -> tuple:
    """
    测量函数执行延迟.

    Returns:
        (result, latency_ms)
    """
    import time

    start = time.perf_counter()
    result = func(*args, **kwargs)
    latency = (time.perf_counter() - start) * 1000

    return result, latency


# ============================================================================
# Smoke Test 基础设施
# ============================================================================

class SmokeTestRunner:
    """冒烟测试运行器."""

    def __init__(self):
        self.results: dict = {}

    def run(self, name: str, func: Callable, *args, **kwargs) -> bool:
        """运行单个冒烟测试."""
        import time

        try:
            start = time.perf_counter()
            func(*args, **kwargs)
            elapsed = time.perf_counter() - start

            self.results[name] = {
                "status": "passed",
                "latency_ms": elapsed * 1000,
            }
            return True
        except Exception as e:
            self.results[name] = {
                "status": "failed",
                "error": str(e),
            }
            return False

    def report(self) -> str:
        """生成报告."""
        lines = ["# Smoke Test Report", "=" * 50]

        passed = sum(1 for r in self.results.values() if r["status"] == "passed")
        total = len(self.results)

        lines.append(f"\nTotal: {passed}/{total} passed")

        for name, result in self.results.items():
            status = "✓" if result["status"] == "passed" else "✗"
            if result["status"] == "passed":
                lines.append(f"{status} {name}: {result['latency_ms']:.2f}ms")
            else:
                lines.append(f"{status} {name}: {result['error']}")

        return "\n".join(lines)


# ============================================================================
# 对比测试辅助（用于验证Fake vs Real一致性）
# ============================================================================

class ConsistencyChecker:
    """一致性检查器：验证Fake实现与真实实现输出相似."""

    def __init__(self, tolerance: float = 0.8):
        self.tolerance = tolerance
        self.differences: list = []

    def check(self, fake_result: str, real_result: str, context: str = "") -> bool:
        """检查一致性."""
        import difflib

        seq = difflib.SequenceMatcher(None, fake_result, real_result)
        similarity = seq.ratio()

        if similarity < self.tolerance:
            self.differences.append({
                "context": context,
                "similarity": similarity,
                "fake": fake_result[:100],
                "real": real_result[:100],
            })
            return False

        return True

    def report(self) -> str:
        """生成不一致报告."""
        if not self.differences:
            return "All results are consistent within tolerance."

        lines = [f"Inconsistencies found ({len(self.differences)}):"]
        for diff in self.differences:
            lines.append(f"\n[{diff['context']}] Similarity: {diff['similarity']:.2%}")
            lines.append(f"  Fake:   {diff['fake']}...")
            lines.append(f"  Real:   {diff['real']}...")

        return "\n".join(lines)
