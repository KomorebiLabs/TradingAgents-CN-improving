# Screener 模块详解

> 本文档供 Codex（或其他开发者）快速理解 Screener 各模块的职责、作用和数据流向。
> 基于 `docs/SCREENER_DESIGN.md` 设计规格和实际代码实现编写。

---

## 1. Screener 在整个系统中的位置

Screener 是 TradingAgents 的 **Stage 1（主动选股引擎）**，位于 Deep Analyzer（Stage 2）之前。

```
全市场/降维股票池
    │
    ▼
┌─────────────────┐
│  Stage 1        │  ← Screener（本模块）
│  主动选股引擎   │
└─────────────────┘
    │
    │  Top 3-5 SignalCard[]
    ▼
┌─────────────────┐
│  Stage 2        │
│  Deep Analyzer  │  ← TradingAgentsGraph
│  深度研判平台   │     (TradingAgents 原核心)
└─────────────────┘
    │
    ▼
 最终决策报告
```

**Screener 的核心职责**：
不是替代 `TradingAgentsGraph`，而是为它提供一个**低成本、高约束、可审计的前置候选发现层**——从数千只股票中快速筛选出最值得 AI Agent 深度分析的 3-5 只。

---

## 2. 整体数据流

```
交易日 + 运行模式
    │
    ├─► Universe（构建股票池）
    │       └─► 指数成分股 或 用户自定义列表
    │
    ├─► Stage A（预筛）──► 快速过滤无效股票
    │       ├─ 无历史数据
    │       ├─ 历史行数不足
    │       └─ 低流动性 / 极端价格
    │
    ├─► Stage B（三策略评分）
    │       ├─ Strategy A（技术）：历史K线趋势
    │       ├─ Strategy B（政策）：概念板块热度
    │       └─ Strategy C（Smart Money）：资金质量
    │
    ├─► Merger（合并与过滤）
    │       ├─ 去重 + 共振加分
    │       ├─ 语义优先级
    │       ├─ 熔断过滤
    │       └─ 分散化
    │
    ├─► NameResolver（补充公司名）
    │
    ├─► Deep Analyzer（可选，Stage 2 桥接）
    │       └─► TradingAgentsGraph.propagate()
    │
    └─► 报告输出（JSON + Markdown）
```

---

## 3. 各模块详解

### 3.1 `config.py` — 全局配置中心

**一句话描述**：Screener 所有可配置项的单一真相来源。

**为什么存在**：避免在策略代码中出现魔法数字（硬编码阈值）。修改评分行为只需改配置，不需要改 Python 代码。

**核心内容**：

| 配置块 | 作用 |
|--------|------|
| `SCREENER_UNIVERSE` | 定义 6 种运行模式的股票池规模（上证指数代码列表、每阶段输入上限） |
| `SCREENER_CONFIG` | 运行时规则：策略权重、数据源优先级、防封禁参数、冲突解析参数、合并评分参数 |
| `SCREENER_THRESHOLDS` | 硬过滤阈值：ST、涨跌幅、换手率、市值、PE 边界 |
| `DeepAnalyzerConfig` | Deep Analyzer 并发配置 |
| `build_graph_config()` | 为 TradingAgentsGraph 构造兼容 config dict |

**配置优先级示例**：
```python
# 修改技术策略评分权重？改这里：
SCREENER_CONFIG["strategies"]["technical"]["weight"] = 0.50

# 修改 ST 过滤边界？改这里：
SCREENER_THRESHOLDS["low_turnover_rate"] = 1.5

# 修改防封禁请求间隔？改这里：
SCREENER_CONFIG["anti_ban"]["base_interval"] = 1.0
```

---

### 3.2 `models.py` — 数据契约（Pydantic 模型）

**一句话描述**：用 Pydantic V2 定义所有核心数据结构的"形状"，运行时强制校验。

**为什么存在**：确保 Screener 内部各模块之间、 Screener 与 Deep Analyzer 之间的数据接口不会漂移。字段缺失或类型错误会在运行前被立即捕获，而不是在生产环境崩溃。

**核心模型**：

| 模型 | 作用 | 关键字段 |
|------|------|---------|
| `DataFreshness` | 记录每个数据源的新鲜度状态 | `source`, `status`（fresh/stale/missing/estimated） |
| `SignalEvidence` | 单策略单股票的评分证据 | `strategy`, `score`, `degraded`, `degradation_reason` |
| `SignalCard` | 完整的股票信号卡（最终输出单元） | 所有策略证据 + 最终评分 + 风险标记 |
| `ScreeningResult` | 整轮筛选结果 | 候选列表、被剔除列表、策略状态、指标 |
| `DeepAnalysisResult` | Deep Analyzer 单只分析结果 | `final_decision`, `final_state_summary` |
| `ScreenerMetrics` | 运行指标 | 请求数、失败数、降级策略、阈值快照 |

**`SignalCard` 审计能力示例**：
```python
card = result.candidates[0]
print(card.screening_score)          # 最终综合评分
print(card.trigger_reason)          # 被选中的原因
print(card.risk_flags)             # 风险标记列表
print(card.signal_breakdown)        # 各策略的评分证据
for evidence in card.signal_breakdown:
    print(evidence.strategy)        # 哪个策略命中
    print(evidence.degraded)        # 是否降级运行
    print(evidence.degradation_reason)  # 降级原因
print(card.evidence_snapshot)        # 完整的中间计算快照
```

---

### 3.3 `runtime_guard.py` — 运行守卫

**一句话描述**：在 Screener 运行前检查"现在是否可以安全运行"。

**为什么存在**：确保在数据质量最好的时间窗口运行（收盘后 16:30 至次日 09:00）。盘中运行会导致数据不完整。

**`TimeValidator` 规则**：

| 场景 | 行为 |
|------|------|
| 当前是周末 | MVP/EXTENDED 默认拒绝运行（可用 `--allow-weekend` 覆盖） |
| 当前是盘中（09:30-15:00） | MVP/EXTENDED 拒绝运行；EXPERIMENTAL 可运行但标记数据可能不完整 |
| 当前是收盘后（15:00-16:30） | 拒绝运行（数据不稳定窗口） |
| trade_date 超过 2 天 | 发出警告但不阻止 |

---

### 3.4 `throttling.py` — 防封禁请求器

**一句话描述**：对所有 AkShare API 请求施加限速，防止 IP 被封禁。

**为什么存在**：AkShare 数据源来自东方财富、新浪等平台，频繁请求可能触发封禁。

**限速策略**：
- 基础间隔：每请求间隔 0.5 秒
- Burst 暂停：连续超过 10 次请求后强制暂停 2 秒
- 失败惩罚：请求失败后额外等待 1.5 秒
- 软 RPM 限制：30 次/分钟，超过后记录警告但不阻塞

**使用方式**：
```python
from tradingagents.screener.throttling import ThrottledRequester

requester = ThrottledRequester()
result = requester.request(some_akshare_function, ...)
stats = requester.get_stats()  # 查看请求统计
```

---

### 3.5 `universe.py` — 股票池构建

**一句话描述**：根据运行模式，构建要筛选的股票代码列表。

**为什么存在**：Screener 不能处理全市场 5000 只股票（成本太高），需要按模式降维。

**6 种运行模式**：

| 模式 | 含义 | 股票池规模 |
|------|------|-----------|
| MVP | 沪深300 + 中证500 | ~800 只 |
| EXTENDED | + 创业板 + 科创50 | ~1500 只 |
| EXPERIMENTAL | + 中证1000 | ~2500 只 |
| FULL | 近全市场 | ~4000 只 |
| FOCUSED | 指定板块/主题/指数 | 动态 |
| CUSTOM | 用户自定义列表 | 用户指定 |

**关键设计**：真实股票代码通过 AkShare 的 `index_stock_cons_weight_csindex` 接口获取（不是直接用指数代码 000300 等）。

---

### 3.6 `data_access.py` — 多源数据访问层

**一句话描述**：封装多个数据源（Sina、Tencent、THS、Baidu、Baostock、yfinance），提供统一 API 并自动选择可用源。

**为什么存在**：
1. 不同数据源的接口格式不同（列名字段名各异）
2. 单个数据源可能随时不可用，需要备源自动切换
3. 需要统一限速和请求伪装

**数据源优先级**：

| 数据类型 | 主源 | 备源1 | 备源2 | 最终兜底 |
|---------|------|--------|--------|---------|
| 历史K线 | Tencent | Sina | Baostock | yfinance |
| 实时行情 | Tencent | Sina | — | — |
| 概念板块 | THS | Sina | — | — |
| 资金流向 | THS | AkShare EM | — | — |
| 指数数据 | Sina | Tencent | — | — |
| 分笔成交 | Tencent | Sina | — | — |
| 估值/人气 | Baidu | — | — | — |

**A0 Probe 系统**：每次运行前探测各接口可用性，生成 `capability_summary`，告诉各策略"哪些数据源可用、哪些降级了"。

---

### 3.7 `strategies/technical.py` — Strategy A：技术与资金共振

**一句话描述**：基于历史K线趋势 + 资金流向，给每只股票打技术分。

**核心逻辑**：

```
获取成分股
    → 批量获取全市场资金流
    → 对 Top 100 候选抓 100 天历史数据
    → 计算 9 个技术子分
    → 加权求和 + 资金流奖励/惩罚
    → 输出策略内 Top 20 SignalCard
```

**9 个技术子分**：

| 子分 | 权重 | 含义 |
|------|------|------|
| trend_alignment | 0.22 | 价格与均线系统对齐程度（close > MA20 > MA60 → 高分） |
| momentum | 0.18 | 20日和60日动量（收益率换算） |
| drawdown_resilience | 0.14 | 回撤控制能力（最大回撤越小 → 高分） |
| volatility | 0.10 | 波动率健康度（年化波动率越低 → 高分） |
| trend_consistency | 0.12 | 趋势一致性（正收益天数比例） |
| structure_risk | 0.11 | 结构风险（延伸幅度、均线支撑/跌破次数） |
| volume_confirmation | 0.07 | 量价配合（量增价涨 → 高分） |
| breakout_quality | 0.04 | 突破质量（突破幅度 + 量能配合） |
| divergence | 0.02 | 量价背离检测（有背离 → 减分） |

**降级设计**：若资金流或历史K线不可用，分数自动扣减，但策略仍可运行。

---

### 3.8 `strategies/policy.py` — Strategy B：政策与事件驱动

**一句话描述**：通过概念板块热度 + 政策新闻事件，找到当前最热概念中的强势股票。

**核心逻辑**：

```
获取概念板块列表（THS）
    → 拉取政策/财经新闻（百度）
    → LLM 抽取当前热点概念
    → 关键词 Fallback（内置 POLICY_KEYWORDS）
    → 概念合法性校验（只允许有效概念）
    → 概念 → 成分股映射
    → 成分股按涨跌幅/成交额/换手率打分
    → 输出策略内候选
```

**评分维度**：
- 概念热度：新闻中概念出现频次
- 成分股强度：涨跌幅 + 成交额 + 换手率
- 板块领导地位：成分股内相对排名（前3/前10/尾部）
- 新闻源权重：官方政策 > 主流财经 > 二手转载

**降级设计**：概念列表不可用时，策略降级运行（仍输出结果，但标记 `degraded=True`）。

---

### 3.9 `strategies/smart_money.py` — Strategy C：Smart Money

**一句话描述**：寻找"资金质量高"的标的——机构参与度高、连续性强、资金与价格质量匹配。

**核心逻辑**：

```
获取历史K线（Tencent 主源）
    → 获取分笔成交（腾讯）
    → 获取龙虎榜/机构席位（Sina）
    → 获取人气投票（百度）
    → 获取估值数据（百度）
    → 计算 10 个资金质量子分
    → 标注 capital_quality_tag
    → 输出策略内候选
```

**10 个资金质量子分**：

| 维度 | 权重 | 含义 |
|------|------|------|
| momentum | 0.24 | 历史动量（来自历史K线） |
| tick | 0.11 | 分笔大单净买入方向（大单买入 > 大单卖出 → 高分） |
| tick_persistence | 0.10 | 分笔大单连续性（连续净买入天数） |
| popularity | 0.12 | 百度人气投票（人气越高 → 高分） |
| institutional | 0.11 | 龙虎榜机构席位信号 |
| continuity | 0.10 | 龙虎榜连续上榜强度 |
| multi_day | 0.10 | 多日持续性 |
| valuation | 0.10 | 估值合理区间（PE/PB） |
| risk_constraint | 0.07 | 风险约束（波动率/回撤控制） |
| joint_quality | 0.10 | 综合资金质量 |

**`capital_quality_tag`**（每个 SignalCard 被打上的资金质量标签）：

| 标签 | 含义 | Merger 影响 |
|------|------|-----------|
| `capital_quality_high` | 高质量持续资金流入 | 天然优先 |
| `capital_quality_persistent` | 多日持续资金 | 优先 |
| `capital_quality_mixed` | 混合质量 | 正常处理 |
| `capital_quality_speculative` | 高热度低质量投机资金 | 额外扣分，可能被过滤 |

**MVP 设计意图**：只要 Tencent 历史K线可用，Smart Money 就能运行。龙虎榜/机构席位/人气投票是增强项，不是硬性要求。

---

### 3.10 `merger.py` — 合并器（Screener 的大脑）

**一句话描述**：将三策略输出融合为最终 Top 候选——不只是加权平均，而是基于语义标签的决策引擎。

**为什么存在**：多策略的评分可能相互冲突（如强概念股 + 高技术风险），需要一套决策规则来决定"谁最终胜出"。

**融合流程**：

```
所有 SignalCard（三策略 × N只股票）
    │
    ├─► 按 ticker 去重
    │       └─ 合并多策略 evidence
    │
    ├─► 语义优先级计算
    │       ├─ policy_strength（0-3）：龙头/核心/交叉/关键词
    │       ├─ capital_tag（+4/-4）：高质量/投机
    │       ├─ 技术结构惩罚：structure_risk 低分时扣分
    │       └─ 跨策略冲突检测（aligned/moderate/high/severe）
    │
    ├─► 冲突解析（8条规则）
    │       ├─ 强概念 + 高技术风险 → 技术否决
    │       ├─ 强概念 + 高质量资金 → 概念优先
    │       ├─ 弱概念 + 高技术风险 → 降低权重
    │       └─ ...
    │
    ├─► 熔断过滤
    │       ├─ ST/*ST → 直接剔除
    │       ├─ 跌停/近跌停 → 直接剔除
    │       ├─ 低流动性（换手率 < 2%）→ 直接剔除
    │       ├─ PE < 0 或 PE > 150 → 直接剔除
    │       └─ speculative 资金 + 低分 → 直接剔除
    │
    ├─► 分散化
    │       └─ 同板块最多 2 只
    │
    └─► 输出 Top N
```

**语义优先级示例**：

```
贵州茅台（600519）：
  - policy_strength = 3（概念板块龙头）
  - capital_tag = capital_quality_high（高质量资金）
  - 技术结构风险 = 低
  → 语义优先级：非常高 → 几乎必然保留

某题材股：
  - policy_strength = 0（关键词 fallback）
  - capital_tag = capital_quality_speculative（高热度投机资金）
  - 技术结构风险 = 高
  → 语义优先级：非常低 → 需要高分才能保留
```

---

### 3.11 `deep_analyzer.py` — Deep Analyzer（Stage 2 桥接）

**一句话描述**：将 Screener 输出的 Top 候选逐只送入 `TradingAgentsGraph`，获得 AI Agent 的完整研判结论。

**为什么存在**：Screener 负责"选"，Deep Analyzer 负责"深度分析"。两者通过 `config` 字典传递上下文，不修改原有 `TradingAgentsGraph` 的接口。

**工作流程**：

```
SignalCard[]
    │
    ├─► 为每只候选构造 graph_config
    │       ├─ company_of_interest = ticker
    │       └─ screener_context = {
    │               trigger_reason,       # 为什么被选中
    │               strategy_sources,     # 哪几个策略命中
    │               screening_score,      # 初筛分数
    │               risk_flags,          # 风险标记
    │               sector_tags,         # 行业标签
    │               concept_tags,        # 概念标签
    │               semantic_prompt_slots, # 结构化语义载荷
    │               route_decision,      # 路由决策
    │           }
    │
    ├─► 顺序调用（每只间隔 2 秒）
    │       └─ TradingAgentsGraph(debug=False, config=graph_config)
    │               .propagate(ticker, trade_date)
    │
    └─► 解析 final_state
            ├─ final_decision（最终买卖决策）
            ├─ route_decision（使用了哪些分析 Agent）
            └─ semantic_trigger_audit（路由触发原因）
```

**兼容性约束**：
- ❌ 不修改 `TradingAgentsGraph.propagate()` 的函数签名
- ❌ 不把 `SignalCard` 直接传入 graph
- ✅ 只通过 `config` 字典注入必要上下文

---

### 3.12 `report.py` — 报告生成器

**一句话描述**：将 `ScreeningResult` 输出为可读的 JSON 和 Markdown 报告。

**输出文件**：

| 文件 | 位置 | 内容 |
|------|------|------|
| `screening_result.json` | `~/.tradingagents/logs/screener/<run_id>/` | 完整结构化数据（含所有 evidence_snapshot，可程序化解析） |
| `daily_gold_stocks_report.md` | 同上 | 人类可读 Markdown 摘要 |

**Markdown 报告包含**：

```
# Screener Report
- Funnel Summary（Stage A/B 通过率）
- Data Issues（数据问题清单）
- Strategy Status（A/B/C 是否 degraded）
- Capability Summary（各数据源探测结果）
- Candidates
  - 每只候选的评分、置信度、风险标记
  - 策略来源、触发原因
  - 语义决策摘要
- Dropped Candidates（含剔除原因）
- Deep Analysis（含路由决策和分析结论）
```

---

### 3.13 `engine.py` — Screener 引擎（主编排器）

**一句话描述**：串联所有模块，协调数据流，是 Screener 的主入口。

**执行顺序**：

```
ScreenerEngine.run()
    │
    ├─► Runtime Guard 验证（时间/日期是否允许运行）
    │
    ├─► Universe 构建（获取股票列表）
    │
    ├─► Stage A 预筛
    │       └─ 快速过滤无效股票（数据缺失/低流动性/极端价格）
    │
    ├─► Stage B 三策略评分
    │       ├─ Strategy A（技术）
    │       ├─ Strategy B（政策）
    │       └─ Strategy C（Smart Money）
    │
    ├─► Merger 合并与过滤
    │
    ├─► Name Resolver（补充公司中文名）
    │
    ├─► Deep Analyzer（可选，调用 TradingAgentsGraph）
    │
    ├─► 数据一致性检查
    │
    └─► 报告输出
```

**`ScreenerEngine` 使用示例**：

```python
from tradingagents.screener import ScreenerEngine

engine = ScreenerEngine(config={...})
result = engine.run(
    mode="MVP",
    trade_date="2026-05-18",
    enable_deep_analysis=True,
    persist_outputs=True,
)
print(result.candidates)      # Top 候选 SignalCard[]
print(result.metrics)        # 运行指标
```

---

### 3.14 `name_resolver.py` — 公司名解析

**一句话描述**：将股票代码转换为公司中文名（解决新浪 API 中文乱码问题）。

**为什么存在**：Sina API 返回中文时可能有编码问题，导致公司名显示为乱码。

**策略**：
- 主源：`akshare.stock_info_a_code_name()`（全市场 A 股名称，一次获取，UTF-8）
- 备源：中证指数成分股权重数据中的名称
- 缓存：每日缓存到 `~/.tradingagents/cache/screener/names_YYYYMMDD.json`

**使用方式**：
```python
from tradingagents.screener.name_resolver import NameResolver

resolver = NameResolver(data_access=data_access, trade_date="2026-05-18")
resolver.load()
name = resolver.resolve("600519")  # "贵州茅台"
```

---

### 3.15 `cli/` — 命令行界面

**一句话描述**：为 Screener 提供交互式/命令行两种使用方式。

| 文件 | 职责 |
|------|------|
| `app.py` | Typer CLI 根入口（无参数启动交互式向导） |
| `commands/run_impl.py` | `screener run` 子命令实现（参数解析、配置构造、结果序列化） |
| `formatters/terminal.py` | Rich 终端表格/面板格式化（颜色、emoji、进度条） |
| `interactive.py` | 交互式向导（Komo mascot + 步骤引导） |

**运行示例**：

```bash
# MVP 模式（默认）
python -m tradingagents.screener.cli run --date 2026-05-08

# 全市场模式
python -m tradingagents.screener.cli run --mode FULL

# 聚焦板块
python -m tradingagents.screener.cli run --mode FOCUSED --focus-type sector --focus-value semiconductor

# 自定义列表（快速测试）
python -m tradingagents.screener.cli run --tickers 600519,000001 --no-deep

# 仅输出 JSON
python -m tradingagents.screener.cli run --output json

# 交互式向导
python -m tradingagents.screener.cli
```

---

## 4. 关键设计决策速查

### 4.1 为什么 Screener 不处理全市场 5000 只股票？

成本太高。AkShare 免费接口在顺序请求下：
- 100 天历史数据 × 800 只股票 ≈ 数十分钟
- 超过 1000 只后请求成本显著增加
- Stage A 预筛负责提前剔除无效股票

### 4.2 为什么三策略的评分公式与设计文档不一致？

设计文档是"起点规格"，实际实现是"工程演进"的产物。评分公式在实践中被细化为更多子维度，核心业务逻辑（技术/概念/资金三维度共振）保持不变。**建议**：更新设计文档与实现对齐。

### 4.3 Merger 中的"语义优先级"是什么？

不是简单的加权平均分数，而是一套决策规则：

```
policy_strength（政策强度，0-3）
  3 = 概念板块龙头（policy_top_stock）
  2 = 概念板块核心成员（policy_core_member）
  1 = 跨概念命中（policy_cross_hit_candidate）
  0 = 关键词兜底（policy_keyword_fallback）

+ capital_tag（资金质量）
  high = +4，persistent = +2，speculative = -4

- 技术结构惩罚（structure_risk 低分时）

= 语义优先级（决定最终排序）
```

### 4.4 为什么需要 Deep Analyzer（Stage 2）？

Screener 只能给出"哪只股票值得看"，不能给出"为什么买/卖"。

Deep Analyzer 通过 `TradingAgentsGraph` 的多 Agent 辩论（基本面分析师 + 情绪分析师 + 新闻分析师 + 技术分析师 + 研究员团队），输出：
- 最终买卖决策（BUY/HOLD/SELL）
- 决策理由（上行/下行风险）
- 置信度

### 4.5 数据源全部失败时会发生什么？

| 模块 | 失败场景 | 行为 |
|------|---------|------|
| Universe | 所有成分股接口失败 | **Bug B-3 已修复**：显式抛出 RuntimeError，不再静默降级 |
| Strategy A | 历史K线不可用 | 降级运行，分数扣减，不阻断 |
| Strategy B | 概念列表不可用 | 降级运行，关键词兜底，不阻断 |
| Strategy C | 龙虎榜不可用 | 降级运行，主要依赖历史K线，不阻断 |
| Deep Analyzer | TradingAgentsGraph 调用失败 | dry_run 输出，不伪造结论 |

---

## 5. 文件索引

```
tradingagents/screener/
├── __init__.py              # 包入口，屏蔽第三方库警告
├── config.py                 # 全局配置中心
├── models.py                 # Pydantic 数据契约
├── engine.py                 # 主编排器
├── merger.py                  # 合并器（决策引擎）
├── report.py                  # 报告生成器
├── runtime_guard.py           # 运行守卫
├── throttling.py             # 防封禁请求器
├── universe.py               # 股票池构建
├── data_access.py            # 多源数据访问层
├── name_resolver.py           # 公司名解析
├── http_spoof.py             # 请求头伪装（防反爬）
├── strategies/
│   ├── __init__.py        # 导出 TechnicalStrategy, PolicyStrategy, SmartMoneyStrategy, StrategyOutcome
│   ├── technical.py          # Strategy A：技术分析
│   ├── policy.py             # Strategy B：政策驱动
│   └── smart_money.py        # Strategy C：Smart Money
├── cli/
│   ├── __main__.py
│   ├── app.py                # CLI 根入口
│   ├── interactive.py        # 交互式向导
│   ├── commands/
│   │   ├── __init__.py
│   │   └── run_impl.py       # run 子命令实现
│   └── formatters/
│       ├── __init__.py
│       └── terminal.py        # 终端格式化
└── deep_analyzer.py           # Deep Analyzer 桥接器
```

---

## 6. 配置项速查表

**需要调整评分行为时**，请修改 `config.py` 中的对应字段：

| 你想要的改动 | 修改配置项 |
|-------------|-----------|
| 改变 MVP 模式的股票池 | `SCREENER_UNIVERSE["MVP"]["index_codes"]` |
| 调整技术策略权重 | `SCREENER_CONFIG["strategies"]["technical"]["weight"]` |
| 放宽/收紧 ST 过滤 | `SCREENER_THRESHOLDS["low_turnover_rate"]` |
| 调整防封禁请求间隔 | `SCREENER_CONFIG["anti_ban"]["base_interval"]` |
| 改变资金质量评分权重 | `SCREENER_CONFIG["strategies"]["smart_money"]["weight"]` |
| 调整 Deep Analyzer 并发数 | `SCREENER_CONFIG["deep_analyzer"]["max_stocks"]` |
| 改变冲突解析规则 | `SCREENER_CONFIG["conflict_priority"]["technical_veto_bias"]` |
| 调整分散化限制（同板块最多几只） | `SCREENER_CONFIG["candidates"]["same_sector_limit"]` |
| 调整历史数据缓存TTL | `SCREENER_CONFIG["cache"]["cache_ttl_minutes"]` |