# Harness Phase2 实现计划：Skills Loader + CostTracker + Screener Context

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**计划概览：10 个 Task**
#	Task	范围
1	P3 可观测性基础设施	CostTracker + TokenCountingCallback + 测试
2	Screener Models 更新	DeepAnalysisResult 新增 token_usage 字段
3	DeepAnalyzer 集成	将 CostTracker + callback 接入 DeepAnalyzer
4	P2 Skills Loader 核心	types.py + registry.py + loader.py + 测试
5	13 个内置 Skill 文件	bundled/market/（4个） + news/（3个） + fundamentals/（3个） + social/（2个）
6	SkillInjector	Skill 内容注入到 Agent prompt
7	ScreenerContextInjector	选择性注入技术指标/资金质量/概念标签/风险标志
8	Analyst Agent 集成	market/news/fundamentals/social 4 个 Analyst 接入 Skill + Context
9	harness 完整导出	更新 __init__.py
10	集成测试	端到端验证完整链路


**目标：** 为 TradingAgents 引入三大 Harness 子系统：
1. **P3 可观测性**：LangGraph Callback + CostTracker + DeepAnalysisResult 含 token 消耗字段
2. **P2 Skills Loader**：基于 .md 文件 + Skills Loader，按分析师类型静态加载金融领域 Skill
3. **Scene C Screener Context**：选择性注入技术指标 + 资金质量 + 概念标签 + 风险标志到 Agent prompt

**架构概述：** 在 `tradingagents/harness/` 下构建独立的 harness 层：
- `harness/skills/` — Skills Loader（文件发现 + Registry + Prompt 注入）
- `harness/engine/` — 可观测性（CostTracker + TokenCountingCallback）
- `harness/context/` — Screener 上下文注入器

**技术栈：** Python + Pydantic + LangChain/LangGraph callback 机制

**依赖关系：** P3（可观测性）→ P2（Skills Loader）→ Scene C（Context 注入）。三者可独立测试，但按此顺序实施。

---

## 文件总览

### 新建文件（全部在 `tradingagents/harness/` 下）

| 文件 | 用途 |
|------|------|
| `harness/__init__.py` | 包入口 |
| `harness/skills/types.py` | `SkillDefinition` Pydantic 模型 |
| `harness/skills/registry.py` | `SkillRegistry` 内存注册表 |
| `harness/skills/loader.py` | 核心加载器（目录扫描 + YAML frontmatter 解析） |
| `harness/skills/injector.py` | Skill 内容注入到 Agent prompt 的逻辑 |
| `harness/skills/bundled/market/indicator_library.md` | 技术指标库 Skill |
| `harness/skills/bundled/market/trend_patterns.md` | 趋势形态识别 Skill |
| `harness/skills/bundled/market/volume_analysis.md` | 成交量分析 Skill |
| `harness/skills/bundled/market/breakout_recognition.md` | 突破形态识别 Skill |
| `harness/skills/bundled/news/policy_impact.md` | 政策影响分析 Skill |
| `harness/skills/bundled/news/sector_rotation.md` | 板块轮动分析 Skill |
| `harness/skills/bundled/news/event_catalyst.md` | 事件催化剂分析 Skill |
| `harness/skills/bundled/fundamentals/fraud_detection.md` | 财报舞弊识别 Skill |
| `harness/skills/bundled/fundamentals/valuation_methods.md` | 估值方法 Skill |
| `harness/skills/bundled/fundamentals/growth_quality.md` | 成长质量评估 Skill |
| `harness/skills/bundled/social/sentiment_scoring.md` | 情绪评分 Skill |
| `harness/skills/bundled/social/crowd_behavior.md` | 群体行为分析 Skill |
| `harness/engine/cost_tracker.py` | 从 OpenHarness 零修改复制 |
| `harness/engine/api/usage.py` | 从 OpenHarness 零修改复制 |
| `harness/engine/callbacks.py` | `TokenCountingCallback`（LangChain callback） |
| `harness/context/injector.py` | Screener 原始数据注入器 |
| `harness/context/templates/screener_context.md` | 注入模板 |

### 修改文件

| 文件 | 修改内容 |
|------|---------|
| `tradingagents/screener/models.py:67-73` | `DeepAnalysisResult` 新增 `token_usage: dict` 字段 |
| `tradingagents/screener/deep_analyzer.py:25-50` | `DeepAnalyzer.__init__` 增加 `token_tracker`；`analyze()` 返回值注入 `token_usage` |
| `tradingagents/agents/analysts/market_analyst.py:140-213` | 在 `system_message` 拼接后追加 Skill 内容和 Screener Context |
| `tradingagents/agents/analysts/news_analyst.py:52-120` | 同上 |
| `tradingagents/agents/analysts/fundamentals_analyst.py:同上` | 同上 |
| `tradingagents/agents/analysts/social_media_analyst.py:同上` | 同上 |
| `tradingagents/agents/researchers/bull_researcher.py:同上` | 同上（可选，看是否需要 Skill 强化） |
| `tradingagents/agents/researchers/bear_researcher.py:同上` | 同上 |
| `tradingagents/agents/managers/portfolio_manager.py:同上` | 同上 |
| `tradingagents/agents/risk_mgmt/*.py` | 同上 |
| `tradingagents/agents/trader/trader.py:同上` | 同上 |

---

## 分析师 Skill 映射（聚焦版）

```python
ANALYST_SKILL_MAPPING = {
    "market": ["indicator_library", "trend_patterns", "volume_analysis", "breakout_recognition"],
    "news": ["policy_impact", "sector_rotation", "event_catalyst"],
    "fundamentals": ["fraud_detection", "valuation_methods", "growth_quality"],
    "social": ["sentiment_scoring", "crowd_behavior"],
    # Researchers / Managers / Trader 暂不加载 Skill，保持轻量
}
```

---

## Task 1: P3 可观测性基础设施（成本最低，可最先验证）

**Files:**
- Create: `tradingagents/harness/__init__.py`
- Create: `tradingagents/harness/engine/__init__.py`
- Create: `tradingagents/harness/engine/api/__init__.py`
- Create: `tradingagents/harness/engine/api/usage.py`（从 OpenHarness 复制）
- Create: `tradingagents/harness/engine/cost_tracker.py`（从 OpenHarness 复制）
- Create: `tradingagents/harness/engine/callbacks.py`
- Create: `tests/harness/engine/test_cost_tracker.py`
- Create: `tests/harness/engine/test_callbacks.py`

- [ ] **Step 1: 创建包目录结构**

```python
# tradingagents/harness/__init__.py
"""TradingAgents Harness Layer — Skills Loader, Observability, and Context Injection."""

__all__ = []
```

```python
# tradingagents/harness/engine/__init__.py
from .cost_tracker import CostTracker
from .callbacks import TokenCountingCallback

__all__ = ["CostTracker", "TokenCountingCallback"]
```

```python
# tradingagents/harness/engine/api/__init__.py
from .usage import UsageSnapshot

__all__ = ["UsageSnapshot"]
```

- [ ] **Step 2: 复制 OpenHarness usage.py（零修改）**

```python
# tradingagents/harness/engine/api/usage.py
from pydantic import BaseModel


class UsageSnapshot(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens
```

- [ ] **Step 3: 复制 OpenHarness cost_tracker.py（零修改）**

```python
# tradingagents/harness/engine/cost_tracker.py
from .api.usage import UsageSnapshot


class CostTracker:
    def __init__(self):
        self._usage = UsageSnapshot(input_tokens=0, output_tokens=0)

    def add(self, usage: UsageSnapshot) -> None:
        self._usage = UsageSnapshot(
            input_tokens=self._usage.input_tokens + usage.input_tokens,
            output_tokens=self._usage.output_tokens + usage.output_tokens,
        )

    @property
    def total(self) -> UsageSnapshot:
        return self._usage
```

- [ ] **Step 4: 编写 CostTracker 测试**

```python
# tests/harness/engine/test_cost_tracker.py
import pytest
from tradingagents.harness.engine.api.usage import UsageSnapshot
from tradingagents.harness.engine.cost_tracker import CostTracker


def test_cost_tracker_initial_state():
    tracker = CostTracker()
    assert tracker.total.input_tokens == 0
    assert tracker.total.output_tokens == 0
    assert tracker.total.total_tokens == 0


def test_cost_tracker_add():
    tracker = CostTracker()
    tracker.add(UsageSnapshot(input_tokens=100, output_tokens=50))
    assert tracker.total.input_tokens == 100
    assert tracker.total.output_tokens == 50
    assert tracker.total.total_tokens == 150


def test_cost_tracker_accumulates():
    tracker = CostTracker()
    tracker.add(UsageSnapshot(input_tokens=100, output_tokens=50))
    tracker.add(UsageSnapshot(input_tokens=200, output_tokens=100))
    assert tracker.total.input_tokens == 300
    assert tracker.total.output_tokens == 150
    assert tracker.total.total_tokens == 450
```

- [ ] **Step 5: 运行测试验证 CostTracker**

Run: `pytest tests/harness/engine/test_cost_tracker.py -v`
Expected: PASS

- [ ] **Step 6: 编写 TokenCountingCallback**

```python
# tradingagents/harness/engine/callbacks.py
from langchain_core.callbacks import BaseCallbackHandler

from .cost_tracker import CostTracker
from .api.usage import UsageSnapshot


class TokenCountingCallback(BaseCallbackHandler):
    """捕获每个 LLM 调用的 token 使用量，累积到 CostTracker。"""

    def __init__(self, tracker: CostTracker):
        self.tracker = tracker

    def on_llm_end(self, response, **kwargs) -> None:
        # 兼容 LangChain 不同版本的 usage 提取方式
        usage = None

        # 方式 1: response.llm_output（旧版）
        if hasattr(response, "llm_output") and response.llm_output:
            usage = response.llm_output.get("usage") or response.llm_output

        # 方式 2: response.usage_metadata（1.x 版本）
        if usage is None and hasattr(response, "usage_metadata"):
            meta = response.usage_metadata or {}
            usage = {
                "input_tokens": meta.get("input_tokens", 0),
                "output_tokens": meta.get("output_tokens", 0),
            }

        # 方式 3: 直接从 response 提取
        if usage is None:
            usage = {
                "input_tokens": getattr(response, "prompt_tokens", 0),
                "output_tokens": getattr(response, "completion_tokens", 0),
            }

        snapshot = UsageSnapshot(
            input_tokens=usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0) or usage.get("output_tokens", 0),
        )
        self.tracker.add(snapshot)
```

- [ ] **Step 7: 编写 TokenCountingCallback 测试**

```python
# tests/harness/engine/test_callbacks.py
import pytest
from unittest.mock import MagicMock
from tradingagents.harness.engine.cost_tracker import CostTracker
from tradingagents.harness.engine.callbacks import TokenCountingCallback


class FakeResponse:
    """模拟 LangChain LLM 响应对象"""
    def __init__(self, llm_output=None, usage_metadata=None):
        self.llm_output = llm_output
        self.usage_metadata = usage_metadata


def test_callback_extracts_from_llm_output():
    tracker = CostTracker()
    cb = TokenCountingCallback(tracker)
    response = FakeResponse(llm_output={"usage": {"prompt_tokens": 100, "completion_tokens": 50}})
    cb.on_llm_end(response)
    assert tracker.total.input_tokens == 100
    assert tracker.total.output_tokens == 50


def test_callback_extracts_from_usage_metadata():
    tracker = CostTracker()
    cb = TokenCountingCallback(tracker)
    response = FakeResponse(usage_metadata={"input_tokens": 200, "output_tokens": 80})
    cb.on_llm_end(response)
    assert tracker.total.input_tokens == 200
    assert tracker.total.output_tokens == 80
```

- [ ] **Step 8: 运行测试验证 TokenCountingCallback**

Run: `pytest tests/harness/engine/test_callbacks.py -v`
Expected: PASS

- [ ] **Step 9: 更新 harness/__init__.py 导出**

```python
# tradingagents/harness/__init__.py
"""TradingAgents Harness Layer — Skills Loader, Observability, and Context Injection."""

from .engine import CostTracker, TokenCountingCallback
from .engine.api import UsageSnapshot

__all__ = ["CostTracker", "TokenCountingCallback", "UsageSnapshot"]
```

- [ ] **Step 10: 提交**

```bash
git add tradingagents/harness/ tests/harness/
git commit -m "feat(harness): P3 可观测性基础设施 — CostTracker + TokenCountingCallback"
```

---

## Task 2: Screener Models 更新 — DeepAnalysisResult 增加 token_usage 字段

**Files:**
- Modify: `tradingagents/screener/models.py:67-73`（在 `DeepAnalysisResult` 中增加字段）
- Create: `tests/screener/test_models.py`

- [ ] **Step 1: 读取现有 DeepAnalysisResult 定义**

```python
# 当前 tradingagents/screener/models.py 中的 DeepAnalysisResult（第 67-73 行）：
class DeepAnalysisResult(BaseModel):
    signal_card: SignalCard
    success: bool
    final_decision: Optional[str] = None
    elapsed_seconds: float
    error: str = ""
    final_state_summary: Dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 2: 修改 DeepAnalysisResult，增加 token_usage 字段**

在 `error: str = ""` 之前插入：

```python
    token_usage: Dict[str, int] = Field(
        default_factory=lambda: {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        description="LLM token consumption for this analysis run",
    )
```

完整结果类应为：

```python
class DeepAnalysisResult(BaseModel):
    signal_card: SignalCard
    success: bool
    final_decision: Optional[str] = None
    elapsed_seconds: float
    token_usage: Dict[str, int] = Field(
        default_factory=lambda: {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        description="LLM token consumption for this analysis run",
    )
    error: str = ""
    final_state_summary: Dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 3: 编写测试验证新字段**

```python
# tests/screener/test_models.py
import pytest
from tradingagents.screener.models import DeepAnalysisResult, SignalCard


def test_deep_analysis_result_has_token_usage_field():
    """验证 DeepAnalysisResult 有 token_usage 字段且默认值正确"""
    card = SignalCard(
        ticker="600519.SH",
        raw_code="600519",
        exchange="SH",
        company_name="贵州茅台",
        trade_date="2025-01-10",
        sector_tags=["白酒"],
        concept_tags=["policy_top_stock"],
        strategy_sources=["technical"],
        signal_breakdown=[],
        trigger_reason="test",
        initial_confidence=75.0,
        risk_flags=[],
        screening_score=80.0,
    )
    result = DeepAnalysisResult(
        signal_card=card,
        success=True,
        elapsed_seconds=12.5,
    )
    assert result.token_usage == {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    result.token_usage = {"input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500}
    assert result.token_usage["total_tokens"] == 1500
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/screener/test_models.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tradingagents/screener/models.py tests/screener/test_models.py
git commit -m "feat(screener): DeepAnalysisResult 增加 token_usage 字段"
```

---

## Task 3: DeepAnalyzer 集成 CostTracker 和 TokenCountingCallback

**Files:**
- Modify: `tradingagents/screener/deep_analyzer.py:25-50`（`__init__` 和 `analyze()` 方法）

- [ ] **Step 1: 读取当前 DeepAnalyzer.__init__ 的完整代码（第 25-50 行）**

```python
# 当前 tradingagents/screener/deep_analyzer.py:25-50
class DeepAnalyzer:
    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {}
        deep_config = self.config.get("deep_analyzer", {})
        self.deep_config = DeepAnalyzerConfig(
            max_stocks=deep_config.get("max_stocks", 3),
            delay_between_stocks=deep_config.get("delay_between_stocks", 2.0),
            retry_on_failure=deep_config.get("retry_on_failure", True),
            max_retries=deep_config.get("max_retries", 1),
        )
        self._enable_real_analysis = self._resolve_real_analysis_flag()
```

- [ ] **Step 2: 修改 DeepAnalyzer.__init__，增加 token_tracker 和 callback 初始化**

在 `__init__` 中，`self._enable_real_analysis = self._resolve_real_analysis_flag()` 之后添加：

```python
        # H3 可观测性：初始化 CostTracker 和 TokenCountingCallback
        from tradingagents.harness import CostTracker, TokenCountingCallback
        self._token_tracker = CostTracker()
        self._token_callback = TokenCountingCallback(self._token_tracker)
```

完整 `__init__` 方法应为：

```python
class DeepAnalyzer:
    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {}
        deep_config = self.config.get("deep_analyzer", {})
        self.deep_config = DeepAnalyzerConfig(
            max_stocks=deep_config.get("max_stocks", 3),
            delay_between_stocks=deep_config.get("delay_between_stocks", 2.0),
            retry_on_failure=deep_config.get("retry_on_failure", True),
            max_retries=deep_config.get("max_retries", 1),
        )
        self._enable_real_analysis = self._resolve_real_analysis_flag()
        # H3 可观测性：初始化 CostTracker 和 TokenCountingCallback
        from tradingagents.harness import CostTracker, TokenCountingCallback
        self._token_tracker = CostTracker()
        self._token_callback = TokenCountingCallback(self._token_tracker)
```

- [ ] **Step 3: 修改 analyze() 方法，在创建 TradingAgentsGraph 时传入 callback**

找到 `analyze()` 方法中创建 `TradingAgentsGraph` 的代码：

```python
            ta = TradingAgentsGraph(debug=False, config=graph_config)
```

替换为：

```python
            ta = TradingAgentsGraph(debug=False, config=graph_config, callbacks=[self._token_callback])
```

- [ ] **Step 4: 修改 analyze() 返回值，注入 token_usage**

找到 `analyze()` 方法返回的 `DeepAnalysisResult`，在 `elapsed_seconds=elapsed` 之后添加：

```python
            return DeepAnalysisResult(
                signal_card=signal_card,
                success=True,
                final_decision=decision,
                elapsed_seconds=elapsed,
                token_usage={
                    "input_tokens": self._token_tracker.total.input_tokens,
                    "output_tokens": self._token_tracker.total.output_tokens,
                    "total_tokens": self._token_tracker.total.total_tokens,
                },
                # ... 其余字段保持不变
            )
```

- [ ] **Step 5: 同上，修改 _dry_run() 返回值**

在 `_dry_run()` 返回的 `DeepAnalysisResult` 中，同样增加 `token_usage` 字段（dry_run 时为全零）：

```python
        return DeepAnalysisResult(
            signal_card=signal_card,
            success=True,
            final_decision=decision,
            elapsed_seconds=elapsed,
            token_usage={
                "input_tokens": self._token_tracker.total.input_tokens,
                "output_tokens": self._token_tracker.total.output_tokens,
                "total_tokens": self._token_tracker.total.total_tokens,
            },
            # ... 其余字段保持不变
        )
```

- [ ] **Step 6: 运行现有测试确保没有破坏性变更**

Run: `pytest tests/screener/ -v -k "deep" --tb=short`
Expected: PASS（或已知失败的测试不新增失败）

- [ ] **Step 7: 提交**

```bash
git add tradingagents/screener/deep_analyzer.py
git commit -m "feat(harness): DeepAnalyzer 集成 CostTracker 和 TokenCountingCallback"
```

---

## Task 4: P2 Skills Loader 核心 — types + registry + loader

**Files:**
- Create: `tradingagents/harness/skills/__init__.py`
- Create: `tradingagents/harness/skills/types.py`
- Create: `tradingagents/harness/skills/registry.py`
- Create: `tradingagents/harness/skills/loader.py`
- Create: `tests/harness/skills/test_loader.py`
- Create: `tests/harness/skills/test_registry.py`

- [ ] **Step 1: 创建 skills 包入口**

```python
# tradingagents/harness/skills/__init__.py
"""Skills Loader — 动态发现和加载 .md 技能文件。"""

from .types import SkillDefinition
from .registry import SkillRegistry
from .loader import load_skill_registry, load_skills_from_dirs

__all__ = ["SkillDefinition", "SkillRegistry", "load_skill_registry", "load_skills_from_dirs"]
```

- [ ] **Step 2: 创建 SkillDefinition Pydantic 模型**

```python
# tradingagents/harness/skills/types.py
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SkillDefinition(BaseModel):
    """一个技能的定义，包含元数据和内容。"""

    name: str = Field(description="技能唯一名称（如 fraud_detection）")
    description: str = Field(description="技能简短描述，供展示和路由使用")
    category: Optional[str] = Field(default=None, description="技能分类（如 market, fundamentals）")
    applies_to_analyst: List[str] = Field(
        default_factory=list,
        description="适用于哪些分析师类型（如 [fundamentals, news]）",
    )
    version: str = Field(default="1.0", description="技能版本")
    content: str = Field(default="", description="技能的完整 Markdown 内容")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="额外元数据（从 YAML frontmatter 解析）",
    )

    def to_prompt_section(self) -> str:
        """将 Skill 转换为可供注入 Agent prompt 的文本片段。"""
        return f"## Skill: {self.name}\n\n{self.content}"
```

- [ ] **Step 3: 创建 SkillRegistry 内存注册表**

```python
# tradingagents/harness/skills/registry.py
from typing import List, Optional

from .types import SkillDefinition


class SkillRegistry:
    """内存中的 Skill 注册表，支持按名称查询和按分析师类型过滤。"""

    def __init__(self):
        self._skills: Dict[str, SkillDefinition] = {}

    def register(self, skill: SkillDefinition) -> None:
        if skill.name in self._skills:
            # 后注册的同名 Skill 覆盖先注册的（支持 override）
            pass
        self._skills[skill.name] = skill

    def get(self, name: str) -> Optional[SkillDefinition]:
        return self._skills.get(name)

    def list_skills(self) -> List[SkillDefinition]:
        return list(self._skills.values())

    def get_skills_for_analyst(self, analyst_type: str) -> List[SkillDefinition]:
        """返回适用于某分析师类型的所有 Skill（按 applies_to_analyst 过滤）。"""
        return [
            s for s in self._skills.values()
            if not s.applies_to_analyst or analyst_type in s.applies_to_analyst
        ]

    def get_skills_by_names(self, names: List[str]) -> List[SkillDefinition]:
        """按名称列表批量获取 Skill，不存在的名称忽略。"""
        return [self._skills[n] for n in names if n in self._skills]
```

- [ ] **Step 4: 创建 SkillLoader 核心加载逻辑**

```python
# tradingagents/harness/skills/loader.py
import re
from pathlib import Path
from typing import List

import yaml

from .types import SkillDefinition
from .registry import SkillRegistry


def load_skill_registry(bundled_dir: Path) -> SkillRegistry:
    """从指定目录加载所有 Skill 文件，构建 Registry 并返回。

    约定：
    - bundled_dir/ 下的每个子目录名 = category（如 market, news, fundamentals）
    - 子目录下每个 *.md 文件 = 一个 Skill
    - 文件名（不含扩展名）= Skill 的 name
    - YAML frontmatter 中 name 字段覆盖文件名
    """
    registry = SkillRegistry()
    if not bundled_dir.exists():
        return registry

    for category_dir in sorted(bundled_dir.iterdir()):
        if not category_dir.is_dir():
            continue
        category = category_dir.name

        for md_file in sorted(category_dir.glob("*.md")):
            skill = _load_skill_file(md_file, category)
            if skill:
                registry.register(skill)

    return registry


def _load_skill_file(path: Path, category: str) -> Optional[SkillDefinition]:
    """加载单个 .md Skill 文件，解析 YAML frontmatter。"""
    content = path.read_text(encoding="utf-8")

    # 解析 YAML frontmatter（格式：--- 开头，--- 结尾）
    name_from_file = path.stem  # 文件名（不含扩展名）作为默认 name
    frontmatter: Dict[str, Any] = {}
    body = content

    if content.startswith("---\n"):
        end_marker = content.find("\n---\n", 4)
        if end_marker != -1:
            yaml_text = content[4:end_marker]
            body = content[end_marker + 5 :]
            try:
                frontmatter = yaml.safe_load(yaml_text) or {}
            except yaml.YAMLError:
                frontmatter = {}

    name = frontmatter.get("name") or name_from_file
    description = frontmatter.get("description", f"Skill: {name}")
    applies_to = frontmatter.get("applies_to_analyst", [])
    version = frontmatter.get("version", "1.0")
    metadata = {k: v for k, v in frontmatter.items() if k not in ("name", "description", "applies_to_analyst", "version")}

    return SkillDefinition(
        name=name,
        description=description,
        category=category,
        applies_to_analyst=applies_to,
        version=version,
        content=body.strip(),
        metadata=metadata,
    )


def load_skills_from_dirs(directories: List[Path]) -> List[SkillDefinition]:
    """从多个目录加载所有 Skill（用于支持 bundled + user 叠加）。"""
    all_skills: List[SkillDefinition] = []
    for directory in directories:
        registry = load_skill_registry(directory)
        all_skills.extend(registry.list_skills())
    return all_skills
```

- [ ] **Step 5: 编写 SkillRegistry 测试**

```python
# tests/harness/skills/test_registry.py
import pytest
from tradingagents.harness.skills.types import SkillDefinition
from tradingagents.harness.skills.registry import SkillRegistry


def test_registry_register_and_get():
    registry = SkillRegistry()
    skill = SkillDefinition(
        name="test_skill",
        description="A test skill",
        category="market",
        applies_to_analyst=["market"],
        content="# Test Skill Content",
    )
    registry.register(skill)
    assert registry.get("test_skill") is skill
    assert registry.get("nonexistent") is None


def test_registry_get_skills_for_analyst():
    registry = SkillRegistry()
    market_skill = SkillDefinition(
        name="m1", description="m", applies_to_analyst=["market"], content=""
    )
    fund_skill = SkillDefinition(
        name="f1", description="f", applies_to_analyst=["fundamentals"], content=""
    )
    both_skill = SkillDefinition(
        name="both", description="b", applies_to_analyst=["market", "fundamentals"], content=""
    )
    registry.register(market_skill)
    registry.register(fund_skill)
    registry.register(both_skill)

    market_skills = registry.get_skills_for_analyst("market")
    assert len(market_skills) == 2
    assert {s.name for s in market_skills} == {"m1", "both"}

    fund_skills = registry.get_skills_for_analyst("fundamentals")
    assert len(fund_skills) == 2
    assert {s.name for s in fund_skills} == {"f1", "both"}
```

- [ ] **Step 6: 编写 SkillLoader 测试（使用临时目录）**

```python
# tests/harness/skills/test_loader.py
import pytest
import tempfile
from pathlib import Path
from tradingagents.harness.skills.loader import load_skill_registry, _load_skill_file


def test_load_skill_registry_from_temp_dir():
    with tempfile.TemporaryDirectory() as tmp:
        bundled = Path(tmp)
        market_dir = bundled / "market"
        market_dir.mkdir()
        (market_dir / "indicator_library.md").write_text(
            """---
name: indicator_library
description: 技术指标选择和使用指南
applies_to_analyst: [market]
version: "1.0"
---
# Indicator Library

This skill covers RSI, MACD, and Bollinger Bands.""",
            encoding="utf-8",
        )
        registry = load_skill_registry(bundled)
        assert len(registry.list_skills()) == 1
        skill = registry.get("indicator_library")
        assert skill is not None
        assert skill.category == "market"
        assert "RSI" in skill.content


def test_load_skill_without_frontmatter():
    """测试无 YAML frontmatter 时，用文件名作为 name。"""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "test.md"
        p.write_text("# No frontmatter skill\nContent here.", encoding="utf-8")
        skill = _load_skill_file(p, "news")
        assert skill.name == "test"
        assert skill.category == "news"
```

- [ ] **Step 7: 运行测试验证**

Run: `pytest tests/harness/skills/ -v`
Expected: PASS

- [ ] **Step 8: 提交**

```bash
git add tradingagents/harness/skills/ tests/harness/skills/
git commit -m "feat(harness): P2 Skills Loader 核心 — types + registry + loader"
```

---

## Task 5: 创建 13 个内置 Skill .md 文件

**Files:**
- Create: `tradingagents/harness/skills/bundled/market/indicator_library.md`
- Create: `tradingagents/harness/skills/bundled/market/trend_patterns.md`
- Create: `tradingagents/harness/skills/bundled/market/volume_analysis.md`
- Create: `tradingagents/harness/skills/bundled/market/breakout_recognition.md`
- Create: `tradingagents/harness/skills/bundled/news/policy_impact.md`
- Create: `tradingagents/harness/skills/bundled/news/sector_rotation.md`
- Create: `tradingagents/harness/skills/bundled/news/event_catalyst.md`
- Create: `tradingagents/harness/skills/bundled/fundamentals/fraud_detection.md`
- Create: `tradingagents/harness/skills/bundled/fundamentals/valuation_methods.md`
- Create: `tradingagents/harness/skills/bundled/fundamentals/growth_quality.md`
- Create: `tradingagents/harness/skills/bundled/social/sentiment_scoring.md`
- Create: `tradingagents/harness/skills/bundled/social/crowd_behavior.md`

**注意：** 以下每个文件都严格按照以下 YAML frontmatter 格式：

```markdown
---
name: <技能名>
description: <简短描述>
applies_to_analyst: [<适用分析师类型>]
version: "1.0"
---

# <技能标题>

<技能正文内容>
```

**以下所有 Skill 文件请逐一创建：**

- [ ] **Step 1: 创建 market/indicator_library.md**

```markdown
---
name: indicator_library
description: 如何选择和使用技术指标 — 四大类别、互补原则、不超过 8 个
applies_to_analyst: [market]
version: "1.0"
---

# Technical Indicator Library

## Indicator Selection Principles

1. **互补不冗余**：选能提供不同维度信息的指标，避免 RSI 和 StochRSI 同用
2. **不超过 8 个**：聚焦最有价值的指标，数量过多反而降低分析质量
3. **解释选因**：说明为什么这个指标适合当前市场环境

## Four Indicator Categories

### 趋势指标（Trend Indicators）
- close_50_sma: 50日均线 — 中期趋势基准。用于判断方向和动态支撑/阻力。结合更快指标使用避免滞后。
- close_200_sma: 200日均线 — 长期趋势基准。用于确认整体趋势，金叉/死叉信号。反应慢，适合战略确认而非频繁交易。
- close_10_ema: 10日指数均线 — 快速短期均线。捕捉动量快速变化和潜在入场点。震荡市中噪声多，配合长周期指标过滤。

### 动量指标（Momentum Indicators）
- macd / macds / macdh: MACD 系列 — 通过 EMA 差值计算动量。用于寻找交叉和背离作为趋势变化信号。低速波市场配合其他指标确认。
- rsi: RSI — 衡量动量，标记超买/超卖。70/30 阈值，关注背离。强趋势中 RSI 可能持续极端，配合趋势分析交叉验证。

### 波动性指标（Volatility Indicators）
- boll / boll_ub / boll_lb: 布林带 — 中轨为 20 SMA，上下轨 2 倍标准差。用于发现突破或反转。结合其他工具确认信号。
- atr: ATR — 平均真实波幅衡量波动性。用于设置止损和调整仓位大小。是被动指标，作为更大风控策略的一部分。

### 成交量指标（Volume Indicators）
- vwma: 成交量加权移动平均 — 将成交量融入价格分析确认趋势。成交量异常时结果可能偏移，结合其他成交量分析使用。
```

- [ ] **Step 2: 创建 market/trend_patterns.md**

```markdown
---
name: trend_patterns
description: 识别和评估市场趋势形态 — 上升/下降/震荡趋势的结构特征
applies_to_analyst: [market]
version: "1.0"
---

# Trend Pattern Recognition

## Trend Structure Anatomy

A healthy uptrend: Higher highs + Higher lows + Expanding volume
A healthy downtrend: Lower highs + Lower lows + Distribution volume

## Key Pattern Types

### Golden Cross / Death Cross
- Golden Cross: 50 SMA crosses above 200 SMA → Bullish confirmation
- Death Cross: 50 SMA crosses below 200 SMA → Bearish confirmation
- Always confirm with volume and momentum

### Trend Continuation Patterns
- Ascending triangle: Flat resistance + rising support → Bullish breakout
- Descending triangle: Falling resistance + flat support → Bearish breakdown
- Flag / Pennant: Short-term consolidation with declining volume → Trend resumes

### Reversal Patterns
- Head and shoulders: Three peaks with middle highest → Trend reversal
- Double top / bottom: Two tests of the same level → Reversal signal
- Divergence: Price makes new high but indicator doesn't → Momentum fading

## Chinese Market Specifics

- A-shares tend to be more momentum-driven than fundamentals
- Policy announcements can create sharp trend reversals
- Main-force capital (主力) patterns in retail-heavy names differ from institutional names
- Volume confirmation is more critical in A-shares due to retail behavior patterns
```

- [ ] **Step 3: 创建 market/volume_analysis.md**

```markdown
---
name: volume_analysis
description: 成交量分析 — 量和价的关系、资金流向、主力行为识别
applies_to_analyst: [market]
version: "1.0"
---

# Volume Analysis Framework

## Core Principles

Volume is the only indicator that cannot be faked in the same way as price — it reflects actual capital flow.

## Key Signals

### Volume-Price Divergence
- Price rises but volume declines → Exhaustion signal, upward move losing conviction
- Price falls but volume declines → Distribution exhaustion, potential reversal
- Price rises on volume surge → Confirmed bullish momentum

### Volume Spike Patterns
- Spike on breakout → Strong conviction, likely sustained
- Spike on decline → Distribution, institutional selling
- Gradual volume increase → Accumulation or distribution phase

### Chinese Market Specifics
- Retail-heavy names: Volume spikes are common and often temporary
- Main-force flow (主力): Large trades by institutional players create distinct volume patterns
- Limit-up days: Often accompanied by retail frenzy, not sustainable
- Margin financing (融资融券): Volume patterns reflect margin position changes

## Volume Confirmation Score

Rate 0-100:
- 80-100: Price and volume in strong alignment
- 50-79: Moderate confirmation, some divergence present
- 20-49: Significant divergence, question trend sustainability
- 0-19: Severe divergence, reversal likely
```

- [ ] **Step 4: 创建 market/breakout_recognition.md**

```markdown
---
name: breakout_recognition
description: 突破形态识别 — 有效突破 vs 假突破、突破后回踩、量价确认
applies_to_analyst: [market]
version: "1.0"
---

# Breakout Recognition Skill

## True vs False Breakout

### Valid Breakout Criteria
- Volume confirmation: Volume at least 1.5x average on breakout
- Close above resistance with at least 3% buffer
- Multiple time frame confirmation (daily + weekly)
- Accompanied by momentum indicator confirmation (RSI divergence)

### False Breakout Patterns
- Spike through resistance on low volume → Likely reversal
- Close right at resistance level → No commitment
- Accompanied by extreme overbought readings → Exhaustion
- Occurs after prolonged consolidation with declining volume → Likely pullback

## Post-Breakout Behavior

### Healthy Retest
- Price pulls back to broken resistance (now support) within 3-5 days
- Volume on retest is lower than breakout volume → Healthy
- Bounces from support with increasing volume → Confirmed breakout

### Failed Breakout
- Price immediately reverses after breakout
- Volume on reversal exceeds breakout volume
- RSI shows negative divergence at breakout point

## China-Specific Considerations

- Limit-up (涨停) breakouts: Require volume analysis on secondary days
- State fund activity can create artificial breakouts that reverse
- Concept/theme-driven breakouts may lack fundamental support
```

- [ ] **Step 5: 创建 news/policy_impact.md**

```markdown
---
name: policy_impact
description: 政策影响分析 — 解读政策信号、评估对股价/行业的影响时效和力度
applies_to_analyst: [news]
version: "1.0"
---

# Policy Impact Analysis

## Policy Signal Hierarchy

### High Impact (Immediate & Sustained)
- Central Bank interest rate decisions
- PBOC reserve requirement ratio (RRR) changes
- Government fiscal stimulus packages
- Industry-specific regulatory changes

### Medium Impact (Delayed, Sector-Specific)
- Provincial/local government policies
- Sector-specific guidelines
- Environmental/ESG regulations

### Low Impact (Transient, Sentiment Only)
- Routine regulatory updates
- Speculation and rumor
- Policy proposal discussions

## Impact Assessment Framework

When analyzing a policy announcement:

1. **Magnitude**: Is this a minor tweak or major structural change?
2. **Implementation timeline**: Immediate effect or phased rollout?
3. **Enforcement probability**: Previous track record of enforcement
4. **Beneficiary vs loser identification**: Which specific companies/sectors win/lose?
5. **Market pricing**: Is the current price already reflecting the policy?

## Chinese Policy Context

- Central Economic Work Conference signals → Full-year implications
- PBOC quarterly reports → Policy direction hints
- NDRC/MIIT announcements → Sector-specific impact
- CSRC regulatory updates → Market structure impact
- Local government stimulus → Regional economy impact
```

- [ ] **Step 6: 创建 news/sector_rotation.md**

```markdown
---
name: sector_rotation
description: 板块轮动分析 — 识别当前市场热点轮换、资金迁移、不同阶段的策略
applies_to_analyst: [news]
version: "1.0"
---

# Sector Rotation Analysis

## Market Cycle Rotation

Early cycle (Recovery): Financials → Real Estate → Consumer Discretionary
Mid cycle (Expansion): Industrials → Materials → Energy
Late cycle (Overheating): Commodities → Utilities
Contraction: Healthcare → Staples → Cash

## Rotation Signal Detection

### Leading Indicators
- Inter-sector relative strength divergence
- Sector ETF fund flow data
- Policy-driven sector allocation shifts

### Lagging Confirmation
- Sector PE ratio expansion
- Volume confirmation in rotated-to sectors
- Media narrative consensus

## China-Specific Rotation Patterns

- Policy cycle drives rotation more than economic cycle
- Tech → Consumer → Financial rotation tied to growth narratives
- "New energy" rotation is multi-year structural, not tactical
- State-owned enterprise (SOE) vs private rotation reflects policy priorities

## News Narrative Analysis

- Distinguish between sustained theme (months) vs tactical trade (days/weeks)
- Identify whether news is cause or effect of sector rotation
- Look for multiple independent news sources confirming rotation thesis
```

- [ ] **Step 7: 创建 news/event_catalyst.md**

```markdown
---
name: event_catalyst
description: 事件催化剂分析 — 财报/并购/政策等事件如何驱动股价，什么信号值得重视
applies_to_analyst: [news]
version: "1.0"
---

# Event Catalyst Analysis

## Event Categories and Impact

### High-Impact Events
- Earnings surprise >10%: Immediate price repricing
- M&A announcement: Premium valuation + deal certainty risk
- Management change: Leadership credibility re-rating
- Regulatory penalty: Business model risk reassessment

### Medium-Impact Events
- Contract wins (large, strategic): Long-term revenue visibility
- Product launches: Market acceptance signal
- Strategic partnership: Market expansion potential

### Low-Impact Events
- Routine SEC/regulatory filings
- Analyst day presentations (without new material info)
- Minor product updates

## Catalysts by Time Horizon

### Immediate (0-5 days)
- Earnings release and guidance
- Major product announcement
- Regulatory decision
- M&A deal closing

### Short-term (1-4 weeks)
- Industry conference presentations
- Conference call substance
- Management roadshow signals

### Medium-term (1-3 months)
- Product launch results
- Policy implementation details
- Competitive landscape changes

## Pre-Event vs Post-Event Behavior

- Pre-event: Price drift in anticipation direction + IV expansion
- Post-event: Volume surge + directional move
- Gap analysis: Open vs previous close = immediate event repricing
```

- [ ] **Step 8: 创建 fundamentals/fraud_detection.md**

```markdown
---
name: fraud_detection
description: 财务报表舞弊识别 — 常见手法、异常信号清单、核查方法
applies_to_analyst: [fundamentals]
version: "1.0"
---

# Financial Fraud Detection Skill

## Common Fraud Mechanisms in Chinese Listed Companies

### Revenue Manipulation
- Phantom revenue: Fictitious customers, round-trip transactions
- Channel stuffing: Pushing excess inventory to distributors before quarter-end
- Bill-and-hold: Recording revenue before delivery
- Related-party transactions at non-market prices

### Asset Inflation
- Inventory overstatement: Counting non-existent or worthless inventory
- Receivables fabrication: Fake customer receivables
- Fixed asset inflation: Overvaluing property or capitalizing expenses
- Goodwill impairment manipulation

### Cash Flow Discrepancies
- Operating cash flow consistently negative while net income positive → Quality of earnings concern
- Unusual working capital changes → Operating cycle manipulation
- Large unexplained variations between net income and operating cash flow

## Red Flag Checklist

- Accounts receivable growing faster than revenue
- Inventory growing faster than revenue
- Operating cash flow persistently negative despite positive net income
- Frequent changes in auditors or accounting policies
- Large, unexplained transactions with related parties
- Revenue recognition timing manipulation
- Unrealistic margin improvements vs peers
- "Too good to be true" financial metrics

## Analysis Steps

1. Cross-reference revenue growth with accounts receivable growth
2. Check inventory-to-revenue ratio trend vs industry peers
3. Calculate cash conversion cycle changes
4. Examine auditor change history and audit fee trends
5. Screen for related-party transaction disclosures
6. Compare gross margin trajectory vs industry
```

- [ ] **Step 9: 创建 fundamentals/valuation_methods.md**

```markdown
---
name: valuation_methods
description: 估值方法选择 — PE/PB/PS/DCFF/PEG 等方法的适用场景和局限
applies_to_analyst: [fundamentals]
version: "1.0"
---

# Valuation Methods Reference

## Method Selection by Context

### PE Ratio (P/E)
- Best for: Stable, mature companies with predictable earnings
- Not suitable for: Loss-making, highly cyclical, or asset-heavy companies
- China context: A-share PE often higher than developed markets due to growth premium

### PB Ratio (P/B)
- Best for: Financial institutions, asset-heavy businesses, distressed companies
- Not suitable for: Intangible-heavy businesses (tech, consumer brands)
- China context: Banks often trade below book due to NPL concerns

### PS Ratio (P/S)
- Best for: High-growth pre-profit companies
- Not suitable for: Low-margin, capital-intensive businesses
- China context: Internet/platform companies often evaluated on PS

### DCF (Discounted Cash Flow)
- Best for: Companies with stable, predictable cash flows
- Requires: Reliable terminal growth rate and WACC estimates
- Limitation: Extremely sensitive to assumptions

### PEG Ratio
- Best for: Growth companies where P/E overstates premium
- Formula: PE / (Annual EPS Growth * 100)
- Rule of thumb: PEG < 1 = potentially undervalued; PEG > 2 = potentially overvalued

## Relative Valuation Framework

Always compare:
1. Current vs historical average
2. vs industry peers (size/growth/margin adjusted)
3. vs domestic vs global comparable companies
```

- [ ] **Step 10: 创建 fundamentals/growth_quality.md**

```markdown
---
name: growth_quality
description: 成长质量评估 — 区分真成长和伪成长，内生增长 vs 并购扩张
applies_to_analyst: [fundamentals]
version: "1.0"
---

# Growth Quality Assessment

## Sustainable vs Unsustainable Growth

### Sustainable Growth Indicators
- Revenue growth driven by organic market share gains
- EBITDA margin improvement from operating leverage
- Cash conversion improving with scale
- R&D intensity supporting future product pipeline

### Unsustainable Growth Red Flags
- Growth driven entirely by acquisition accounting
- Margin improvement from cost-cutting而非 revenue expansion
- Revenue recognition timing acceleration
- Channel stuffing or end-user demand inflation
- Leverage-driven acquisition growth

## Quality Growth Metrics

### Organic Revenue Growth
= (Revenue - Revenue from acquisitions) / Prior period revenue (organic)

### R&D as % of Revenue
- Tech/Healthcare: Higher R&D% expected (10-20%)
- Traditional sectors: Lower R&D% acceptable (1-3%)

### Capital Efficiency (ROIC - WACC)
- ROIC > WACC: Value-creating growth
- ROIC < WACC: Value-destroying growth regardless of growth rate

### Cash Conversion
= Operating Cash Flow / Net Income
- > 1: High quality (cash exceeds accounting profit)
- < 0.8: Quality concern (accrual-based earnings not converting to cash)

## China-Specific Growth Context

- SOE growth often policy-driven rather than market-driven
- Private enterprise growth more organic but more volatile
- Acquiring growth in China: Integration risk is high due to cultural/management differences
```

- [ ] **Step 11: 创建 social/sentiment_scoring.md**

```markdown
---
name: sentiment_scoring
description: 社交媒体情绪评分 — 从舆情数据中提取有效信号，过滤噪声
applies_to_analyst: [social]
version: "1.0"
---

# Social Sentiment Scoring

## Sentiment Signal Hierarchy

### High-Value Sentiment Signals
- Analyst estimate revisions (buy/sell recommendation changes)
- Insider buying/selling ratio
- Institutional holding changes
- Short interest changes

### Medium-Value Sentiment Signals
- Forum/社区 sentiment trends (雪球/东财)
- News sentiment (positive/negative/neutral ratio)
- Search volume correlation

### Noise-Heavy Signals
- Individual retail tweets/posts
- Short-term social media trends
- One-off viral posts

## Scoring Framework

Rate sentiment on -100 to +100 scale:
- +80 to +100: Extremely bullish consensus, reversal risk
- +40 to +79: Moderately bullish, supportive for price
- -39 to +39: Neutral, no directional signal
- -79 to -40: Moderately bearish, headwind for price
- -100 to -80: Extremely bearish, potential reversal opportunity

## China Social Media Specifics

- 雪球 (Xueqiu): More institutional/serious retail, higher signal quality
- 东财股吧: Retail-heavy, high noise, trend-following behavior
- Weibo/WeChat: Faster signal propagation but less detailed
- 东方财富 choice data: Fund flow sentiment indicators

## Sentiment vs Price Divergence

- Sentiment extremely bullish but price declining → Reversal likely
- Sentiment extremely bearish but price stable → Contrarian buy signal
- Sentiment neutral but price trending → Price leads sentiment
```

- [ ] **Step 12: 创建 social/crowd_behavior.md**

```markdown
---
name: crowd_behavior
description: 群体行为分析 — 识别散户情绪过热、机构动向、羊群效应的市场信号
applies_to_analyst: [social]
version: "1.0"
---

# Crowd Behavior Analysis

## Crowd vs Smart Money Indicators

### Signs of Retail Crowd Dominance
- Limit-up board appearances on low-float names
- Explosion of new stock accounts during bull markets
- Margin financing surge
- Retail-heavy name outperformance vs indices
- Forum sentiment reaching extreme optimism

### Signs of Institutional/Smart Money Activity
- Dark pool data showing block trades
- Options market positioning (put/call ratio)
- ETF flow direction (inflows = bullish, outflows = bearish)
- 主力资金 (main-force) flow indicators

## Behavioral Biases in Chinese Markets

### Home Bias
- A-shares: Strong retail participation creates idiosyncratic behavior
- Foreign investors (北向资金) often provide counter-consensus signals

### Herding Patterns
- Sector rotation in A-shares often abrupt due to policy surprises
- "Concept stocks" (概念股) prone to sudden herd behavior
- Once a theme is "discovered" by retail, moves are sharp and quick

### Disposition Effect
- Retail investors tend to sell winners too early and hold losers too long
- This creates support at profit-taking levels and resistance at cost basis

## Crowd Behavior Scoring

Evaluate:
1. Margin financing balance trend (increasing = crowd bullish)
2. New stock account growth rate
3. Forum activity levels for the stock/topic
4. Daily volume vs historical average
5. Price momentum strength
```

- [ ] **Step 13: 提交所有 Skill 文件**

```bash
git add tradingagents/harness/skills/bundled/
git commit -m "feat(harness): P2 内置 13 个金融领域 Skill 文件（聚焦版）"
```

---

## Task 6: SkillInjector — Skill 内容注入到 Agent prompt

**Files:**
- Create: `tradingagents/harness/skills/injector.py`
- Create: `tests/harness/skills/test_injector.py`
- Modify: `tradingagents/harness/skills/__init__.py`

- [ ] **Step 1: 创建 SkillInjector**

```python
# tradingagents/harness/skills/injector.py
from pathlib import Path
from typing import Dict, List, Optional

from .types import SkillDefinition
from .registry import SkillRegistry
from .loader import load_skill_registry


# 分析师类型 → Skill 名称列表（聚焦版）
ANALYST_SKILL_MAPPING: Dict[str, List[str]] = {
    "market": ["indicator_library", "trend_patterns", "volume_analysis", "breakout_recognition"],
    "news": ["policy_impact", "sector_rotation", "event_catalyst"],
    "fundamentals": ["fraud_detection", "valuation_methods", "growth_quality"],
    "social": ["sentiment_scoring", "crowd_behavior"],
}


class SkillInjector:
    """将 Skill 内容注入到 Agent system prompt 的工具类。

    使用方式：
        injector = SkillInjector(bundled_skills_dir)
        prompt_addition = injector.build_skill_section("market")
        # 然后在 analyst 的 system_message 末尾拼接 prompt_addition
    """

    def __init__(self, bundled_dir: Optional[Path] = None):
        if bundled_dir is None:
            bundled_dir = Path(__file__).parent / "bundled"
        self.registry = load_skill_registry(bundled_dir)

    def build_skill_section(self, analyst_type: str) -> str:
        """为指定分析师类型构建 Skill 内容文本。

        Returns:
            Markdown 格式的 Skill 内容片段，可直接拼接到 system prompt。
        """
        skill_names = ANALYST_SKILL_MAPPING.get(analyst_type, [])
        skills = self.registry.get_skills_by_names(skill_names)

        if not skills:
            return ""

        sections = [
            "# Analytical Skills Available",
            "",
        ]
        for skill in skills:
            sections.append(skill.to_prompt_section())
            sections.append("")

        return "\n".join(sections)

    def inject_into_prompt(
        self,
        analyst_type: str,
        existing_prompt: str,
        add_header: bool = True,
    ) -> str:
        """将 Skill 内容注入到已有的 system prompt 末尾。

        Args:
            analyst_type: 分析师类型（market/news/fundamentals/social）
            existing_prompt: 已有的 system prompt 字符串
            add_header: 是否在 Skill 内容前加注释标记
        """
        skill_section = self.build_skill_section(analyst_type)
        if not skill_section:
            return existing_prompt

        header = (
            "\n\n"
            + "=" * 60 + "\n"
            + "## INJECTED ANALYTICAL SKILLS\n"
            + "=" * 60 + "\n"
        )
        return existing_prompt + header + skill_section
```

- [ ] **Step 2: 编写 SkillInjector 测试**

```python
# tests/harness/skills/test_injector.py
import pytest
import tempfile
from pathlib import Path
from tradingagents.harness.skills.injector import SkillInjector, ANALYST_SKILL_MAPPING


def test_injector_loads_skills_from_bundled_dir():
    with tempfile.TemporaryDirectory() as tmp:
        bundled = Path(tmp)
        market_dir = bundled / "market"
        market_dir.mkdir()
        (market_dir / "test_skill.md").write_text(
            """---
name: test_skill
description: A test skill
applies_to_analyst: [market]
---
# Test Skill

This is test content.""",
            encoding="utf-8",
        )
        injector = SkillInjector(bundled)
        section = injector.build_skill_section("market")
        assert "test_skill" in section
        assert "Test Skill" in section


def test_inject_into_prompt_adds_content():
    with tempfile.TemporaryDirectory() as tmp:
        bundled = Path(tmp)
        market_dir = bundled / "market"
        market_dir.mkdir()
        (market_dir / "m1.md").write_text(
            """---
name: m1
description: m1 desc
applies_to_analyst: [market]
---
Content of m1.""",
            encoding="utf-8",
        )
        injector = SkillInjector(bundled)
        existing = "You are a market analyst."
        result = injector.inject_into_prompt("market", existing)
        assert "You are a market analyst." in result
        assert "Content of m1" in result
        assert "INJECTED ANALYTICAL SKILLS" in result


def test_analyst_skill_mapping_defined():
    assert "market" in ANALYST_SKILL_MAPPING
    assert "news" in ANALYST_SKILL_MAPPING
    assert "fundamentals" in ANALYST_SKILL_MAPPING
    assert "social" in ANALYST_SKILL_MAPPING
    assert len(ANALYST_SKILL_MAPPING["market"]) == 4
    assert len(ANALYST_SKILL_MAPPING["fundamentals"]) == 3
```

- [ ] **Step 3: 运行测试验证**

Run: `pytest tests/harness/skills/test_injector.py -v`
Expected: PASS

- [ ] **Step 4: 更新 harness/skills/__init__.py 导出 SkillInjector**

在 `__all__` 中添加 `SkillInjector` 和 `ANALYST_SKILL_MAPPING`：

```python
from .injector import SkillInjector, ANALYST_SKILL_MAPPING
__all__ = ["SkillDefinition", "SkillRegistry", "load_skill_registry", "SkillInjector", "ANALYST_SKILL_MAPPING"]
```

- [ ] **Step 5: 提交**

```bash
git add tradingagents/harness/skills/injector.py tests/harness/skills/test_injector.py
git commit -m "feat(harness): SkillInjector — Skill 内容注入到 Agent prompt"
```

---

## Task 7: Screener Context 注入器

**Files:**
- Create: `tradingagents/harness/context/__init__.py`
- Create: `tradingagents/harness/context/injector.py`
- Create: `tests/harness/context/test_injector.py`

- [ ] **Step 1: 创建 context 包入口**

```python
# tradingagents/harness/context/__init__.py
"""Screener Context Injection — 将扫描结果选择性注入 Agent prompt。"""

from .injector import ScreenerContextInjector

__all__ = ["ScreenerContextInjector"]
```

- [ ] **Step 2: 创建 ScreenerContextInjector**

```python
# tradingagents/harness/context/injector.py
from typing import Any, Dict, List, Optional

from tradingagents.screener.models import SignalCard, SignalEvidence


class ScreenerContextInjector:
    """将 Screener 扫描结果选择性注入到 Agent prompt。

    注入范围（选择性）：
    1. 技术指标 raw_metrics（来自 technical signal_breakdown）
    2. 资金质量标签和评分（来自 smart_money signal_breakdown）
    3. 概念/板块标签
    4. 风险标志
    5. 综合评分和置信度
    """

    def build_context(self, signal_card: SignalCard) -> str:
        """为单个 SignalCard 构建 Markdown 上下文文本。"""
        parts = [
            "# Screener Scan Results",
            f"## {signal_card.ticker} — {signal_card.company_name or signal_card.ticker}",
            f"**Overall Score:** {signal_card.screening_score:.1f}  **Confidence:** {signal_card.initial_confidence:.1f}",
            "",
        ]

        # 1. Sector & Concept Tags
        if signal_card.sector_tags or signal_card.concept_tags:
            parts.append("## Tags")
            if signal_card.sector_tags:
                parts.append(f"- Sectors: {', '.join(signal_card.sector_tags)}")
            if signal_card.concept_tags:
                parts.append(f"- Concepts: {', '.join(signal_card.concept_tags)}")
            parts.append("")

        # 2. Technical Metrics（选择性）
        tech_metrics = self._extract_metrics(signal_card, "technical")
        if tech_metrics:
            parts.append("## Technical Metrics")
            for key, value in sorted(tech_metrics.items()):
                if key not in ("structure_risk_score", "trend_consistency_score"):
                    parts.append(f"- {key}: {value}")
            parts.append("")

        # 3. Capital Quality（选择性）
        capital_metrics = self._extract_metrics(signal_card, "smart_money")
        if capital_metrics:
            parts.append("## Capital Quality")
            capital_tag = signal_card.evidence_snapshot.get("capital_quality_tag", "unknown")
            parts.append(f"- Quality Tag: {capital_tag}")
            for key in ("heat_quality_gap_score", "capital_quality_weight", "risk_constraint_score", "continuity_score"):
                if key in capital_metrics:
                    parts.append(f"- {key}: {capital_metrics[key]}")
            parts.append("")

        # 4. Risk Flags
        if signal_card.risk_flags:
            parts.append("## Risk Flags")
            for flag in signal_card.risk_flags:
                parts.append(f"- {flag}")
            parts.append("")

        # 5. Evidence Sources
        if signal_card.strategy_sources:
            parts.append(f"**Signal Sources:** {', '.join(signal_card.strategy_sources)}")

        return "\n".join(parts)

    def _extract_metrics(self, card: SignalCard, strategy: str) -> Dict[str, Any]:
        """从 signal_breakdown 中提取指定 strategy 的 raw_metrics。"""
        for evidence in card.signal_breakdown:
            if evidence.strategy == strategy:
                return evidence.raw_metrics or {}
        return {}
```

- [ ] **Step 3: 编写 ScreenerContextInjector 测试**

```python
# tests/harness/context/test_injector.py
import pytest
from tradingagents.screener.models import SignalCard, SignalEvidence
from tradingagents.harness.context.injector import ScreenerContextInjector


def test_injector_builds_basic_context():
    card = SignalCard(
        ticker="600519.SH",
        raw_code="600519",
        exchange="SH",
        company_name="贵州茅台",
        trade_date="2025-01-10",
        sector_tags=["白酒"],
        concept_tags=["政策龙头", "capital_quality_high"],
        strategy_sources=["technical", "policy"],
        signal_breakdown=[],
        trigger_reason="policy_top_stock",
        initial_confidence=82.5,
        risk_flags=["trend_structure_extended"],
        screening_score=88.0,
    )
    injector = ScreenerContextInjector()
    ctx = injector.build_context(card)
    assert "600519.SH" in ctx
    assert "贵州茅台" in ctx
    assert "白酒" in ctx
    assert "88.0" in ctx
    assert "trend_structure_extended" in ctx


def test_injector_extracts_technical_metrics():
    card = SignalCard(
        ticker="000001.SZ",
        raw_code="000001",
        exchange="SZ",
        company_name="平安银行",
        trade_date="2025-01-10",
        sector_tags=["银行"],
        concept_tags=["估值修复"],
        strategy_sources=["technical"],
        signal_breakdown=[
            SignalEvidence(
                strategy="technical",
                score=75.0,
                reason="",
                raw_metrics={"rsi": 65, "macd_signal": "golden_cross", "bollinger_position": 0.55},
            )
        ],
        trigger_reason="technical_breakout",
        initial_confidence=70.0,
        risk_flags=[],
        screening_score=75.0,
    )
    injector = ScreenerContextInjector()
    ctx = injector.build_context(card)
    assert "rsi" in ctx
    assert "65" in ctx
    assert "golden_cross" in ctx
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/harness/context/ -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tradingagents/harness/context/ tests/harness/context/
git commit -m "feat(harness): ScreenerContextInjector — 选择性注入技术指标/资金质量/概念标签/风险标志"
```

---

## Task 8: 将 Skill + Screener Context 集成到各 Analyst Agent

**Files:**
- Modify: `tradingagents/agents/analysts/market_analyst.py:209-213`（在 system_message 拼接后追加 Skill + Screener Context）
- Modify: `tradingagents/agents/analysts/news_analyst.py:同上`
- Modify: `tradingagents/agents/analysts/fundamentals_analyst.py:同上`
- Modify: `tradingagents/agents/analysts/social_media_analyst.py:同上`

**统一的修改模式（每个 analyst 文件都相同）：**

找到 `system_message` 构建完成的最后几行，在 `.get_language_instruction()` 之后追加：

```python
        # H3: 注入 Skill 和 Screener Context
        from tradingagents.harness.skills import SkillInjector
        from tradingagents.harness.context import ScreenerContextInjector

        # 获取 Screener Context（如果存在）
        screener_context_str = ""
        if state.get("screener_context"):
            sc_injector = ScreenerContextInjector()
            signal_card = state.get("screener_context", {}).get("signal_card")
            if signal_card:
                screener_context_str = "\n\n" + sc_injector.build_context(signal_card)

        # 获取 Skill 内容
        skill_injector = SkillInjector()
        skill_section = skill_injector.build_skill_section("market")  # ← 替换为对应 analyst type

        # 追加到 system_message
        system_message = system_message + screener_context_str + "\n" + skill_section
```

**注意：** 以下每个文件请逐一完成修改：

- [ ] **Step 1: 修改 market_analyst.py**

在 `market_analyst_node` 函数中，找到：
```python
            + get_language_instruction()
        )
```
在其后追加 Skill + Screener Context 注入代码。`analyst_type` 为 `"market"`。

- [ ] **Step 2: 修改 news_analyst.py**

同上，`analyst_type` 为 `"news"`。

- [ ] **Step 3: 修改 fundamentals_analyst.py**

同上，`analyst_type` 为 `"fundamentals"`。

- [ ] **Step 4: 修改 social_media_analyst.py**

同上，`analyst_type` 为 `"social"`。

- [ ] **Step 5: 运行测试**

Run: `pytest tests/agents/ -v -k "analyst" --tb=short 2>&1 | head -50`
Expected: 无新增失败（关键测试 PASS）

- [ ] **Step 6: 提交**

```bash
git add tradingagents/agents/analysts/market_analyst.py tradingagents/agents/analysts/news_analyst.py tradingagents/agents/analysts/fundamentals_analyst.py tradingagents/agents/analysts/social_media_analyst.py
git commit -m "feat(harness): Skill + Screener Context 集成到 4 个 Analyst Agent"
```

---

## Task 9: 更新 harness/__init__.py 完整导出

**Files:**
- Modify: `tradingagents/harness/__init__.py`

- [ ] **Step 1: 更新完整导出**

```python
# tradingagents/harness/__init__.py
"""TradingAgents Harness Layer — Skills Loader, Observability, and Context Injection."""

from .engine import CostTracker, TokenCountingCallback
from .engine.api import UsageSnapshot
from .skills import SkillDefinition, SkillRegistry, SkillInjector, ANALYST_SKILL_MAPPING
from .context import ScreenerContextInjector

__all__ = [
    # Engine
    "CostTracker",
    "TokenCountingCallback",
    "UsageSnapshot",
    # Skills
    "SkillDefinition",
    "SkillRegistry",
    "SkillInjector",
    "ANALYST_SKILL_MAPPING",
    # Context
    "ScreenerContextInjector",
]
```

- [ ] **Step 2: 提交**

```bash
git add tradingagents/harness/__init__.py
git commit -m "chore(harness): 更新 __init__.py 完整导出"
```

---

## Task 10: 集成测试和端到端验证

**Files:**
- Create: `tests/harness/test_integration.py`

- [ ] **Step 1: 编写集成测试**

```python
# tests/harness/test_integration.py
"""端到端集成测试：验证 Skill + Screener Context + CostTracker 完整链路。"""
import pytest
from unittest.mock import MagicMock
from tradingagents.screener.models import SignalCard, SignalEvidence, DeepAnalysisResult
from tradingagents.harness import (
    CostTracker,
    TokenCountingCallback,
    SkillInjector,
    ScreenerContextInjector,
)
from tradingagents.harness.skills import load_skill_registry
from pathlib import Path


def test_full_pipeline():
    """验证从 Skill 注册 → 注入 → CostTracker 的完整流程。"""
    # 1. CostTracker
    tracker = CostTracker()
    tracker.add(
        __import__("tradingagents.harness.engine.api.usage", fromlist=["UsageSnapshot"])
        .UsageSnapshot(input_tokens=1000, output_tokens=500)
    )
    assert tracker.total.total_tokens == 1500

    # 2. SkillInjector（使用内置 bundled 路径）
    injector = SkillInjector()
    skill_section = injector.build_skill_section("market")
    assert "indicator_library" in skill_section or "Analytical Skills" in skill_section

    # 3. ScreenerContextInjector
    card = SignalCard(
        ticker="600519.SH",
        raw_code="600519",
        exchange="SH",
        company_name="贵州茅台",
        trade_date="2025-01-10",
        sector_tags=["白酒"],
        concept_tags=["政策龙头"],
        strategy_sources=["technical", "policy"],
        signal_breakdown=[],
        trigger_reason="test",
        initial_confidence=80.0,
        risk_flags=["trend_structure_extended"],
        screening_score=85.0,
    )
    sc_injector = ScreenerContextInjector()
    ctx = sc_injector.build_context(card)
    assert "600519.SH" in ctx
    assert "白酒" in ctx

    # 4. 验证三者可以组合
    combined = "Base prompt\n" + ctx + "\n" + skill_section
    assert len(combined) > len("Base prompt")
    assert "600519.SH" in combined


def test_token_counting_callback_mocks_llm_response():
    """验证 TokenCountingCallback 能正确处理模拟的 LangChain 响应。"""
    tracker = CostTracker()
    cb = TokenCountingCallback(tracker)

    class FakeResponse:
        def __init__(self, usage_dict):
            self.llm_output = {"usage": usage_dict}

    cb.on_llm_end(FakeResponse({"prompt_tokens": 500, "completion_tokens": 250}))
    assert tracker.total.input_tokens == 500
    assert tracker.total.output_tokens == 250
```

- [ ] **Step 2: 运行集成测试**

Run: `pytest tests/harness/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: 运行完整 harness 测试套件**

Run: `pytest tests/harness/ -v --tb=short`
Expected: ALL PASS

- [ ] **Step 4: 提交**

```bash
git add tests/harness/test_integration.py
git commit -m "test(harness): 端到端集成测试"
```

---

## 实施检查清单

### 完成后自检

- [ ] `tradingagents/harness/` 目录结构完整
- [ ] 13 个内置 Skill .md 文件全部创建
- [ ] `DeepAnalysisResult` 有 `token_usage` 字段
- [ ] `DeepAnalyzer` 集成了 `CostTracker` + `TokenCountingCallback`
- [ ] 4 个 Analyst Agent（market/news/fundamentals/social）都注入了 Skill 和 Screener Context
- [ ] `ANALYST_SKILL_MAPPING` 映射正确（market→4个，news→3个，fundamentals→3个，social→2个）
- [ ] 所有 `tests/harness/` 测试 PASS
- [ ] 无新的 linter 错误

### 规格覆盖检查

| 规格要求 | 对应 Task |
|---------|---------|
| LangGraph callback + CostTracker | Task 1 + Task 3 |
| DeepAnalysisResult 含 token_usage | Task 2 |
| Skills Loader 核心（types/registry/loader） | Task 4 |
| 13 个内置 Skill .md 文件 | Task 5 |
| SkillInjector | Task 6 |
| ScreenerContextInjector | Task 7 |
| Skill + Context 集成到 Analyst Agent | Task 8 |
| 集成测试 | Task 10 |
