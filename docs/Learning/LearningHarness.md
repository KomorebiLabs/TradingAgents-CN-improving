# Harness 架构适配分析：P1/P2/P3 子系统（修订版）

> 本文档深入分析 OpenHarness 的 P1 Tool Registry、P2 Skills Loader、P3 可观测性 三大子系统，解答：**它们是什么、我们是否需要、如何适配、有哪些改进点**。
>
> **修订说明**：基于用户反馈，本版本纠正了多处关键误解，包括：Prompt/ 目录的实际归属、Agent 提示词的真实来源、工具参数结构等。

---

## 一、P1 — Tool Registry（工具注册表）

### 1.1 什么是 Tool Registry？

Tool Registry 是一种**工具抽象与统一管理机制**，核心是：

```python
class BaseTool(ABC):
    name: str
    description: str
    input_model: type[BaseModel]      # Pydantic 输入校验

    @abstractmethod
    async def execute(self, arguments, context) -> ToolResult:
        ...

class ToolRegistry:
    def register(self, tool: BaseTool) -> None: ...
    def get(self, name: str) -> BaseTool | None: ...
    def list_tools(self) -> list[BaseTool]: ...
    def to_api_schema(self) -> list[dict]: ...
```

**关键特性：**

- **统一注册**：所有工具通过 `ToolRegistry.register()` 集中注册
- **自描述能力**：每个工具自带 `name` + `description` + `input_model`（Pydantic 模型），可自动生成 JSON Schema
- **标准化结果**：`ToolResult` 统一封装 `{output, is_error, metadata}`
- **上下文传递**：`ToolExecutionContext` 携带执行上下文
- **API Schema 导出**：一次性导出所有工具的 API 描述

### 1.2 我们项目有哪些工具？

| 工具文件 | 工具数量 | 数据源 |
|---------|---------|--------|
| `core_stock_tools.py` | 1 个 | `get_stock_data` — 股票行情 |
| `technical_indicators_tools.py` | 1 个 | `get_indicators` — 技术指标 |
| `fundamental_data_tools.py` | 4 个 | 资产负债表、现金流量表等 |
| `news_data_tools.py` | 5 个 | 新闻、公告、内幕交易 |
| `cn_sector_news_tools.py` | 6 个 | 板块新闻（科技/新能源/医药等） |
| `cn_macro_tools.py` | 3 个 | 宏观数据 |
| **合计** | **约 20+ 个** | |

**重要澄清**：这些工具的函数签名都是**简单参数**：

```python
def get_stock_data(ticker: str, start_date: str, end_date: str) -> dict
def get_indicators(ticker: str, start_date: str, end_date: str, indicators: list[str]) -> dict
def get_news(ticker: str, start_date: str, end_date: str) -> dict
```

**没有 Pydantic 模型**，参数靠提示词约束。如果引入 BaseTool，需要包装。

### 1.3 适用性分析

#### 是否需要 Tool Registry？

**✅ 强烈建议引入**，核心原因：

| 当前痛点 | Tool Registry 如何解决 |
|---------|----------------------|
| 工具散落在 7 个文件中，无统一入口 | 所有工具注册到 `ToolRegistry` 单例 |
| 工具无 Pydantic 校验，LLM 调用参数靠提示词约束 | 每个工具 `input_model` 自动校验 |
| 新增工具需要在 `get_tools_for_analyst()` 手动注册 | 实现 `register()` 自动发现 |
| 无法列出"系统有哪些可用工具" | `list_tools()` + `to_api_schema()` |
| Screener 的 semantic routing 不知道有哪些工具可用 | Registry 提供工具清单供 Screener 决策 |

#### 具体哪些模块需要接入？

```
Screener（筛选器）
  └── deep_analyzer.py → 需要知道哪些工具可以用于深度分析

LangGraph TradingAgents
  └── agent_utils.py → 当前工具加载逻辑，需要改造为 Registry 驱动
  └── graph/setup.py → 工具节点创建依赖 agent_utils
```

### 1.4 如何适配我们项目

#### 适配策略 1：保留 Lazy Import 机制

OpenHarness 的 `BaseTool` 是**异步**的（`async def execute`），我们现有工具都是**同步**的（直接返回数据）。**不能直接复制**：

```python
# tradingagents/harness/tools/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from pydantic import BaseModel

@dataclass(frozen=True)
class ToolResult:
    output: str
    is_error: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class ToolExecutionContext:
    """适配 TradingAgents 的工具执行上下文"""
    ticker: str = ""
    trade_date: str = ""
    config: dict[str, Any] = field(default_factory=dict)

class BaseTool(ABC):
    """TradingAgents 专用工具基类"""
    name: str
    description: str
    input_model: type[BaseModel] | None = None  # 可选，支持非结构化工具

    @abstractmethod
    def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        """同步执行（我们没有 IO 阻塞场景）"""
        ...

    def to_api_schema(self) -> dict[str, Any]:
        schema = {"name": self.name, "description": self.description}
        if self.input_model:
            schema["input_schema"] = self.input_model.model_json_schema()
        return schema
```

**关键改进**：将 OpenHarness 的 `async def execute` 改为同步 `def execute`。

#### 适配策略 2：保留 Analyst Type 分类

OpenHarness 的 `ToolRegistry` 是扁平的，但我们有 `market`/`social`/`news`/`fundamentals` 四类分析师。**需要扩展**：

```python
class AnalystToolRegistry:
    """按分析师类型分类的工具注册表"""
    def __init__(self):
        self._global = ToolRegistry()  # 全局注册表
        self._by_analyst: dict[str, ToolRegistry] = {
            "market": ToolRegistry(),
            "social": ToolRegistry(),
            "news": ToolRegistry(),
            "fundamentals": ToolRegistry(),
        }

    def register(self, tool: BaseTool, analysts: list[str] | None = None):
        self._global.register(tool)
        if analysts:
            for analyst in analysts:
                if analyst in self._by_analyst:
                    self._by_analyst[analyst].register(tool)

    def get_tools_for_analyst(self, analyst: str) -> list[BaseTool]:
        return self._by_analyst.get(analyst, ToolRegistry()).list_tools()
```

#### 适配策略 3：包装现有工具（无需重写）

```python
class StockDataTool(BaseTool):
    name = "get_stock_data"
    description = "获取股票历史行情数据（K线、成交量等）"
    # input_model = StockDataInput  # 可选，按需添加

    def execute(self, arguments: dict, context: ToolExecutionContext) -> ToolResult:
        from tradingagents.agents.utils.core_stock_tools import get_stock_data as _get_stock_data
        try:
            result = _get_stock_data(
                ticker=context.ticker,
                start_date=arguments.get("start_date", ""),
                end_date=arguments.get("end_date", ""),
            )
            return ToolResult(output=str(result))
        except Exception as e:
            return ToolResult(output="", is_error=True, reason=str(e))
```

### 1.5 适配总结

| 改进项 | 原始 OpenHarness | 适配方向 |
|--------|-----------------|---------|
| 异步 vs 同步 | `async def execute` | 改为同步，保留 lazy import |
| 扁平注册表 | `ToolRegistry` 单一 | 增加 `AnalystToolRegistry` 支持分类 |
| 执行上下文 | `cwd` + `metadata` | 改为 `ticker` + `trade_date` + `config` |
| Hook 集成 | `hook_executor` | 推迟到 P3 阶段集成 |
| 输入模型 | Pydantic 必须 | 可选（简单参数的工具有就用，没有不强求） |

---

## 二、P2 — Skills Loader（技能按需加载系统）

### 2.1 什么是 Skills Loader？

Skills Loader 是一种**从文件系统动态发现和加载技能定义的机制**，核心在 `openharness/skills/loader.py`：

```python
def load_skills_from_dirs(directories):
    for directory in directories:
        for child in root.iterdir():
            skill_path = child / "SKILL.md"      # 子目录/SKILL.md 为一个技能
            content = path.read_text(encoding="utf-8")
            name, description = _parse_skill_markdown(default_name, content)
            skills.append(SkillDefinition(...))
```

**关键特性：**

- **YAML Frontmatter**：`---` 分隔的元数据头，包含 `name`、`description` 等
- **目录级发现**：技能按子目录组织
- **降级解析**：无 frontmatter 时，从 `# 标题` 和首段自动提取
- **优先级加载**：`bundled → user → plugin` 覆盖机制

### 2.2 ⚠️ 关键澄清：我们项目的 Prompt 来源

#### 澄清 1：Prompt/ 目录不是项目的一部分

```
项目根目录/
├── Prompt/                    ← 不存在！这是你个人的 Cursor AI 提示词目录
│   ├── Agent_Coder.md        ← 你的 Cursor Agent 设定，不是项目代码
│   ├── Agent_Leader.md
│   └── Agent_Harness.md      ← 我的设定，不是项目代码
├── tradingagents/             ← 真正的项目代码
│   └── agents/
│       └── analysts/
│           ├── market_analyst.py     ← Agent 提示词的真实来源（Python 字符串）
│           ├── news_analyst.py
│           ├── fundamentals_analyst.py
│           └── social_media_analyst.py
│       └── prompts/
│           ├── harness.py              ← 提示词构建辅助函数
│           └── few_shots.py           ← Few-shot 示例
```

**重要**：你个人的 `Prompt/` 目录（`Agent_Coder.md` 等）是给 Cursor AI 用的提示词，和项目的 Agent 提示词完全无关。项目的 Agent 提示词全部在 `tradingagents/agents/` 下，以**硬编码 Python 字符串**形式存在。

#### 澄清 2：Agent 提示词的真实形态

`tradingagents/agents/analysts/market_analyst.py` 第 171-213 行：

```python
system_message = (
    """You are a trading assistant tasked with analyzing financial markets..."""
    # 4 大类指标的详细说明 + 使用策略 + 输出格式要求（全部硬编码字符串）
    + """ Make sure to append a Markdown table at the end of the report..."""
    + segment_advisory    # 动态注入的仪器画像片段
    + semantic_instruction  # 动态注入的 semantic routing 片段
    + get_language_instruction()
)
```

**结论**：Agent 的 system prompt 是**硬编码 Python 字符串 + 动态注入片段**（`segment_advisory`、`semantic_instruction` 等），没有外部化，没有 YAML frontmatter。

### 2.3 我们项目中"类 Skill"的概念有哪些？

| 概念 | 位置 | 形式 | 是否需要 Skills Loader |
|------|------|------|----------------------|
| Agent system prompt | `analysts/*.py` 中的 `system_message` 字符串 | 硬编码 Python 字符串 | ❌ 你已明确不需要 |
| Semantic routing 指令 | `agent_utils.py` 中的 `build_screener_semantic_instruction()` | 硬编码 Python 函数 | ❌ 你已明确不需要 |
| Instrument skill notes | `agent_utils.py` 中的 `SKILL_INSTRUMENT_NOTES` dict | 硬编码 Python dict | ❌ 你已明确不需要 |
| **场景 A：金融知识技能库** | **无** | **需要新建** | **❓ 待确认** |
| **场景 B：分析师 prompt 片段库** | **analyst/*.py 内部已有** | **Python 字符串** | **❌ 你已明确不需要** |
| **场景 C：Context 文件注入** | **无** | **需要新建** | **❓ 待确认** |

### 2.4 Skills Loader 的潜在应用场景

你提到了两个可能的应用场景：

#### 场景 A：金融知识技能库（给 Screener 的 DeepAnalyzer Agent 用）

**思路**：为 Screener 的深度分析 Agent 建立一个**金融领域知识片段库**，让 Agent 按需加载这些技能。例如：

```
Prompt/skills/
  ├── fraud_detection.md         # "如何识别财务报表舞弊"
  ├── cn_money_flow.md         # "如何分析北向资金"
  ├── sector_rotation.md       # "板块轮动分析方法"
  ├── breakout_patterns.md     # "突破形态识别"
  └── macro_event_impact.md   # "宏观事件对股价的影响"
```

每个 `.md` 文件可以是：

```markdown
---
name: fraud_detection
description: 如何识别财务报表舞弊的常见手法
category: fundamentals
applies_to_analyst: [fundamentals, news]
---
# 财务报表舞弊识别指南

## 常见舞弊手法
1. 虚增收入（虚构客户、提前确认收入）
2. 虚减成本（推迟费用确认、资本化费用）
...
```

**问题**：DeepAnalyzer Agent 怎么使用这些 Skills？是：
- A1. 在调用 DeepAnalyzer 时，通过 `config` 传入相关 Skill 片段作为额外上下文？
- A2. DeepAnalyzer Agent 本身的 system prompt 动态拼接这些 Skill 内容？
- A3. 其他方式？

#### 场景 B：分析师可复用 prompt 片段库（让不同分析师共享）

**思路**：将 `market_analyst.py` 中硬编码的指标说明（4 大类指标 + 使用策略）抽出来，放到 `Prompt/skills/indicator_library.md`，在运行时按分析师类型加载：

```
Prompt/skills/
  ├── indicator_library.md     # 技术指标库（market analyst 用）
  ├── news_sources.md         # 新闻来源说明（news analyst 用）
  └── financial_metrics.md    # 财务指标说明（fundamentals analyst 用）
```

**问题**：这个场景下，`analyst/*.py` 中的 `system_message` 字符串需要改造为从文件加载。你是否认为这是一个值得做的改进？

#### 场景 C：Context 文件注入（OpenHarness 的 CLAUDE.md 理念）

**思路**：在 `Prompt/context/` 目录下放置特定股票的分析上下文文件：

```
Prompt/context/
  ├── 600519_maotai.md        # 贵州茅台的专属分析上下文
  ├── 300750_ymcc.md         # 宁德时代的专属上下文
  └── _template.md            # 通用模板
```

分析时自动发现并注入对应 ticker 的 context 文件。

**问题**：你是否有计划为特定股票维护专属分析上下文文件？

### 2.5 你的核心观点总结

根据你的反馈：

1. **`Prompt/*.md` 是你个人用的 Cursor 提示词**，不是项目代码，不需要改造
2. **Agent 提示词硬编码在 Python 字符串中，理论上没有多大问题** — 你不认为这是痛点
3. **Semantic Routing 是 Python 代码，不是 Skill 文件** — 两者是正交的子系统

**因此，P2 的结论需要你来决定**：

- 如果场景 A（金融知识技能库）或场景 C（Context 文件注入）有实际需求，则需要 Skills Loader
- 如果这两个场景都不需要，则 P2 可以**跳过**

---

## 三、P3 — Agent Loop 可观测性（Hooks + CostTracker）

### 3.1 什么是 Agent Loop 可观测性？

可观测性是指在 Agent 循环执行过程中，**可观测、可追踪、可干预**的能力。OpenHarness 提供：

#### 3.1.1 Hook 机制（`hooks/`）

```python
# hooks/types.py — 零修改直接复用
@dataclass(frozen=True)
class HookResult:
    hook_type: str        # "command", "prompt", "http", "agent"
    success: bool
    output: str = ""
    blocked: bool = False  # 可阻止后续操作
    reason: str = ""
    metadata: dict = field(default_factory=dict)

# hooks/events.py — 事件枚举
class HookEvent(Enum):
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    PRE_AGENT_RUN = "pre_agent_run"
    POST_AGENT_RUN = "post_agent_run"
```

#### 3.1.2 CostTracker（Token 累积器）

```python
# engine/cost_tracker.py — 零修改直接复用
class CostTracker:
    def add(self, usage: UsageSnapshot) -> None: ...
    @property
    def total(self) -> UsageSnapshot: ...

# api/usage.py — 零修改直接复用
class UsageSnapshot(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    @property
    def total_tokens(self) -> int: ...
```

### 3.2 我们项目的可观测性现状

#### 当前状态：`trading_graph.py`

| 能力 | 当前状态 | 缺失 |
|------|---------|------|
| `debug` 模式 | ✅ 有，打印每步 `pretty_print()` | 无法记录到文件 |
| `callbacks` 参数 | ✅ 有，透传给 LLM 构造器 | LangChain callback 不暴露原始参数 |
| Token 统计 | ❌ 无 | 不知道每次调用消耗多少 |
| 成本追踪 | ❌ 无 | 无法估算 dollar cost |
| Hook 点 | ❌ 无 | 无法在分析师调用前后插入自定义逻辑 |
| 审计日志 | 部分有，`event_trail` 只记录阶段切换 | 不记录工具调用详情 |

#### 当前状态：Screener

| 能力 | 当前状态 | 缺失 |
|------|---------|------|
| 日志 | ✅ 有 `_logger` | 仅控制台输出 |
| DeepAnalyzer 追踪 | ❌ 无 | 不知道每个股票分析耗时多久 |
| API 调用计数 | ❌ 无 | 不知道 Stage B 执行了多少次 API |
| Cost control | ❌ 无 | 无法限制单次分析 token 上限 |

### 3.3 你的问题：LangChain Callback 的局限是否是问题？

你提出了一个很好的问题：`hooks/types.py` 和 `engine/cost_tracker.py` 零修改可以直接复制，但 LangChain Callback 的局限是否真的是问题？

#### LangChain Callback 能做什么

LangChain 的 `BaseCallbackHandler` 可以：

```python
class TokenCountingCallback(BaseCallbackHandler):
    def on_llm_end(self, response, **kwargs):
        # ✅ 可以：从 LLM 响应中提取 usage
        usage = response.llm_output.get("usage", {}) if hasattr(response, "llm_output") else {}
        tracker.add(UsageSnapshot(
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        ))
```

#### LangChain Callback 的局限

| 局限 | 影响 | 是否致命 |
|------|------|---------|
| 不暴露原始 tool call 参数 | 无法记录"调用了什么参数" | 🟡 中等（可接受） |
| 不暴露 `PRE_TOOL_USE` 拦截点 | 无法在工具调用前 `blocked=True` | 🟡 中等（我们没有危险工具） |
| 每个 LLM 调用单独回调 | 无法看到完整的 Agent 思维链 | 🟡 中等（Screener 不需要） |

**结论**：对于 Screener + DeepAnalyzer 场景，LangChain Callback **基本够用**，局限不是致命问题。只需要一个 `TokenCountingCallback` 就足够捕获 token 使用量。

### 3.4 你的问题：LangGraph 本身的 Hook/中间件是否足够？

你提到 LangGraph 框架本身也有中间件/Hook 能力。这是关键问题：

**LangGraph 自带的能力 vs OpenHarness Hook 的能力：**

| 能力 | LangGraph 自带 | OpenHarness Hook | 我们需要 |
|------|----------------|-----------------|---------|
| LLM 调用前后拦截 | ✅ `BaseCallback` | ✅ `PRE/POST_AGENT_RUN` | 只需要一种 |
| 工具调用拦截 | ✅ `BaseCallback`（部分） | ✅ `PRE/POST_TOOL_USE` | 只需要一种 |
| `blocked=True` 阻止工具 | ❌ 不支持 | ✅ 支持 | 我们不需要 |
| 全局事件总线 | ❌ 不支持 | ✅ `HookExecutor` | 我们不需要 |
| Token 统计 | ❌ 不自带（要自己算） | ✅ `CostTracker` | 我们需要 |

**关键发现**：LangGraph 的 `BaseCallbackHandler` 和 OpenHarness 的 Hook 是**不同层次的抽象**：

- LangGraph callback 是 **Framework 级别**的拦截
- OpenHarness Hook 是 **Application 级别**的事件总线

**你的直觉是对的**：对于我们的场景，只需要一个 LangChain/LangGraph `BaseCallbackHandler` + `CostTracker` 就够了，不需要引入 OpenHarness 的 `HookExecutor`。

### 3.5 适用性分析

#### 是否需要 CostTracker？

**✅ 强烈需要，零成本引入**：
- `UsageSnapshot` + `CostTracker` 可以零修改直接复制
- LangChain 每次 LLM 调用都返回 `usage` 信息
- 有了 CostTracker 才能做：预算控制、成本估算、执行报告

#### 是否需要 Hook 机制？

**⚠️ 需要进一步澄清**：
- OpenHarness 的 `HookExecutor` 可能**过度设计**
- 我们可能只需要 LangChain `BaseCallbackHandler`
- 但 Screener 的 `deep_analyzer.py` / `merger.py` 目前没有 callback 机制，需要补充

#### 具体哪些模块需要接入？

```
TradingAgentsGraph（核心图）
  └── propagate() → LLM invoke 前后插入 CostTracker
  └── __init__ → 将 callback 传入 LLM 构造器

Screener Engine
  └── deep_analyzer.py → 增加 callback（追踪耗时、token 消耗）
  └── engine.py → 增加 API 调用计数
```

### 3.6 如何适配我们项目

#### 策略 1：零修改复制（纯数据层）

```
openharness/hooks/types.py         → tradingagents/harness/hooks/types.py（零修改）
openharness/engine/cost_tracker.py → tradingagents/harness/engine/cost_tracker.py（零修改）
openharness/api/usage.py           → tradingagents/harness/api/usage.py（零修改）
```

这三个文件是**纯数据结构**，不需要任何本地化改造。

#### 策略 2：构建 LangChain Callback 集成 CostTracker（推荐）

```python
# tradingagents/harness/engine/callbacks.py
from langchain_core.callbacks import BaseCallbackHandler
from tradingagents.harness.engine.cost_tracker import CostTracker
from tradingagents.harness.api.usage import UsageSnapshot

class TokenCountingCallback(BaseCallbackHandler):
    """捕获每个 LLM 调用的 token 使用量"""
    def __init__(self, tracker: CostTracker):
        self.tracker = tracker
        self._llm_call_count = 0

    def on_llm_end(self, response, **kwargs):
        self._llm_call_count += 1
        usage = getattr(response, "llm_output", {}) or {}
        if not usage and hasattr(response, "usage_metadata"):
            usage = getattr(response, "usage_metadata", {}) or {}
        snapshot = UsageSnapshot(
            input_tokens=usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0) or usage.get("output_tokens", 0),
        )
        self.tracker.add(snapshot)
```

在 `TradingAgentsGraph.__init__` 中：

```python
token_tracker = CostTracker()
counting_cb = TokenCountingCallback(token_tracker)
self.callbacks = callbacks + [counting_cb]
```

#### 策略 3：Screener DeepAnalyzer 增加 Callback

```python
# deep_analyzer.py 改进
class DeepAnalyzer:
    def __init__(self, config, callback=None):
        self.callback = callback

    def analyze(self, signal_card, trade_date):
        started = time.time()
        if self.callback:
            self.callback.on_analysis_start(signal_card.ticker)

        result = self._do_analyze(signal_card, trade_date)

        elapsed = time.time() - started
        if self.callback:
            self.callback.on_analysis_end(
                ticker=signal_card.ticker,
                elapsed_seconds=elapsed,
                success=result.success,
            )
        return result
```

### 3.7 适配总结

| 改进项 | OpenHarness 原始设计 | 我们适配方向 |
|--------|-------------------|------------|
| Hook 类型 | `HookResult` + `AggregatedHookResult` | **零修改直接复用** |
| HookExecutor | 异步执行器（复杂） | **可能不需要** — 用 LangChain Callback 替代 |
| CostTracker | Token 累积器 | **零修改直接复用** |
| UsageSnapshot | Token 快照 | **零修改直接复用** |
| Callback 集成 | LangChain callback | 构建 `TokenCountingCallback` 提取 usage |
| Screener 可观测性 | 无 | 新增 callback 机制到 `DeepAnalyzer` |

---

## 四、P1/P2/P3 横向对比（修订版）

| 维度 | P1 Tool Registry | P2 Skills Loader | P3 可观测性 |
|------|----------------|-----------------|-------------|
| **适配必要性** | 🔴 强烈建议 | ❓ 待定（取决于场景 A/C） | 🟡 需要 |
| **工程价值** | 高（工具规范化） | 中（配置灵活化） | 高（生产可观测） |
| **实施难度** | 中（需改造 lazy import） | 低/中（取决于范围） | 低（大部分零修改） |
| **依赖顺序** | P1 最先 | 可能跳过 | P3 可最先（无依赖） |
| **破坏风险** | 低（保留原有函数签名） | 低（只扩展不修改） | 极低（纯附加功能） |
| **OpenHarness 复用度** | 核心借鉴（BaseTool + Registry） | 待定 | 高复用（types/cost_tracker 零修改） |

---

## 五、实施顺序建议（修订版）

```
Phase 1: P3 可观测性（最低风险，最高信息价值）
  └── 零修改复制 hooks/types.py + cost_tracker.py + api/usage.py
  └── 构建 TokenCountingCallback 集成到 TradingAgentsGraph
  └── 为 DeepAnalyzer 增加 callback 机制
  └── 立即获得：每次分析消耗多少 token

Phase 2: P1 Tool Registry（工程化基础设施）
  └── 创建 tradingagents/harness/tools/base.py
  └── 创建 tradingagents/harness/tools/registry.py
  └── 包装现有 20+ 工具接入 Registry
  └── 改造 agent_utils.py 的 get_tools_for_analyst() 为 Registry 驱动

Phase 3: P2 Skills Loader（如果确认有场景需求）
  └── 取决于你的回答（场景 A：金融知识库？场景 C：Context 文件注入？）
```

---

## 六、待确认的问题清单

在你决定之前，我需要你回答以下问题：

### P2 相关

**Q1**：金融知识技能库（场景 A）是否有实际需求？

- 为 Screener 的 DeepAnalyzer Agent 建立一个"如何识别财报舞弊"、"如何分析北向资金"等知识片段库
- DeepAnalyzer Agent 在分析时按需加载这些 Skill 作为额外上下文
- **具体问题**：DeepAnalyzer 的 system prompt 是 `analysts/*.py` 中硬编码的字符串，你是否希望在运行时动态拼接这些 Skill 内容？

**Q2**：Context 文件注入（场景 C）是否有实际需求？

- 在 `Prompt/context/` 目录下放置特定股票的分析上下文（如 `600519_maotai.md`）
- 分析时自动发现并注入对应 ticker 的 context 文件
- **具体问题**：你是否计划为特定股票（如茅台、宁德时代）维护专属分析上下文文件？

**Q3**：如果场景 A 和 C 都不需要，P2 可以完全跳过。你的意见？

### P3 相关

**Q4**：Hook 机制的范围确认：

- OpenHarness 的 `HookExecutor` 可能是过度设计（异步 + 事件总线）
- 我们可能只需要 LangChain `BaseCallbackHandler` + `CostTracker`
- **具体问题**：你是否认为 OpenHarness 的 `hooks/types.py` + `cost_tracker.py` 足够，不需要 `executor.py`？

**Q5**：Screener 可观测性的具体需求：

- DeepAnalyzer 目前没有 callback 机制
- 你是否希望每个 DeepAnalyzer 分析任务都产出：耗时、token 消耗、API 调用次数？
- **具体问题**：DeepAnalyzer 的分析结果报告（`DeepAnalysisResult`）中是否需要包含 token 消耗字段？

---

*本文档由 Harness 工程师角色生成，基于 OpenHarness 参考库和 TradingAgents 项目现状分析。*
