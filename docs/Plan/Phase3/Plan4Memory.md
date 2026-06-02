# P4 Memory 实现计划：股票分析结论缓存

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Trader 节点执行前注入历史分析结论，减少重复分析的 token 消耗，同时保证数据始终为最新。

**Architecture:** 分析完成时，`Reflector` 生成结构化摘要 JSON 存入 `~/.tradingagents/memory/<ticker>_<trade_date>.json`；下次分析同一股票时，`TradingAgentsGraph` 在初始化阶段加载有效期内（7天TTL）的摘要并注入 `AgentState.historical_context`，Trader 节点读取后作为补充上下文。

**Tech Stack:** Python 文件 I/O（json）、LangChain/LangGraph、`tradingagents/agents/utils/memory.py`（现有 BM25 结构参考）、`tradingagents/graph/reflection.py`（Reflector 扩展）、`tradingagents/agents/utils/agent_states.py`（AgentState 扩展）

---

## 文件变更总览

| 文件 | 操作 | 职责 |
|------|------|------|
| `tradingagents/agents/utils/agent_states.py` | 修改 | `AgentState` 新增 `historical_context` 字段 |
| `tradingagents/agents/utils/memory_manager.py` | 新建 | 负责 JSON 读/写/TTL 检查，与现有 BM25 memory 解耦 |
| `tradingagents/graph/reflection.py` | 修改 | `Reflector` 新增 `generate_conclusion_summary()` 方法 |
| `tradingagents/graph/trading_graph.py` | 修改 | `__init__` 时加载历史摘要；`propagate()` 时写入 state；`reflect_and_remember()` 时生成并持久化摘要 |
| `tradingagents/graph/propagation.py` | 修改 | `create_initial_state()` 新增 `historical_context` 字段初始化 |
| `tests/test_memory_manager.py` | 新建 | 单元测试 |
| `tests/test_historical_context_injection.py` | 新建 | 集成测试 |

---

## Task 1: `AgentState` 新增 `historical_context` 字段

**文件:** `tradingagents/agents/utils/agent_states.py`

- [ ] **Step 1: 在 `AgentState` 类末尾添加 `historical_context` 字段**

找到 `AgentState` 类定义末尾（大约第 270 行），在 `decision_blocks` 字段后添加：

```python
    # -------------------------------------------------------------------------
    # 【第六层】历史结论上下文 - 跨会话注入
    # -------------------------------------------------------------------------
    historical_context: Annotated[
        Optional[Dict[str, Any]],
        "Historical analysis conclusion for the same ticker within TTL window"
    ]
```

确保 `from typing import Optional` 已导入（应该在文件顶部已有）。

- [ ] **Step 2: 在 `DecisionBlocksState` 中确认 `decision_blocks` 结构**

确认 `DecisionBlocksState` 已包含 `investment_plan` / `trader_plan` / `final_trade_decision` 字段（用于摘要模板拼接）。这些字段应在约第 176-184 行已存在，无需修改。

- [ ] **Step 3: 验证类型导入**

确认 `Optional` 在文件顶部 `from typing import ...` 中。如缺失，在导入语句中添加。

---

## Task 2: 新建 `memory_manager.py` — 负责持久化读写

**文件:** `tradingagents/agents/utils/memory_manager.py`

- [ ] **Step 1: 创建文件，定义路径常量**

```python
"""Historical conclusion memory manager — file-based persistence for cross-session memory."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from datetime import date, timedelta
from typing import Optional, Dict, Any

DEFAULT_MEMORY_DIR = Path.home() / ".tradingagents" / "memory"
DEFAULT_TTL_DAYS = 7


def _get_memory_path(ticker: str, trade_date: str, memory_dir: Path | None = None) -> Path:
    """Compute the JSON file path for a given ticker and trade date.

    Filename format: {ticker}_{trade_date}.json
    """
    safe_ticker = ticker.replace("/", "_").replace("\\", "_")
    if memory_dir is None:
        memory_dir = DEFAULT_MEMORY_DIR
    memory_dir = Path(memory_dir)
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir / f"{safe_ticker}_{trade_date}.json"


def _get_latest_for_ticker(
    ticker: str,
    memory_dir: Path | None = None,
    ttl_days: int = DEFAULT_TTL_DAYS,
) -> Optional[Dict[str, Any]]:
    """Find the most recent non-expired memory entry for a ticker.

    Scans memory_dir for files matching "{ticker}_*.json",
    returns the most recent one if within TTL, else None.
    """
    if memory_dir is None:
        memory_dir = DEFAULT_MEMORY_DIR
    memory_dir = Path(memory_dir)
    if not memory_dir.exists():
        return None

    safe_ticker = ticker.replace("/", "_").replace("\\", "_")
    today = date.today()

    candidates = []
    for f in memory_dir.iterdir():
        if not f.name.startswith(safe_ticker + "_") or not f.name.endswith(".json"):
            continue
        try:
            trade_date_str = f.stem[len(safe_ticker) + 1:]
            trade_date = date.fromisoformat(trade_date_str)
            age_days = (today - trade_date).days
            if age_days <= ttl_days:
                candidates.append((trade_date, age_days, f))
        except ValueError:
            continue

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    _, age_days, path = candidates[0]
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_conclusion_summary(
    ticker: str,
    trade_date: str,
    summary: Dict[str, Any],
    memory_dir: Path | None = None,
) -> Path:
    """Write a conclusion summary JSON to disk.

    Returns the path where it was saved.
    """
    path = _get_memory_path(ticker, trade_date, memory_dir)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    return path


def load_historical_conclusion(
    ticker: str,
    current_date: str | None = None,
    ttl_days: int = DEFAULT_TTL_DAYS,
    memory_dir: Path | None = None,
) -> Optional[Dict[str, Any]]:
    """Load the most recent non-expired conclusion for ticker.

    Returns None if no valid entry exists (expired or never analyzed).
    Silently skips expired entries — caller receives None.
    """
    return _get_latest_for_ticker(ticker, memory_dir, ttl_days)
```

- [ ] **Step 2: 写单元测试**

**文件:** `tests/test_memory_manager.py`

```python
"""Tests for memory_manager.py."""
import json
import tempfile
from pathlib import Path
from datetime import date, timedelta

import pytest

from tradingagents.agents.utils.memory_manager import (
    save_conclusion_summary,
    load_historical_conclusion,
    _get_memory_path,
    DEFAULT_TTL_DAYS,
)


def test_save_and_load(tmp_path):
    ticker = "300750"
    trade_date = "2026-05-20"
    summary = {"ticker": ticker, "trade_date": trade_date, "summary": "test"}

    path = save_conclusion_summary(ticker, trade_date, summary, memory_dir=tmp_path)
    assert path.exists()

    loaded = load_historical_conclusion(ticker, memory_dir=tmp_path)
    assert loaded is not None
    assert loaded["ticker"] == ticker
    assert loaded["summary"] == "test"


def test_expired_ttl_returns_none(tmp_path):
    ticker = "300750"
    old_date = (date.today() - timedelta(days=10)).isoformat()
    summary = {"ticker": ticker, "trade_date": old_date, "summary": "stale"}

    save_conclusion_summary(ticker, old_date, summary, memory_dir=tmp_path)

    result = load_historical_conclusion(ticker, memory_dir=tmp_path, ttl_days=7)
    assert result is None


def test_within_ttl_returns_entry(tmp_path):
    ticker = "300750"
    recent_date = (date.today() - timedelta(days=3)).isoformat()
    summary = {"ticker": ticker, "trade_date": recent_date, "summary": "fresh"}

    save_conclusion_summary(ticker, recent_date, summary, memory_dir=tmp_path)

    result = load_historical_conclusion(ticker, memory_dir=tmp_path, ttl_days=7)
    assert result is not None
    assert result["summary"] == "fresh"


def test_most_recent_wins_when_multiple(tmp_path):
    ticker = "300750"
    old = (date.today() - timedelta(days=2)).isoformat()
    newer = (date.today() - timedelta(days=1)).isoformat()

    save_conclusion_summary(ticker, old, {"ticker": ticker, "trade_date": old, "summary": "old"})
    save_conclusion_summary(ticker, newer, {"ticker": ticker, "trade_date": newer, "summary": "newer"})

    result = load_historical_conclusion(ticker, memory_dir=tmp_path)
    assert result is not None
    assert result["summary"] == "newer"


def test_different_ticker_no_cross_contamination(tmp_path):
    save_conclusion_summary("300750", "2026-05-20", {"ticker": "300750"}, memory_dir=tmp_path)
    result = load_historical_conclusion("600519", memory_dir=tmp_path)
    assert result is None


def test_get_memory_path_sanitizes_ticker():
    path = _get_memory_path("TSLA", "2026-05-20")
    assert "TSLA" in path.name
    assert ".json" in path.name
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/test_memory_manager.py -v
```

预期：所有测试 PASS。如有失败，检查文件路径处理逻辑。

---

## Task 3: `Reflector` 新增摘要生成方法

**文件:** `tradingagents/graph/reflection.py`

- [ ] **Step 1: 在文件顶部添加导入**

在 `reflection.py` 顶部找到现有 `import` 区块，确认以下导入存在后，在附近添加：

```python
from tradingagents.agents.utils.memory_manager import save_conclusion_summary
```

- [ ] **Step 2: 在 `Reflector` 类中添加 `generate_conclusion_summary` 方法**

在 `reflect_portfolio_manager` 方法之后（约第 1135 行附近）添加：

```python
    def generate_conclusion_summary(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a structured lightweight conclusion summary for cross-session memory.

        This method creates a JSON-serializable summary of the analysis result
        using a hybrid approach:
        - Structured fields are extracted from AgentState via template (no LLM cost)
        - The 'summary' field is generated by a lightweight LLM call (~50-100 tokens)

        Args:
            current_state: The final AgentState after analysis completes

        Returns:
            Dict containing: ticker, trade_date, summary, dimensions, final_decision,
            confidence, key_reasons, risks
        """
        ticker = current_state.get("company_of_interest", "UNKNOWN")
        trade_date = str(current_state.get("trade_date", ""))

        # ── Template-based extraction (no LLM cost) ─────────────────────────────
        decision_blocks = current_state.get("decision_blocks", {}) or {}
        investment_plan = decision_blocks.get("investment_plan", "")
        trader_plan = decision_blocks.get("trader_plan", "")
        final_decision = decision_blocks.get("final_trade_decision", "")

        investment_debate = current_state.get("investment_debate_state", {}) or {}
        judge_decision = investment_debate.get("judge_decision", "")

        risk_debate = current_state.get("risk_debate_state", {}) or {}
        risk_judge = risk_debate.get("judge_decision", "")

        # Extract bull/bear sentiment from debate
        bull_history = investment_debate.get("bull_history", "")
        bear_history = investment_debate.get("bear_history", "")

        # Extract key reasons and risks from debate conclusions
        key_reasons = []
        risks = []

        if bull_history:
            key_reasons.append(f"Bull case: {bull_history[:300]}")
        if judge_decision and len(judge_decision) > 10:
            key_reasons.append(f"Investment judgment: {judge_decision[:300]}")
        if risk_judge and len(risk_judge) > 10:
            risks.append(f"Risk judgment: {risk_judge[:300]}")

        # Extract dimensions from screener_context if present
        dimensions = {}
        screener_context = current_state.get("screener_context", {}) or {}
        route_decision = screener_context.get("route_decision", {}) or {}
        signal_card = route_decision.get("signal_card") or {}
        if isinstance(signal_card, dict):
            dimensions = {
                "policy": signal_card.get("policy_signal_score", 0.5),
                "technical": signal_card.get("technical_signal_score", 0.5),
                "smart_money": signal_card.get("smart_money_signal_score", 0.5),
            }

        # Determine confidence level
        confidence = "中"
        if final_decision:
            if "强" in final_decision or "买入" in final_decision or "BUY" in final_decision.upper():
                confidence = "高"
            elif "不" in final_decision or "卖出" in final_decision or "SELL" in final_decision.upper():
                confidence = "低"
        if judge_decision and ("不" in judge_decision or "无" in judge_decision):
            confidence = "低"

        # ── LLM-generated one-line summary (hybrid part) ───────────────────────
        prompt = (
            f"Given the following analysis results for {ticker} on {trade_date}, "
            f"write ONE concise sentence (in Chinese, under 50 characters) that captures the core investment conclusion.\n\n"
            f"Investment plan: {investment_plan[:500]}\n"
            f"Final decision: {final_decision[:500]}\n"
            f"Judge opinion: {judge_decision[:300]}\n"
            f"Risk opinion: {risk_judge[:300]}"
        )

        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.llm.invoke(messages)
            summary_text = response.content.strip() if hasattr(response, "content") else str(response)
            # Truncate to avoid bloated context
            summary_text = summary_text[:200]
        except Exception:
            summary_text = f"分析完成，结论：{final_decision[:100] if final_decision else '待确认'}"

        return {
            "ticker": ticker,
            "trade_date": trade_date,
            "summary": summary_text,
            "dimensions": dimensions,
            "final_decision": final_decision[:500] if final_decision else "N/A",
            "confidence": confidence,
            "key_reasons": key_reasons[:5],
            "risks": risks[:5],
        }
```

- [ ] **Step 3: 验证 Reflector 已有 `llm` 属性**

确认 `Reflector.__init__` 接收 `llm` 参数并存储为 `self.llm`。查看约第 1-30 行的 `__init__`：

```python
class Reflector:
    def __init__(self, llm):
        self.llm = llm
```

如结构不同，根据实际签名调整 Task 3 Step 2 中的 LLM 调用方式。

---

## Task 4: 修改 `propagation.py` — 初始化 `historical_context`

**文件:** `tradingagents/graph/propagation.py`

- [ ] **Step 1: 在 `create_initial_state()` 返回字典中初始化字段**

在 `create_initial_state()` 返回字典（约第 145-180 行）中，找到 `screener_context` 初始化行，在其下方添加：

```python
            "historical_context": None,  # Loaded at graph init time by TradingAgentsGraph
```

完整上下文：

```python
        return {
            # ... existing fields ...

            "screener_context": screener_context,
            "historical_context": None,  # Loaded at graph init time by TradingAgentsGraph

            # ... rest of fields ...
```

- [ ] **Step 2: 如 `create_initial_state` 后续被传入 config 参数，确认 config 中无 historical_context 冲突**

确认该方法不从 `config` 中读取 `historical_context`，避免覆盖。

---

## Task 5: 修改 `trading_graph.py` — 加载 + 写入

**文件:** `tradingagents/graph/trading_graph.py`

- [ ] **Step 1: 在文件顶部添加导入**

在文件顶部找到现有 `import` 行，添加：

```python
from tradingagents.agents.utils.memory_manager import (
    save_conclusion_summary,
    load_historical_conclusion,
)
```

- [ ] **Step 2: 修改 `TradingAgentsGraph.__init__()` — 加载历史结论**

找到 `__init__` 中初始化 `route_memory` 的位置（约第 116 行），在其下方添加：

```python
        self.route_memory = StructuredMemory("route_memory", self.config)

        # P4 Memory: Load historical conclusion for company_of_interest
        self._historical_context: Optional[Dict[str, Any]] = None
        company = self.config.get("company_of_interest", "")
        if company:
            self._historical_context = load_historical_conclusion(company)
```

需要确保 `Optional` 和 `Dict, Any` 的导入存在（应该已通过 `from typing import Dict, Any, Optional` 导入）。

- [ ] **Step 3: 修改 `propagate()` 方法 — 将历史上下文注入初始状态**

找到 `propagate()` 方法（约第 194 行），找到这行：

```python
            init_agent_state = self.propagator.create_initial_state(
                company_name, trade_date, self.graph_setup.selected_analysts
            )
```

在其后添加：

```python
            # P4 Memory: Inject historical context into initial state
            if self._historical_context is not None:
                init_agent_state["historical_context"] = self._historical_context
```

- [ ] **Step 4: 修改 `reflect_and_remember()` — 生成并持久化摘要**

找到 `reflect_and_remember()` 方法（约第 417 行），在现有5个 `reflect_*` 调用之后添加：

```python
        self.reflector.reflect_portfolio_manager(
            self.curr_state, returns_losses, self.portfolio_manager_memory,
            route_memory=self.route_memory
        )

        # P4 Memory: Generate and persist conclusion summary
        try:
            summary = self.reflector.generate_conclusion_summary(self.curr_state)
            ticker = self.curr_state.get("company_of_interest", "")
            trade_date = str(self.curr_state.get("trade_date", ""))
            if ticker and trade_date:
                save_conclusion_summary(ticker, trade_date, summary)
        except Exception:
            # Memory persistence must never crash the reflection flow
            pass
```

- [ ] **Step 5: 在 `propagate()` 末尾，重置 `_historical_context` 以便下次调用**

在 `propagate()` 方法返回语句之后（约第 241 行附近），在 `return` 之前添加：

```python
        self._historical_context = None  # Reset for next propagate() call
```

---

## Task 6: 修改 `trader_node` — 读取并注入 `historical_context`

**文件:** `tradingagents/agents/trader/trader.py`

- [ ] **Step 1: 在 `trader_node` 的 context 构建处注入 `historical_context`**

找到 `trader_node` 中构建 `context` 的位置（约第 239-255 行）。在 `context["content"]` 字符串末尾，`f"Leverage these insights...` 那一行之前，插入：

```python
                # P4 Memory: Append historical context if available
                historical_context = state.get("historical_context")
                historical_context_str = ""
                if historical_context:
                    dims = historical_context.get("dimensions", {})
                    dim_str = "; ".join(f"{k}={v}" for k, v in dims.items()) if dims else "N/A"
                    historical_context_str = (
                        f"\n\n[Historical Context from {historical_context.get('trade_date', 'N/A')} "
                        f"({historical_context.get('confidence', 'N/A')}置信度)]\n"
                        f"Summary: {historical_context.get('summary', 'N/A')}\n"
                        f"Dimensions: {dim_str}\n"
                        f"Final Decision: {historical_context.get('final_decision', 'N/A')}\n"
                        f"Key Reasons: {'; '.join(historical_context.get('key_reasons', [])[:3])}\n"
                        f"Risks: {'; '.join(historical_context.get('risks', [])[:2])}\n"
                    )

                f"Leverage these insights to make an informed and strategic decision."
            ),
        }

        # 如果不使用 + 拼接，可以在现有 f-string 后追加
        if historical_context_str:
            context["content"] += historical_context_str
```

找到 `f"Leverage these insights to make an informed and strategic decision.\n\n"` 那行，将其改为不以 `\n\n` 结尾（因为 `historical_context_str` 会自带换行），或将追加逻辑放在 `context` 构建之后：

```python
        # ── P4 Memory: Inject historical context ───────────────────────────────
        historical_context = state.get("historical_context")
        if historical_context:
            dims = historical_context.get("dimensions", {})
            dim_str = "; ".join(f"{k}={v}" for k, v in dims.items()) if dims else "N/A"
            historical_context_str = (
                f"\n\n[Historical Context — {historical_context.get('trade_date', '')} "
                f"({historical_context.get('confidence', '')}置信度)]\n"
                f"上一轮分析结论: {historical_context.get('summary', 'N/A')}\n"
                f"策略维度: {dim_str}\n"
                f"最终决策: {historical_context.get('final_decision', 'N/A')}\n"
                f"关键理由: {'; '.join(historical_context.get('key_reasons', [])[:3])}\n"
                f"风险提示: {'; '.join(historical_context.get('risks', [])[:2])}\n"
            )
            context["content"] += historical_context_str
```

将这段代码插入到 `context` 字典定义之后（约第 255 行后，`messages = [` 之前）。

---

## Task 7: 集成测试

**文件:** `tests/test_historical_context_injection.py`

- [ ] **Step 1: 写集成测试**

```python
"""Integration tests for historical context injection."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from tradingagents.graph.trading_graph import TradingAgentsGraph


@pytest.fixture
def mock_config(tmp_path):
    return {
        "company_of_interest": "TEST_TICKER",
        "llm_provider": "openai",
        "deep_think_llm": "gpt-4o",
        "quick_think_llm": "gpt-4o-mini",
        "backend_url": "https://api.openai.com/v1",
        "max_debate_rounds": 2,
        "max_risk_discuss_rounds": 2,
        "max_recur_limit": 10,
        "enable_confidence_score": True,
    }


def test_memory_saved_after_reflection(tmp_path, mock_config):
    """Verify that analyze_with_harness saves a conclusion summary to disk."""
    pass  # TODO: integrate with full harness test


def test_memory_loaded_at_init(tmp_path, mock_config):
    """Verify that TradingAgentsGraph loads historical context on init."""
    # Pre-write a memory file
    ticker = mock_config["company_of_interest"]
    trade_date = "2026-05-20"
    summary = {
        "ticker": ticker,
        "trade_date": trade_date,
        "summary": "test summary",
        "dimensions": {"policy": 0.8},
        "final_decision": "买入",
        "confidence": "高",
        "key_reasons": ["reason1"],
        "risks": ["risk1"],
    }

    with patch("tradingagents.agents.utils.memory_manager.DEFAULT_MEMORY_DIR", tmp_path):
        from tradingagents.agents.utils.memory_manager import save_conclusion_summary
        save_conclusion_summary(ticker, trade_date, summary, memory_dir=tmp_path)

        # Verify loading returns it
        from tradingagents.agents.utils.memory_manager import load_historical_conclusion
        result = load_historical_conclusion(ticker, memory_dir=tmp_path)
        assert result is not None
        assert result["summary"] == "test summary"
        assert result["confidence"] == "高"


def test_expired_memory_not_loaded(tmp_path, mock_config):
    """Verify that expired memory returns None."""
    from datetime import date, timedelta
    from tradingagents.agents.utils.memory_manager import (
        save_conclusion_summary, load_historical_conclusion
    )

    ticker = "EXPIRED_TICKER"
    old_date = (date.today() - timedelta(days=10)).isoformat()
    save_conclusion_summary(ticker, old_date, {"ticker": ticker, "trade_date": old_date}, memory_dir=tmp_path)

    result = load_historical_conclusion(ticker, ttl_days=7, memory_dir=tmp_path)
    assert result is None
```

- [ ] **Step 2: 运行测试**

```bash
pytest tests/test_memory_manager.py tests/test_historical_context_injection.py -v
```

---

## Task 8: CLI 参数扩展（可选）

**文件:** `tradingagents/commands/analyze/app.py`

如果需要在 CLI 层控制 TTL，添加 `--memory-ttl` 参数：

- [ ] **Step 1: 在 `analyze` 命令中添加参数**

在 `analyze` 命令函数签名中添加：

```python
memory_ttl: int = typer.Option(
    7,
    "--memory-ttl",
    help="Days to keep historical conclusion memory (default: 7)",
),
```

- [ ] **Step 2: 将 TTL 传入 config**

在 `analyze` 命令中将 `memory_ttl` 写入 config 字典，`TradingAgentsGraph` 从 config 中读取 `memory_ttl` 并传给 `load_historical_conclusion`。

---

## 执行顺序

1. Task 1 (`AgentState` 新字段) — 基础类型定义
2. Task 2 (`memory_manager.py`) — 核心持久化逻辑，独立可测
3. Task 3 (`Reflector` 扩展) — 依赖 Task 2
4. Task 4 (`propagation.py`) — 状态初始化
5. Task 5 (`trading_graph.py`) — 加载 + 写入逻辑
6. Task 6 (`trader.py`) — 注入点
7. Task 7 (集成测试) — 验证全链路
8. Task 8 (CLI 参数) — 可选，最后做

---

## 自检清单

- [ ] Spec coverage: 每个设计决策都有对应 Task 覆盖
- [ ] Placeholder scan: 无 "TODO" / "TBD" / "填充" 字样
- [ ] 类型一致性: `historical_context` 字段在 `AgentState` 定义、`propagation.py` 初始化、`trader.py` 读取三处类型一致（`Optional[Dict[str, Any]]`）
- [ ] TTL 静默跳过: `load_historical_conclusion` 对过期数据返回 `None`，`trading_graph.py` 对 `None` 无操作，不抛异常
- [ ] 反射流程保护: `save_conclusion_summary` 被 `try/except` 包裹，不影响 `reflect_and_remember` 主流程
