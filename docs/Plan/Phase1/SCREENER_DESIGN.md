# Stage 1: The Screener — 主动选股引擎实现规格文档 (V6.0)

> **文档版本**: V6.0
> **创建日期**: 2026-05-07
> **文档性质**: 可直接开工的实现规格文档
> **适用范围**: `D:\cursor\HarmonyOS\Github project\TradingAgents-main`

---

## 0. 文档定位

本文档不是概念草案，而是用于指导直接编码实现的工程规格。

相较于 V5.0，本版本重点解决 7 类问题：

1. 与现有代码接口不兼容
2. 文档内部自相矛盾
3. 数据源假设不够稳
4. 筛选逻辑不可审计
5. 与现有 Harness 能力耦合不深
6. 异常与降级策略不完整
7. 测试与验收标准不足

同时保留辩证约束：

- 本文档优先追求 `稳定可实现`，不是一次性追求“最聪明”的 Screener。
- 所有依赖免费数据源的设计都必须允许降级。
- 对我方当前判断不充分确定的地方，必须显式写成 `假设` 或 `待验证项`，而不是伪装成事实。

---

## 1. 背景与目标

### 1.1 背景

当前项目已经完成以下基础能力：

- `L2 Tool System`：A 股工具底盘、AkShare 主干、CN 专项工具、vendor fallback
- `L3 Execution Orchestration`：状态驱动轨道、handoff、compression、route insight
- `L4 State & Memory`：structured state、structured memory、reflection 闭环

当前缺少的是 Stage 1 的主动选股入口，即：

```text
全市场/降维股票池
    -> 初筛
    -> 候选信号卡
    -> Deep Analyzer
    -> 最终三大金股深度报告
```

### 1.2 目标

Screener 的目标不是替代 `TradingAgentsGraph`，而是为它提供一个低成本、高约束、可审计的前置候选发现层。

### 1.3 非目标

以下内容不属于 V6.0 第一阶段交付：

- 不做全市场 5000 只股票逐票深度分析
- 不做盘中高频更新
- 不做复杂回测引擎
- 不做完整 RAG 新闻检索重排闭环
- 不把质押、财报、龙虎榜等所有信息都升级为逐票硬过滤项

---

## 2. 总体结论与实施原则

### 2.1 总体结论

Screener 应采用两阶段架构：

1. `Stage 1 Screener`
   - 输入：交易日、股票池
   - 输出：`SignalCard[]`
2. `Stage 2 Deep Analyzer`
   - 输入：`SignalCard[]`
   - 输出：对 Top 3 候选的完整多 Agent 深度论证结果

### 2.2 实施原则

1. `稳定性优先`
   - 免费源可慢，不可脆。
2. `结构化优先`
   - 所有阶段产物必须可存储、可校验、可测试。
3. `顺序优先`
   - MVP 不引入并发抓取，不引入并发深度分析。
4. `显式降级`
   - 任何策略失效都必须写入状态、指标和报告。
5. `与现有 Harness 对齐`
   - 不重复发明 memory/orchestration 体系。

---

## 3. 当前仓库的兼容性约束

本节用于解决“设计看似合理，但一实现就与现有代码冲突”的问题。

### 3.1 现有图入口约束

当前 [tradingagents/graph/trading_graph.py](D:/cursor/HarmonyOS/Github%20project/TradingAgents-main/tradingagents/graph/trading_graph.py:1) 的核心入口为：

```python
TradingAgentsGraph(config: Dict[str, Any])
ta.propagate(company_name, trade_date)
```

因此 Screener 侧必须遵守：

- `TradingAgentsGraph` 接收的是 `dict config`，不是 dataclass 对象
- `propagate()` 当前没有 `timeout` 参数
- Screener 不能假设 graph 会自动读取 `SignalCard`

### 3.2 兼容性决策

Screener 的 Deep Analyzer 编排器必须改为：

1. 自己维护 Screener 并发/冷却配置
2. 构造一个 `graph_config: dict`
3. 调用 `TradingAgentsGraph(debug=False, config=graph_config)`
4. 使用 `ta.propagate(ticker, trade_date)`

### 3.3 Ticker 规范

统一规范如下：

- Screener 内部主键字段：`ticker`
- A 股标准输出：`600519.SH` / `000001.SZ` / `430xxx.BJ`
- 兼容字段：`raw_code`

理由：

- 当前项目 `build_instrument_profile()` 已支持带交易所后缀的 ticker
- exchange-qualified ticker 更利于后续工具路由和审计

辩证说明：

- 当前本地 `main.py` 仍存在直接传 `000001` 的用法
- 因此实现时必须保留兼容解析，不能强制旧路径全部改掉

---

## 4. 模块边界与目录设计

本节用于解决“实现放哪里、哪些模块负责什么”的问题。

### 4.1 新增目录

建议新增：

```text
tradingagents/
  screener/
    __init__.py
    config.py
    models.py
    engine.py
    merger.py
    report.py
    runtime_guard.py
    throttling.py
    universe.py
    deep_analyzer.py
    data_access.py
    strategies/
      __init__.py
      technical.py
      policy.py
      smart_money.py
```

### 4.2 职责划分

`config.py`
- Screener 全局配置与默认值

`models.py`
- `SignalCard`
- `ScreeningResult`
- `DeepAnalysisResult`
- `ScreenerMetrics`
- `DataFreshness`

`runtime_guard.py`
- 运行时间验证
- 数据日期一致性检查

`throttling.py`
- 防封禁请求器
- 请求统计与限速控制

`universe.py`
- 股票池构建
- 成分股获取与缓存

`data_access.py`
- Screener 所需 AkShare/本地数据访问适配
- 不直接复用 graph agent tool 的 LangChain Tool 形式

`strategies/*.py`
- 三个策略的纯筛选逻辑

`merger.py`
- 去重、融合、打分、分散化、熔断过滤

`deep_analyzer.py`
- `SignalCard -> TradingAgentsGraph` 的桥接

`report.py`
- 文本报告与 JSON 报告输出

### 4.3 不应做的事

以下设计禁止：

- 不要把 Screener 逻辑塞进 `tradingagents/graph/`
- 不要把 Screener 的抓数逻辑直接写进 agent tools
- 不要让 `TradingAgentsGraph` 反向感知 Screener 具体实现细节

---

## 5. 数据契约

本节用于解决“字段不清、模块衔接不稳”的问题。

### 5.1 核心数据模型

#### 5.1.1 DataFreshness

```python
class DataFreshness(BaseModel):
    source: str
    trade_date: str | None
    fetched_at: str
    status: Literal["fresh", "stale", "missing", "estimated"]
    notes: str = ""
```

#### 5.1.2 SignalEvidence

```python
class SignalEvidence(BaseModel):
    strategy: Literal["technical", "policy", "smart_money"]
    score: float
    rank_in_strategy: int | None = None
    reason: str
    raw_metrics: dict[str, Any] = Field(default_factory=dict)
    freshness: list[DataFreshness] = Field(default_factory=list)
    degraded: bool = False
    degradation_reason: str = ""
```

#### 5.1.3 SignalCard

```python
class SignalCard(BaseModel):
    ticker: str
    raw_code: str
    exchange: str
    company_name: str
    trade_date: str
    sector_tags: list[str] = Field(default_factory=list)
    concept_tags: list[str] = Field(default_factory=list)
    strategy_sources: list[str] = Field(default_factory=list)
    signal_breakdown: list[SignalEvidence] = Field(default_factory=list)
    trigger_reason: str
    initial_confidence: float
    risk_flags: list[str] = Field(default_factory=list)
    screening_score: float
    screening_rank: int | None = None
    data_source_verified: bool = False
    evidence_snapshot: dict[str, Any] = Field(default_factory=dict)
```

#### 5.1.4 ScreeningResult

```python
class ScreeningResult(BaseModel):
    run_id: str
    mode: Literal["MVP", "EXTENDED", "EXPERIMENTAL"]
    trade_date: str
    started_at: str
    completed_at: str
    universe_size: int
    candidates: list[SignalCard]
    dropped_candidates: list[dict[str, Any]] = Field(default_factory=list)
    strategy_status: dict[str, str]
    data_issues: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
```

#### 5.1.5 DeepAnalysisResult

```python
class DeepAnalysisResult(BaseModel):
    signal_card: SignalCard
    success: bool
    final_decision: str | None = None
    elapsed_seconds: float
    error: str = ""
    final_state_summary: dict[str, Any] = Field(default_factory=dict)
```

### 5.2 Deep Analyzer 输入契约

`DeepAnalyzer` 只消费 `SignalCard`，不直接消费策略内部中间状态。

### 5.3 Graph 状态注入契约

为避免 Screener 与 graph 完全断裂，Deep Analyzer 在 graph 启动前必须把以下信息注入 `config`：

```python
config["company_of_interest"] = signal_card.ticker
config["screener_context"] = {
    "trigger_reason": signal_card.trigger_reason,
    "strategy_sources": signal_card.strategy_sources,
    "screening_score": signal_card.screening_score,
    "initial_confidence": signal_card.initial_confidence,
    "risk_flags": signal_card.risk_flags,
    "sector_tags": signal_card.sector_tags,
    "concept_tags": signal_card.concept_tags,
}
```

辩证说明：

- 当前 graph 不一定会直接消费 `screener_context`
- 但该字段必须先写入 config，为后续 prompt 增强和 route memory 扩展留接口

---

## 6. 运行模式与时间约束

本节修正文档原有“时间只写原则、不写行为”的问题。

### 6.1 三种运行模式

`MVP`
- 默认模式
- 仅输出 Top 3
- 顺序抓数
- 顺序 deep analysis

`EXTENDED`
- 输出 Top 5
- 仍不启用抓数并发
- 需要显式开关

`EXPERIMENTAL`
- 允许放宽时间限制或股票池限制
- 不作为生产结果使用

### 6.2 生产运行时间规则

生产默认推荐时间：

- 当日 `16:30` 之后
- 或下一交易日 `09:00` 之前

行为规则：

1. 若处于 `09:30-15:00` 盘中
   - `MVP/EXTENDED` 默认拒绝执行
   - `EXPERIMENTAL` 允许执行，但标记 `data_source_verified=False`
2. 若在 `15:00-16:30`
   - 默认拒绝执行
3. 若周末/非交易日
   - 默认拒绝执行
   - 可通过 `allow_non_trading_day_override=True` 强制运行

辩证说明：

- V5.0 中“16:30 后强制要求运行”过于绝对
- V6.0 改成：生产默认硬约束，实验模式允许人工覆盖

### 6.3 数据新鲜度要求

所有策略必须回填 `DataFreshness`：

- `fresh`: 数据与目标交易日一致
- `stale`: 数据滞后但可参考
- `missing`: 完全缺失
- `estimated`: 通过降级逻辑推断

---

## 7. 股票池定义

本节用于解决“为什么是这些股票、如何可配置”的问题。

### 7.1 MVP 默认股票池

默认股票池定义为以下成分股并集去重：

- 沪深 300：`000300`
- 中证 500：`000905`

### 7.2 原因

原因不是“它们最完美”，而是：

- 免费数据场景下能显著降维
- 足够覆盖主流机构关注标的
- 流动性更稳定
- 降低小盘题材极端噪声

### 7.3 已知代价

此定义会漏掉：

- 中证 1000 小票热点
- 纯题材短线股
- 部分科创/创业板极端风格标的

因此必须把该约束显式写入报告元信息。

### 7.4 可配置扩展

保留扩展开关：

```python
SCREENER_UNIVERSE = {
    "mvp": ["000300", "000905"],
    "growth_extended": ["000300", "000905", "399006", "000688"],
}
```

其中：

- `399006` 代表创业板指扩展池
- `000688` 代表科创 50 扩展池

---

## 8. 防封禁与请求治理

### 8.1 原则

- 不做多线程抓取
- 批量接口优先
- 单票接口必须走统一限速器

### 8.2 实现要求

`ThrottledRequester` 必须修正以下问题：

- 初始化时必须设置 `_start_time`
- 统计逻辑不能依赖未初始化字段
- 失败重试与延时必须配置化

### 8.3 请求治理规格

统一约束：

- 基础间隔：`0.5s`
- 连续请求阈值：`10`
- burst pause：`2.0s`
- 单轮失败后惩罚间隔：`1.5s`

### 8.4 缓存要求

以下数据必须允许当日内缓存：

- 成分股列表
- 有效概念列表
- 策略 B 新闻原文摘要
- 策略 A Top100 历史数据

缓存目标不是“性能极限”，而是“避免重复请求触发封禁”。

---

## 9. 数据访问与待验证项

### 9.0 当前正式数据源基线

自 `2026-05-07` 起，Screener 的正式运行基线固定为：

- `Tencent Finance` 是历史K线主源
- `THS` 是概念/行业/资金流主源
- `Sina` 是实时行情、指数、龙虎榜主源
- `Baidu` 是新闻、估值、人气等辅助源
- `Baostock` 是低频历史/兜底备源
- `EastMoney/AkShare-EM` 不再作为默认主源，只保留兼容层角色

这不是对 EastMoney 的永久否定，而是基于当前项目环境、封禁风险和可维护性做出的工程基线。

### 9.0.1 各策略的正式依赖分工

`Strategy A / technical`
- 必需：`THS fund flow` + `Tencent hist`
- 次级：`Sina hist`
- 末级兜底：`Baostock hist` / `yfinance`

`Strategy B / policy`
- 必需：`THS concept boards`
- 兼容：`Sina concept classify`
- 辅助：`Baidu news`

`Strategy C / smart_money`
- MVP 必需：`Tencent hist`
- 增强项：`THS fund flow`、`Tencent tick`、`Sina 龙虎榜`、`Baidu valuation/sentiment`
- 结论：Smart Money 在 MVP 阶段不能再被设计为“必须等机构席位/北向/业绩三件套齐备才可运行”，否则会长期停留在设计态

本节用于解决“设计依赖的免费接口是否真实可用”的问题。

### 9.1 预实现前必须验证的 4 项

实现前先做 `A0 验证任务`，确认以下接口行为：

1. `stock_individual_fund_flow()` 是否存在全量模式
2. `stock_board_concept_spot_em()` 在收盘后是否稳定提供完整概念名
3. 龙虎榜、北向、业绩预告在目标时间窗内是否稳定
4. 历史日线 `stock_zh_a_hist_em()` 在 100 票顺序请求场景下的真实耗时

### 9.2 若验证失败的决策

若 `stock_individual_fund_flow()` 不支持稳定全量模式：

- Strategy A 改为：
  - 使用 `stock_zh_a_spot_em()` 做截面与流动性预筛
  - 再仅对 Top 50 候选逐票抓资金流
- 文档估算耗时与评分逻辑一并下调

这不是设计失败，而是对免费源现实约束的正常适配。

---

## 10. 三策略实现规格

本节用于解决“策略只有概念，没有可执行规则”的问题。

### 10.1 Strategy A：技术与资金共振

#### 10.1.1 目标

从降维股票池中寻找：

- 资金净流入强
- 价格趋势未坏
- 技术状态偏多
- 流动性足够

#### 10.1.2 数据流

1. 获取成分股列表
2. 批量获取全市场/可用范围实时行情
3. 批量或准批量获取资金流
4. 基于截面指标生成 coarse rank
5. 仅对 Top 100 候选抓 100 天历史数据
6. 计算技术确认分数
7. 输出策略内 Top N

#### 10.1.3 历史窗口

统一要求：

- `lookback_days = 100`

删除 V5.0 中遗留的“20天简化 MACD”描述，不允许实现成近似版。

#### 10.1.4 评分公式

Strategy A 最终分数范围 `0-100`：

```text
A_score =
  0.35 * fund_flow_rank_score
  + 0.30 * momentum_score
  + 0.20 * macd_confirmation_score
  + 0.15 * liquidity_score
```

各子分数定义：

`fund_flow_rank_score`
- 在候选池内按主力净流入、净流入占成交额比例做截面分位映射到 0-100

`momentum_score`
- 满足 `close > MA20 > MA60` 得高分
- 仅 `close > MA20` 得中分
- 否则低分

`macd_confirmation_score`
- `DIF > DEA` 且柱体连续改善：高分
- `DIF > DEA` 但柱体走平：中分
- 否则低分

`liquidity_score`
- 由成交额、换手率、流通市值映射

#### 10.1.5 输出约束

仅输出策略内 Top 20 到 merger，不直接输出最终 Top 3。

### 10.2 Strategy B：政策与事件驱动

#### 10.2.1 目标

从新闻与政策事件中找到当前最热概念，并映射到强势标的。

#### 10.2.2 数据流

1. 获取新闻摘要集合
2. 获取当日有效概念列表
3. LLM 概念抽取
4. 概念合法性校验
5. 概念成分股映射
6. 概念股强度评分
7. 输出策略内 Top N

#### 10.2.2A 数据能力边界

Strategy B 当前必须继续依赖：

- `THS`：概念板块列表
- `Sina`：概念列表兼容回退
- `Baidu`：政策/财经新闻辅助输入

Strategy B 当前不应绑定：

- `Tencent hist`
- `EastMoney concept boards`

原因：

- Policy 的可运行性关键在“概念合法列表是否稳定”，不在历史K线
- 将 Tencent 历史链路强耦合进 Policy，只会把无关失败传播成错误降级

#### 10.2.3 概念约束

LLM 只能从有效概念列表中选择，返回 JSON 数组。

#### 10.2.4 评分公式

```text
B_score =
  0.40 * concept_heat_score
  + 0.35 * stock_strength_score
  + 0.15 * source_quality_score
  + 0.10 * liquidity_score
```

`concept_heat_score`
- 概念在新闻中出现频次
- 不同源的重复验证次数

`stock_strength_score`
- 概念成分股中相对涨幅、成交额、换手率

`source_quality_score`
- 新闻源权重
- 官方政策 > 主流财经媒体 > 二手转载

#### 10.2.5 降级策略

若 LLM 抽取失败：

- 进入 `keyword_fallback`

若有效概念列表抓取失败：

- Strategy B 标记 `degraded=True`
- 本轮允许跳过，不阻塞系统主流程

### 10.3 Strategy C：Smart Money

#### 10.3.1 目标

利用机构席位、北向资金、业绩超预期等信号，寻找“有资金质量”的标的。

#### 10.3.2 数据流

1. 龙虎榜/机构席位汇总
2. 北向资金摘要
3. 业绩预告/高增长筛选
4. 规则打分
5. 输出策略内 Top N

#### 10.3.2A MVP 数据能力重写

为避免长期设计空转，Smart Money 在 MVP 阶段改写为两层能力：

`最小可运行链路`
- `Tencent hist`
- 可选 `Tencent tick`

`增强链路`
- `THS fund flow`
- `Sina 龙虎榜`
- `Baidu valuation / vote / news`

状态判定规则：

- 只要 `Tencent hist` 可用，Smart Money 即可 `ready`
- 若增强链路缺失，记入 `risk_flags` 或 `raw_metrics`，但不应直接把策略打成不可运行
- 若 `Tencent hist` 不可用，再尝试 `Sina/Baostock/yfinance` 降级链
- 若历史链全失效，Smart Money 才进入 `degraded`

#### 10.3.3 评分公式

```text
C_score =
  0.45 * institutional_activity_score
  + 0.30 * northbound_score
  + 0.15 * earnings_quality_score
  + 0.10 * liquidity_score
```

辩证说明：

- `northbound_score` 对纯中小盘票的解释力有限
- `earnings_quality_score` 对题材股也不应赋予过高权重
- 因此 C 策略天然偏机构风格，不应被描述为“全风格通杀”

---

## 10A. Stage A 预筛设表（Phase 2 新增）

> 本节补充说明在 Stage B 三策略评分之前新增的两级过滤架构。

### 10A.1 为什么需要 Stage A

直接对 ~800 只股球运行 Stage B 三策略，会导几多无数据/低质量股球济赛 API 请求酏后和计算资源。Stage A 是一个轻量级预筛层，在不触发主要数据源的前提下，快速剔除明显无效的候选。

### 10A.2 Stage A 过滤条件

Stage A 在 \`engine.py\` 的 \`_run_stage_a()\` 中执行，对 Universe 构建出的所有股球逐只检查：

| 过滤条件 | 行为 | 原因 |
|---------|------|------|
| 无历史数据 | 剔除 | 无法进行任何策略评分 |
| 历史行数 < 10 | 剔除 | 数据不足，无法计算趨势 |
| 换手率 < 0.5% | 剔除 | 极度低流动性，无实际交易价值 |
| 折倒 (change_pct <= -9.9) | 剔除 | 极端风陹信号 |
| ST/*ST | 剔除 | Merger 熔断层统一外处理 |

### 10A.3 Stage B 输入截断

Stage A 通过的候选数量可能仍然很大（如 MVP 股球池 ~800 只）。通过 \`stageb_max_input\` 配置项（默认 1000）限制输入 Stage B 的数量。超出限制时取前 N 只（排序不变），并记录日志 \`Stage B limit applied: X -> Y\`。

Stage A 的结果写入 \`ScreenerMetrics.stagea_audit\` （含输入数、通过数、剔除数、各剔除原因的分布）。

### 10A.4 数据来源

Stage A 复用 \`ScreenerDataAccess.fetch_hist()\` 莧取历史K线。同一股球的同一日期范回请求会被进程级 \`_hist_cache\` 缓存，避免重复请求。

### 10A.5 与设表文档的关系

原始 \`SCREENER_DESIGN.md\` § 10 只描述了"初策"概念（无历史数据 → 剔除），Stage A 是对该概念的具体工程实现，增加了流动性过滤、极端价格过滤和数量截断。该设表不改变 \`SCREENER_DESIGN.md\` 的核心约束。

---

## 11. 安全熔断过滤

本节用于解决“过滤规则模糊且不可复盘”的问题。

### 11.1 硬过滤

以下条件命中即剔除：

- `ST` / `*ST`
- 跌停或近跌停：`change_pct <= -9.9`
- 低流动性：`turnover_rate < 2%` 或 `float_market_cap < 30亿`

### 11.2 条件过滤

以下规则仅在字段可用时启用：

- `PE < 0`
- `PE > 150`

若字段缺失：

- 不做剔除
- 仅添加 `risk_flag = "pe_unavailable"`

### 11.3 明确不做的事

本阶段不做逐票高质押硬过滤。

原因不是项目没有该工具，而是：

- 逐票抓质押会显著增加请求成本
- 不符合 Screener 第一阶段防封禁目标

但可以做：

- 在 Deep Analyzer 阶段按需补充质押风险
- 在 `risk_flags` 中保留“待补查”的风险提示位

---

## 12. 合并、去重、共振与排序

本节用于解决“多策略共振怎么加分、怎么去重”的问题。

### 12.1 去重主键

去重以 `ticker` 为主键。

### 12.2 融合规则

若同一股票被多个策略命中：

```text
screening_score =
  sum(strategy_score * strategy_weight)
  + resonance_bonus
```

其中：

- `strategy_weight` 取各策略全局权重
- `resonance_bonus = 5 * (命中策略数 - 1)`
- `screening_score` 上限封顶为 `100`

### 12.3 置信度定义

```text
initial_confidence =
  min(100, screening_score * 0.85 + data_quality_bonus - risk_penalty)
```

`data_quality_bonus`
- 所有关键源 fresh：`+5`
- 存在 estimated/stale：`0`

`risk_penalty`
- 每个高风险标记：`-3`

### 12.4 板块分散限制

`same_sector_limit = 2`

板块优先级定义：

1. 若有稳定的行业字段，优先行业
2. 若无行业字段，则退化为概念标签主分类
3. 若仍无，则使用 `unknown`

### 12.5 merger 输出

`merger.py` 输出：

- 最终候选 `SignalCard[]`
- 被剔除原因清单
- 多策略共振统计

---

## 13. 与现有 Harness 的深度集成

本节用于解决“筛完即忘，无法进入 memory/reflection”的问题。

### 13.1 Screener 不只是过滤器

Screener 必须进入现有系统的三条链路：

1. `orchestration`
2. `memory`
3. `reflection`

### 13.2 第一阶段最小集成要求

本阶段至少实现：

- `SignalCard` 注入 Deep Analyzer config
- 报告中保留 `trigger_reason / strategy_sources / risk_flags`
- 将 `screening_score`、`strategy_sources`、`concept_tags` 写入 Deep Analyzer 输出摘要

### 13.3 第二阶段预留接口

预留但不要求首批实现：

- `ScreenerReflection`
- `screening_context` 进入 analyst prompt
- `screening_score` 与 `final_decision_quality` 相关性统计

辩证说明：

- 我方建议做更深耦合，但第一阶段不应为了“闭环完美”阻塞主流程落地
- 因此本节只把首批最小集成写成硬需求，剩余写成预留接口

---

## 14. 异常与降级矩阵

本节用于解决“失败后到底怎么处理”的问题。

### 14.1 策略级降级

| 场景 | 行为 | 是否阻塞整轮 |
|------|------|-------------|
| Strategy A 全失败 | 标记 degraded，继续执行 B/C | 否 |
| Strategy B 全失败 | 标记 degraded，继续执行 A/C | 否 |
| Strategy C 全失败 | 标记 degraded，继续执行 A/B | 否 |
| 三个策略都失败 | 返回空候选 + Fatal issue | 是 |

### 14.2 数据级降级

| 场景 | 行为 |
|------|------|
| 概念列表获取失败 | 跳过 B，记入 metrics |
| LLM 概念抽取失败 | 走关键词 fallback |
| 历史日线部分缺失 | 对成功样本继续打分 |
| 龙虎榜缺失 | C 降权，不整轮终止 |
| 北向资金缺失 | C 降权，不整轮终止 |
| PE 字段缺失 | 仅打风险标记，不过滤 |

### 14.3 Deep Analyzer 级降级

| 场景 | 行为 |
|------|------|
| 单只深度分析失败 | 记录 `DeepAnalysisResult.success=False` |
| Top 3 中 1 只失败 | 不递补 |
| Top 3 中 2 只失败 | 允许从第 4、第 5 候选递补，仅 EXTENDED 模式启用 |
| 全部失败 | 输出“仅初筛推荐报告”，不伪造深度结论 |

### 14.4 报告级约束

报告必须明确写出：

- 哪些策略降级了
- 哪些数据源缺失
- 最终结论属于“完整深度分析”还是“仅初筛推荐”

---

## 15. Deep Analyzer 编排规格

### 15.1 基本原则

- MVP 只顺序分析
- 默认 Top 3
- 每只之间冷却 2 秒

### 15.2 配置对象

```python
@dataclass
class DeepAnalyzerConfig:
    max_stocks: int = 3
    delay_between_stocks: float = 2.0
    retry_on_failure: bool = True
    max_retries: int = 1
```

注意：

- 该 dataclass 只属于 Screener 编排器
- 不能直接传给 `TradingAgentsGraph`

### 15.3 Graph config 生成

```python
graph_config = DEFAULT_CONFIG.copy()
graph_config.update(user_graph_overrides or {})
graph_config["company_of_interest"] = signal_card.ticker
graph_config["screener_context"] = {...}
```

### 15.4 调用方式

```python
ta = TradingAgentsGraph(debug=False, config=graph_config)
final_state, decision = ta.propagate(signal_card.ticker, signal_card.trade_date)
```

### 15.5 timeout 处理原则

当前不修改 `TradingAgentsGraph.propagate()` 签名。

若后续需要 timeout：

- 由 Screener 编排器外层控制
- 不在本阶段强改 graph 核心接口

---

## 16. 指标、日志与报告

### 16.1 必须记录的指标

`ScreenerMetrics` 至少包含：

- `run_id`
- `mode`
- `universe_size`
- `strategy_a_candidates`
- `strategy_b_candidates`
- `strategy_c_candidates`
- `final_candidates`
- `api_requests_total`
- `api_requests_failed`
- `degraded_strategies`
- `elapsed_seconds_total`
- `llm_calls_total`

### 16.2 报告输出形式

必须同时输出：

1. `screening_result.json`
2. `daily_gold_stocks_report.md`

### 16.3 报告最小字段

每只候选必须展示：

- ticker / name
- strategy sources
- trigger reason
- screening score
- initial confidence
- risk flags
- deep analysis result status

---

## 17. 测试矩阵

本节用于解决“实现了但无法证明可用”的问题。

### 17.1 单元测试

至少新增以下测试文件：

```text
tests/test_screener_models.py
tests/test_screener_runtime_guard.py
tests/test_screener_throttling.py
tests/test_screener_universe.py
tests/test_screener_strategy_technical.py
tests/test_screener_strategy_policy.py
tests/test_screener_strategy_smart_money.py
tests/test_screener_merger.py
tests/test_screener_deep_analyzer.py
```

### 17.2 集成测试

至少覆盖：

- 股票池构建
- 三策略各自成功路径
- 单策略失败路径
- Screener -> Deep Analyzer 桥接
- 报告输出

### 17.3 伪数据测试

必须引入 fake data 场景：

- 三策略共振
- 只有单策略命中
- 概念列表为空
- 历史数据部分缺失
- Deep Analyzer 单只失败

### 17.4 性能测试

MVP 模式验收上限：

- Screener 总耗时：`<= 8 分钟`
- Deep Analyzer 3 只：`<= 15 分钟`
- 单轮总请求数：记录但不硬卡死

辩证说明：

- V5.0 的“4分钟 Screener”是理想估计，不应直接写成硬承诺
- V6.0 改成更保守的生产验收阈值

---

## 18. 验收标准

### 18.1 功能验收

- 能稳定产出 Top 3 `SignalCard`
- 至少一条策略成功时系统仍可输出结果
- Deep Analyzer 能顺序消费候选并产出结果

### 18.2 稳定性验收

- 单策略失败不崩溃
- 数据缺失时有明确降级标记
- 不出现字段缺失导致的序列化失败

### 18.3 可审计性验收

- 每只候选都能追溯来源策略
- 每个分数都可拆到原始子分数
- 每轮运行都能看到 degraded 原因

### 18.4 兼容性验收

- 不破坏现有 `TradingAgentsGraph`
- 不破坏现有 CN 工具测试
- 不修改现有 `propagate()` 签名

---

## 19. 分阶段实施计划

### Phase A0：接口验证

先验证免费数据源假设，不写大规模业务代码。

交付：

- fund flow 可用性结论
- 概念接口可用性结论
- 龙虎榜/北向/业绩源更新时间结论

### Phase A1：基础骨架

实现：

- `models.py`
- `config.py`
- `runtime_guard.py`
- `throttling.py`
- `universe.py`

### Phase A2：三策略 MVP

实现：

- `technical.py`
- `policy.py`
- `smart_money.py`
- `merger.py`

### Phase A3：Deep Analyzer 桥接

实现：

- `deep_analyzer.py`
- `report.py`
- 端到端 JSON/Markdown 输出

### Phase A4：测试与收尾

实现：

- 单元测试
- 集成测试
- 文档与指标补齐

---

## 20. 本文档中的明确取舍

为了避免后期反复争论，以下取舍在 V6.0 中明确固定：

1. MVP 不做抓数并发
2. MVP 默认股票池不是全市场
3. MVP 不做质押硬过滤
4. MVP 不修改 `TradingAgentsGraph` 核心签名
5. MVP 先做结构化输出，再考虑更深 memory/reflection 闭环

这些取舍不是“理论最优”，而是当前仓库、免费数据源、实现成本三者折中的工程最优。

---

## 21. 当前仍保留的不确定性

以下问题在文档中已经被约束，但仍不应被误判为完全确定：

1. AkShare 免费源的批量 fund flow 形式是否稳定
2. 不同数据源在 `16:30-18:00` 的实际刷新延迟
3. 北向与龙虎榜对中小盘标的的解释力边界
4. Top 3 的固定输出上限是否在后续需要动态放宽

因此实现时必须保留：

- feature flag
- degraded 标记
- metrics 记录

---

## 22. 最终结论

V6.0 的目标不是把 Screener 设计得最“聪明”，而是把它设计成：

- 能接入当前项目
- 能在免费数据源现实约束下稳定运行
- 能明确降级与审计
- 能作为后续更强闭环系统的可靠前置层

后续所有 Screener 开发，均以本文档为唯一实施基线；若实现过程中发现免费源行为与本文档假设不一致，应优先修正文档，再修改代码，不允许一边偏离文档一边静默实现。
