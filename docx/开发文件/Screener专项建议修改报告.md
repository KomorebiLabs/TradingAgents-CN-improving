# Screener 专项建议修改报告

审查日期：2026-08-24  
审查对象：`tradingagents/screener`、`cli/screener`、`tradingagents/backtest`、Screener 配置、测试与报告产物  
审查方式：GitNexus 执行流/符号关系分析、源码抽样审查、CLI 帮助验证、现有测试及回测结构检查  
审查结论：Screener 已具备“多策略股票候选发现”工程骨架，但尚未达到“稳定扫描当日市场并给出经过验证的股票推荐”的验收标准。

## 一、执行摘要

当前 Screener 不是空白模块，也不是只有页面展示。它已经形成了以下执行链：

```text
股票池构建
  → Stage A 历史数据/流动性/异常预筛
  → TechnicalStrategy
  → PolicyStrategy
  → SmartMoneyStrategy
  → 多策略合并、冲突处理、硬过滤、行业分散
  → 可选 DeepAnalyzer
  → JSON/Markdown 审计报告
```

这套链路具备较好的工程展示价值，尤其是结构化信号卡片、策略证据、风险标签、数据供应商降级、候选淘汰原因和运行产物。

但目前不能把它描述为“全市场当日选股系统”，也不能把 `BUY/HOLD/SELL` 当作经过回测验证的交易信号。主要原因是：

1. 默认股票池是多个指数成分股并集，不是全市场股票；
2. 股票池缓存没有严格按交易日或有效期失效；
3. 数据降级后仍可能产生并保留候选；
4. 没有严格的当日数据新鲜度门禁；
5. FULL 模式在 Stage B 前按股票池原始顺序截取前 N 只，未按轻量评分选出最优输入；
6. 标准模式暴露了 `stagea_max_input`，但 Engine 没有在 Stage A 前统一执行；
7. 默认 FULL 模式没有完整进入现有盘中/收盘后时间保护，最近交易日计算也不识别法定休市日；
8. 分数和 BUY/HOLD/SELL 阈值尚未经过充分的样本外校准；
9. 仓库已有技术策略回测，但存在 T 日收盘信号可能使用 T 日收益、交易成本缺失和当前成分股幸存者偏差；
10. Screener 缺少完整的 Engine 级集成测试；
11. DeepAnalyzer 的 dry-run 结果使用 `success=True`，容易让上层误认为真实深度分析成功。

因此建议将改造目标分成两个阶段：

- 第一阶段：先修复执行正确性、数据可信度和状态语义；
- 第二阶段：升级现有回测并完成样本外验证，最后才考虑对外使用“推荐”措辞；
- 第三阶段：核心链路稳定后，再扩展全市场股票池和性能能力。

### 1.1 证据索引

以下结论均来自当前代码事实；“建议”部分是拟议设计，不代表当前已经实现。

| 事实 | 代码证据 |
|---|---|
| Engine 创建数据访问实例后，构建股票池时未传入该实例 | `tradingagents/screener/engine.py:209-213` |
| Stage B 按原顺序直接切片 | `tradingagents/screener/engine.py:242-246` |
| 标准模式没有统一应用 Stage A 输入上限 | `tradingagents/screener/engine.py:228-233`、`tradingagents/screener/universe.py:362-366` |
| 股票池缓存存在即返回，没有日期/有效期校验 | `tradingagents/screener/universe.py:60-68`、`:233-238` |
| FULL 不在 MVP/EXTENDED 的盘中保护集合内 | `tradingagents/screener/runtime_guard.py:53-60` |
| 最近交易日只按周末回退 | `cli/screener/run_impl.py:28-34` |
| 合并过滤没有把验证状态作为统一资格门禁 | `tradingagents/screener/merger/filters.py:28-121` |
| dry-run 仍返回 `success=True` | `tradingagents/screener/deep_analyzer.py:170-202` |
| 已有技术策略回测及标准绩效指标 | `tradingagents/backtest/engine.py:1-156`、`performance.py:20-120` |
| 回测信号日立即切换持仓并应用当日收益 | `tradingagents/backtest/performance.py:97-115` |
| 现有回测明确未建模成本且存在成分股幸存者偏差 | `tradingagents/backtest/report.py:67-75` |
| 供应商健康当前只有平均耗时，没有 P95 样本 | `tradingagents/dataflows/vendor_health.py:32-71` |

## 二、当前实现能力盘点

### 2.1 已经具备的能力

| 能力 | 当前状态 | 评价 |
|---|---|---|
| 股票池构建 | 已实现指数成分股展开、FOCUSED、CUSTOM | 工程骨架完整，但范围不是全市场 |
| Stage A 预筛 | 已实现历史数据、最小行数、换手率、异常涨跌幅检查 | 有效，但对数据日期和异常原因记录仍不充分 |
| 技术策略 | 已实现均线、收益、波动、回撤、成交量等指标 | 属于启发式评分，未完成预测有效性验证 |
| 政策策略 | 已实现概念、政策新闻、板块与核心股标签 | 数据缺失时会降级，但降级候选未强制阻断 |
| 资金策略 | 已实现资金流、龙虎榜、成交与热度相关逻辑 | 供应商依赖多，需强化证据一致性 |
| 多策略合并 | 已实现共振加分、冲突处理、风险扣分、行业分散 | 规则较丰富，但缺少数据可信度硬门禁 |
| 供应商健康 | 底层已有健康状态、探测、熔断/降级记录 | 需要提升为 Screener 报告的一等结果 |
| 结果审计 | 已输出 JSON 和 Markdown，包含候选、淘汰、指标与能力摘要 | 具备面试展示价值 |
| 深度分析 | 已有真实 Agent 路径和 dry-run 降级路径 | 状态语义需要修正，避免成功状态误导 |

### 2.2 当前产品定位

当前最准确的定位是：

> 基于指数成分股的多策略 A 股候选发现与研究辅助系统。

不建议当前定位为：

> 扫描当天全部股票并稳定给出买入推荐的实盘选股系统。

## 三、问题清单与修改建议

以下优先级含义：

- **P0：必须先修复，否则不应把结果称为正式推荐**；
- **P1：影响准确性、可维护性或面试可信度，应在近期完成**；
- **P2：增强项，可在核心链路稳定后处理**。

### P0-1：建立明确的 Screener 结果契约

#### 问题

当前报告把候选、评分、信号和深度分析结果放在同一条链路中，但没有明确区分：

- 数据是否经过验证；
- 是否只使用到目标交易日之前的数据；
- 是否允许在降级状态下输出候选；
- 候选是“研究对象”还是“交易建议”。

#### 建议修改

新增明确的结果状态模型，例如：

```text
RUN_READY
RUN_DEGRADED
RUN_BLOCKED

VERIFIED_CANDIDATE
DEGRADED_CANDIDATE
UNVERIFIED_CANDIDATE
```

当前 `SignalEvidence` 已有 `DataFreshness(source, trade_date, fetched_at, status)`。不要在 `SignalCard` 再维护一份可独立写入的重复日期状态；应保留来源级原始 freshness，并由合并器生成只读聚合摘要：

```text
data_quality_status
aggregated_freshness
  latest_required_data_date
  max_required_data_lag_days
  stale_required_sources
required_evidence_missing
recommendation_eligible
recommendation_block_reason
```

`ScreeningResult` 只汇总运行级状态和统计，`SignalCard` 保存聚合后的候选资格，原始供应商日期仍以每条 `SignalEvidence.freshness` 为唯一事实来源。

#### 验收标准

- 任一关键数据源没有验证通过时，运行状态必须显示 `RUN_DEGRADED`；
- `recommendation_eligible=False` 的候选不能进入正式推荐列表；
- 报告必须清楚区分“候选发现”和“可交易建议”；
- 所有降级原因必须可追溯到供应商、接口和字段。

### P0-2：增加严格的数据新鲜度和交易日门禁

#### 问题

Stage A 调用历史数据时使用目标交易日作为 `end_date`，但没有严格确认返回数据最后日期就是目标交易日，也没有清楚区分实时、延迟、旧缓存和最近交易日数据。

#### 建议修改

在统一数据访问层增加标准化校验：

1. 解析每个供应商返回数据的最后有效日期；
2. 与 `trade_date` 比较，计算 `data_lag_days`；
3. 区分交易日和自然日；
4. 对收盘后运行、盘中运行、非交易日运行使用不同策略；
5. 对关键字段设定最大允许滞后天数；
6. 将 `fresh/stale/missing/estimated` 统一写入证据。

建议使用以下门禁规则：

| 数据状态 | 研究候选 | 正式推荐 |
|---|---:|---:|
| fresh 且目标交易日一致 | 允许 | 允许 |
| 轻微滞后且有明确说明 | 允许但降级 | 禁止 |
| stale、missing、estimated | 只进入诊断报告 | 禁止 |

#### 验收标准

- 用 fake provider 返回旧日期数据时，测试必须得到 `stale`；
- 目标日期没有行情时，不能静默使用旧缓存冒充当日数据；
- 报告显示每个候选的最后数据日期和滞后天数；
- 没有新鲜核心数据时，最终候选列表为空或全部标记为不可推荐。

### P0-3：修复股票池缓存的日期有效性

#### 问题

`load_universe_cache()` 当前发现缓存文件存在即可返回，缓存元数据中的 `built_at` 没有参与有效性判断。指数成分股发生调整时，旧股票池可能继续用于新交易日扫描。

#### 建议修改

缓存至少应包含：

```text
trade_date
as_of
source_vendor
source_signature
constituent_version
built_at
expires_at
```

读取缓存时校验：

- 缓存交易日是否与运行目标一致；
- `source_signature` 是否与当前配置一致；
- 是否超过有效期；
- 是否存在供应商更新标记；
- 是否允许使用旧缓存作为降级数据。

建议将“正常缓存”和“降级缓存”分开标记，旧缓存不得伪装成当日正式股票池。

#### 验收标准

- 不同交易日不能无条件复用同一个股票池缓存；
- 配置指数发生变化时必须重新构建；
- 过期缓存只能产生降级运行状态；
- 报告明确显示股票池的来源、构建时间和有效期。

### P0-4：建立结构化证据资格门禁

#### 问题

三类策略已经设置 `degraded` 和 `data_source_verified`，但合并过滤器主要依据 ST、换手率、市值、PE、资金质量、技术风险等条件，没有把数据验证状态作为统一资格门禁。

更深层的问题是单一布尔值的含义并不一致：TechnicalStrategy、PolicyStrategy、SmartMoneyStrategy 对“已验证”的依赖集合不同。简单判断 `data_source_verified=False` 无法说明具体缺失了历史行情、资金流、概念数据还是辅助数据。

#### 建议修改

先为每个策略声明必需证据和可选证据，再由统一 `eligibility_gate` 聚合，不要把资格逻辑继续散落到各策略中：

```text
required_evidence_verified
optional_evidence_verified
verified_modules
missing_required_modules
degraded_modules
verified_strategy_count
recommendation_eligible
```

建议提供两个输出模式和策略配额：

- `research`：允许降级候选，但必须显著标注；
- `recommendation`：必需证据不完整时阻断；
- `minimum_verified_strategy_count`：规定至少有多少个独立策略完整验证；
- 不因某个可选辅助源降级而无条件丢弃其他证据完整的策略结果。

#### 验收标准

- 缺少必需证据的候选不能出现在正式推荐列表；
- 淘汰原因包含具体缺失证据，而不是只显示“低分”；
- 单个可选数据源降级不会错误否决其他完整策略；
- 对同一组输入，research 和 recommendation 模式的差异有测试覆盖。

### P0-5：修正 DeepAnalyzer 的成功状态语义

#### 问题

DeepAnalyzer 失败后进入 dry-run，但 dry-run 结果仍然使用 `success=True`。上层如果只读取 `success`，会误以为 LLM 深度分析已经完成。

#### 建议修改

将状态拆成枚举，逐步废弃含义模糊的单一 `success`：

```text
analysis_status:
  GRAPH_COMPLETED
  DRY_RUN_REQUESTED
  FALLBACK_COMPLETED
  FAILED

fallback_used: true | false
fallback_reason: string
```

用户主动关闭真实分析与真实分析失败后回退必须区分：

```text
主动关闭：DRY_RUN_REQUESTED, fallback_used=False
调用失败后降级：FALLBACK_COMPLETED, fallback_used=True
真实图完成：GRAPH_COMPLETED, fallback_used=False
```

如果短期仍保留 `success`，必须文档化它表示“本次请求产生了可消费结果”还是“真实图执行成功”，不能让调用方猜测；不建议简单把所有 dry-run 一律改成 `False`。

同时在 CLI、JSON、Markdown 中显式显示：

```text
真实深度分析：未执行/失败
降级原因：...
```

#### 验收标准

- LLM 调用异常时，结果不能标记为真实成功；
- 测试覆盖超时、认证失败、限流和模型不可用；
- 报告不会把 dry-run 文本显示成真实投资结论。

### P0-6：修复 Stage B 按原始顺序截断

#### 问题

Engine 在 Stage A 通过后直接执行 `stagea_pass_tickers[:stageb_max]`。Stage A 当前只返回通过/淘汰，没有提供排序分数，因此 FULL 模式实际分析的是“通过列表中的前 N 只”，不是“最值得进入 Stage B 的 N 只”。最终结果会受到供应商返回顺序和指数合并顺序影响。

#### 建议修改

让 Stage A 返回结构化轻量候选：

```text
StageACandidate
  ticker
  data_completeness_score
  liquidity_score
  basic_momentum_score
  anomaly_flags
  stage_a_score
```

完成去重和稳定排序后再截取 Stage B 输入，并把截断前后数量、最低入选分、被截断数量写入漏斗审计。若暂时无法形成合理轻量分数，宁可明确采用可复现的分层抽样，也不能依赖接口原始顺序。

#### 验收标准

- 调换股票池原始顺序不会显著改变同一数据集的 Stage B 入选集合；
- `stageb_max_input` 的截断依据可解释、可复现；
- FULL 报告明确显示多少股票没有进入完整三策略分析。

### P0-7：让 Stage A 输入限制在所有模式真实生效

#### 问题

CLI 和配置暴露 `stagea_max_input`，但标准模式的 Engine 在执行 Stage A 前没有统一应用；当前主要只有部分 FOCUSED 路径进行了截断。这会形成“参数接受了，但行为没有改变”的配置假象。

#### 建议修改与验收

- 在 Engine 编排层统一执行输入预算，避免仅在某个 Universe 分支实现；
- 明确输入预算发生在去重之后、请求之前；
- 报告记录 `universe_count`、`stagea_budget`、`stagea_actual_input`；
- 增加参数化测试，证明 FULL、MVP、FOCUSED、CUSTOM 均遵守配置。

### P0-8：修复生产模式时间保护和交易日判断

#### 问题

运行守卫的盘中和收盘后稳定窗口主要只检查 MVP/EXTENDED，而 CLI 默认是 FULL。`_get_last_trading_day()` 只按星期回退，也会把法定休市工作日误认为交易日。

#### 建议修改与验收

- 用显式 `production_modes` 集合统一管理 FULL、MVP、EXTENDED、FOCUSED 和 CUSTOM 的默认行为；
- 只有明确的实验模式可以盘中运行，并强制标记数据未闭合；
- 接入可缓存的 A 股交易日历，网络不可用时使用本地版本并报告 `calendar_as_of`；
- 参数化测试覆盖所有模式、周末、法定节假日、盘中、收盘后不稳定窗口和历史日期。

### P0-9：修复 Stage A 固定涨跌幅“异常”规则

#### 问题

Stage A 使用固定约 `±9.9%` 检查最近三日涨跌幅，并将命中者归为 `extreme_price_anomaly`。这没有区分 ST、主板、创业板、科创板、北交所和新股特殊阶段，也混淆了“合法涨跌停”“策略风险”和“脏数据异常”。近期涨停还可能正是动量策略希望研究的信号。

#### 建议修改与验收

- 复用统一交易规则模块，按股票、板块、日期解析当日涨跌幅限制；
- 数据异常检查只处理不可能值、价格断层和字段错误；
- 合法涨跌停作为 `market_state` 或风险标签进入策略，不在 Stage A 无条件淘汰；
- 使用主板、ST、创业板/科创板、北交所和新股样例做参数化测试。

## 四、P1 级结构和工程问题

### P1-1：扩大股票池能力，但保留可控范围

当前 `FULL` 只是五类指数并集。建议增加明确的 `MARKET` 或 `ALL_A_SHARE` 模式，并把股票池分成：

```text
INDEX_UNION
MARKET_SNAPSHOT
SECTOR_FOCUS
CUSTOM
```

全市场模式需要配套：

- 上市状态过滤；
- ST、退市整理、停牌过滤；
- 北交所、科创板、创业板交易规则差异；
- 供应商批量行情接口；
- 分批、限流、断点和缓存；
- 股票池规模和耗时指标。

不能简单把所有代码拼进现有循环，否则会把当前每只股票逐个请求的性能问题放大。

### P1-2：让 Engine 复用同一个数据访问实例

`ScreenerEngine.run()` 已经创建了 `ScreenerDataAccess`，但构建股票池时没有把该实例传入 `build_screening_universe()`，而该函数本身支持 `data_access` 参数。

建议统一改为：

```python
universe = build_screening_universe(
    mode=mode,
    config=self.config,
    data_access=data_access,
)
```

这样可以统一：

- 供应商健康状态；
- 请求统计；
- 熔断状态；
- HTTP 会话；
- 缓存命中率；
- 本次运行的审计上下文。

### P1-3：收窄 Stage A 的异常分类

当前 Stage A 对单只股票的异常较宽泛地归类为 `no_hist_data`。这会把以下情况混为一类：

- 股票确实没有历史数据；
- 供应商超时；
- 代码格式错误；
- 返回字段变化；
- 解析失败；
- 本地缓存损坏。

建议统一错误码：

```text
NO_DATA
STALE_DATA
VENDOR_TIMEOUT
VENDOR_RATE_LIMITED
SCHEMA_ERROR
INVALID_TICKER
LOCAL_CACHE_ERROR
```

报告需要同时展示汇总数量和示例代码，便于判断是股票问题还是供应商问题。

### P1-4：统一代码格式化和交易规则

Stage A 中存在手动交易所后缀格式化逻辑，覆盖沪深，但没有完整复用股票池的北交所格式化能力。

建议建立唯一的 `normalize_ticker()` 和 `format_ticker()` 入口，统一处理：

- 沪市；
- 深市；
- 北交所；
- ETF/指数代码；
- 已带后缀和不带后缀代码；
- 供应商专用代码格式。

不要在 Engine、策略、供应商适配器中各自判断交易所。

### P1-5：把供应商健康状态提升为一等报告产物

底层 `ScreenerDataAccess` 已能生成供应商健康快照，能力摘要也会携带相关信息。建议进一步完善：

每次运行固定输出：

```text
vendor_health.json
vendor_health.md
```

至少包含：

- 每个供应商的成功率；
- 请求数、失败数、超时数、限流数；
- 平均延迟；如需 P95，先增加有界延迟样本或 histogram/bucket，当前 tracker 只有累计耗时，不能直接推导 P95；
- 熔断状态；
- 当前主供应商和备用供应商；
- 最近成功时间；
- 使用了哪些降级路径。

Markdown 报告的摘要区也应直接显示，而不是要求用户深入 JSON 的嵌套字段才能看到。

### P1-6：拆分“评分”“置信度”“推荐资格”

当前 `screening_score`、`initial_confidence` 和 CLI 的 BUY/HOLD/SELL 映射容易被理解成同一种概率。

建议明确区分：

```text
raw_score              启发式原始分
calibrated_probability 经过历史样本校准后的概率（尚未实现前不要伪造）
confidence              证据完整性/一致性置信度
recommendation_eligible 是否满足正式推荐门槛
signal_label            候选标签，不等于收益保证
```

在完成回测校准前，CLI 标签建议改成：

```text
STRONG_CANDIDATE
WATCHLIST
RESEARCH_ONLY
```

而不是直接显示 `BUY/HOLD/SELL`。

### P1-7：修正“无候选即 FATAL”的错误语义

`check_data_consistency()` 当前在候选为空时直接写入 `[FATAL] 没有候选股票，策略可能全部失效`。但严格过滤后得到零候选可能是完全合法且更安全的结果，不能自动等同于策略失效。

建议区分：

```text
NO_CANDIDATE_VALID       数据完整、规则正常、当日无合格候选
NO_CANDIDATE_DEGRADED    数据降级导致无法形成候选
PIPELINE_FAILED          关键阶段失败
```

只有第三种应为 FATAL；前两种分别是正常空结果和降级结果。

### P1-8：统一 DeepAnalyzer 配置读取层级

CLI 构建配置时把 `enable_real_deep_analysis` 放在 `deep_analyzer` 子字典内，但 `DeepAnalyzer._resolve_real_analysis_flag()` 读取的是顶层 `self.config`。虽然 `--no-deep` 当前会从 Engine 层跳过整个阶段，但直接构造 DeepAnalyzer 或其他调用路径可能忽略嵌套配置。

建议只保留一个配置契约，并增加以下测试：

- 顶层旧配置的兼容迁移；
- `deep_analyzer.enable_real_deep_analysis=false` 确实进入主动 dry-run；
- CLI `--no-deep` 确实完全跳过阶段；
- 环境变量只作为最低优先级回退。

## 五、P0/P1 级量化验证缺口

### 5.1 升级现有 Screener 技术策略回测，不重复建设

仓库已经存在 `tradingagents/backtest`，并非完全没有 Screener 回测。现有实现会：

```text
CSI300 当前成分股切片
  → 使用真实 TechnicalStrategy.run 生成 Top-K
  → 定期等权调仓
  → 计算收益、年化波动、夏普、最大回撤、胜率和 CSI300 超额收益
  → 输出 Markdown、CSV 和净值曲线
```

因此不建议另建一套平行的 `tradingagents/screener/evaluation`。应以现有 `tradingagents/backtest` 为唯一回测入口，扩展其数据契约、执行模型、泄漏检查和报告。

现有回测已经明确披露以下限制：只覆盖技术策略；不建模手续费、滑点和涨跌停成交；股票池使用当前 CSI300 成分股，存在幸存者偏差。还需优先修复一个更具体的问题：信号在 T 日收盘数据上生成，但持仓在同一个 T 日立即生效并应用 T 日 close-to-close 收益，可能形成前视偏差。

### 5.2 P0：修复 T 日信号使用 T 日收益

正确的最小执行模型应明确：

```text
T 日收盘后生成信号
  → T+1 第一个可成交时点执行
  → 从实际成交价格之后开始计算持仓收益
```

需要增加：

- `signal_time`、`execution_time`、`execution_price_type`；
- T+1 开盘、VWAP 或可配置成交模型；
- 停牌、涨跌停无法成交时延迟或取消订单；
- 针对 T/T+1 边界的确定性回归测试。

在该问题修复前，现有收益曲线只能作为工程演示，不能作为策略有效性证据。

### 5.3 P1：扩展现有回测能力

在修复执行时序后，现有模块至少应继续支持：

- 固定历史交易日生成候选；
- 使用当时可获得的数据；
- 计算 T+1、T+5、T+20 收益；
- 与 CSI 300、中证 500或等权基准比较；
- 手续费、印花税、滑点；
- 停牌、涨跌停、无法成交处理；
- 最大回撤、波动率、换手率；
- Top-K 命中率和收益分布；
- 样本内、验证集、样本外切分。

PolicyStrategy 和 SmartMoneyStrategy 当前缺少可靠的历史 point-in-time 概念、政策、资金流快照，不能通过今天的接口结果重建过去信号。应先建立不可变历史快照，再扩展到三策略回测；在此之前只能诚实声明“技术策略回测”。

### 5.4 防止其他前视偏差和幸存者偏差

评估时必须记录：

- 股票池在当时是否已经属于指数成分股；
- 财务、公告、政策和资金数据的发布时间；
- 是否误用了收盘后才产生的数据；
- 是否使用了后来退市股票之外的幸存者集合；
- 是否用未来复权数据影响了当日决策。

没有这些约束，回测数字即使很好也不能证明策略有效。

### 5.5 阈值应来自验证集，而不是手工猜测

当前分数阈值、风险扣分、策略权重和输出数量都应在配置中保留版本号，并在回测报告中记录：

```text
config_version
threshold_snapshot
training_period
validation_period
test_period
benchmark
data_sources
```

任何修改阈值后的结果都必须生成新的评估记录，不能覆盖旧结果。

## 六、P0/P1 级测试计划

建议至少补充以下测试分组：

### 6.1 Universe 测试

- 缓存命中；
- 缓存过期；
- 交易日不一致；
- 指数配置变更；
- 供应商全部失败；
- CUSTOM 模式不请求指数接口；
- 北交所代码格式化；
- 去重和股票池规模限制。

### 6.2 Engine 集成测试

使用 fake `ScreenerDataAccess`，验证完整链路：

```text
universe → Stage A → strategies → merger → report
```

覆盖：

- 全部数据正常；
- 历史数据缺失；
- 供应商超时；
- 仅部分策略降级；
- 所有策略降级；
- 无候选；
- DeepAnalyzer dry-run；
- 报告产物完整性。
- `stagea_max_input` 在所有模式真实生效；
- 调换股票池原始顺序后，Stage B 入选不依赖原始顺序；
- `stageb_max_input` 截断规则及漏斗指标正确。

### 6.3 Freshness 和资格门禁测试

- 最后一根 K 线早于目标交易日；
- 目标日期为周末；
- 目标日期无交易；
- 供应商返回旧缓存；
- `data_source_verified=False`；
- evidence 中存在 degraded 项；
- research/recommendation 两种模式差异。
- 一个策略的可选证据降级，不会错误否决其他完整策略；
- 必需证据和可选证据产生不同资格结果。

### 6.4 CLI 端到端测试

- `--mode CUSTOM --tickers ... --no-deep`；
- 输出目录可控；
- JSON 和 Markdown 同步生成；
- 运行失败返回非零退出码；
- dry-run 不被报告为真实成功；
- 供应商健康状态写入运行目录。

### 6.5 时间守卫和交易日历测试

- FULL、MVP、EXTENDED、FOCUSED、CUSTOM 的生产规则一致；
- EXPERIMENTAL 盘中运行必须显式标记未闭合数据；
- 周末、法定节假日、临时休市和历史日期；
- 15:00 到稳定时间窗口之间默认拒绝正式运行；
- 本地交易日历过期时产生明确降级状态。

### 6.6 回测执行时序测试

- T 日收盘信号不获取 T 日已发生收益；
- T+1 正常成交、停牌、涨停买不进、跌停卖不出；
- 手续费、印花税和滑点按配置进入净值；
- 当前成分股回测必须显式标记幸存者偏差；
- point-in-time 股票池可用后，验证历史成分股切换。

## 七、P2 增强项

### 7.1 性能和请求效率

当前 Stage A 按股票逐只调用历史数据。扩展到全市场后，可能形成明显的 N+1 请求问题。

建议优先级：

1. 优先使用供应商批量行情接口；
2. 对历史数据按交易日或股票池批量缓存；
3. 将 Stage A 指标计算改为向量化；
4. 为每阶段设置请求预算和时间预算；
5. 支持失败股票断点续跑；
6. 记录每阶段的吞吐量、缓存命中率和延迟；P95 使用有界样本或 histogram 计算。

### 7.2 运行可观测性

建议在结果中增加漏斗指标：

```text
universe_input_count
stage_a_pass_count
stage_b_input_count
technical_card_count
policy_card_count
smart_money_card_count
merged_count
hard_filter_drop_count
stale_drop_count
unverified_drop_count
final_research_candidates
final_recommendation_candidates
```

这比只记录“最终得到几只股票”更能解释系统行为。

### 7.3 报告表达

当前报告名称可以保留，但“金股”“BUY”等措辞应谨慎。建议在报告头部固定显示：

```text
本报告为研究辅助输出，不构成投资建议。
本次运行是否允许正式推荐：是/否。
禁止推荐原因：数据滞后/供应商降级/证据不足/未完成回测校准。
```

## 八、推荐实施顺序

### 第 1 批：执行正确性

1. 修复 Stage B 按原始顺序截断，建立可解释的 Stage A 轻量排序；
2. 让 `stagea_max_input` 在全部模式真实生效；
3. 修复 FULL 等生产模式的运行时间保护；
4. 接入真实 A 股交易日历；
5. 修复固定 ±9.9% 异常规则；
6. 修复现有回测 T 日信号使用 T 日收益；
7. 为上述行为增加确定性回归测试。

### 第 2 批：可靠性与状态门禁

1. 定义运行状态和结构化证据资格；
2. 实现实际数据日期的新鲜度校验；
3. 阻止缺少必需证据的候选进入正式推荐；
4. 区分 DeepAnalyzer 真实成功、主动 dry-run 和失败回退；
5. 修复股票池缓存有效期；
6. Engine 复用同一个 `ScreenerDataAccess`；
7. 增加 fake-provider、Universe 和故障测试。

### 第 3 批：策略与回测可信度

1. 拆分 raw score、confidence 和 recommendation eligibility；
2. 暂时将 BUY/HOLD/SELL 改为候选标签；
3. 扩展现有 `tradingagents/backtest`，不另建平行回测系统；
4. 增加交易成本、成交约束、point-in-time 股票池和样本外切分；
5. 先验证技术策略，再在历史快照可用后验证政策/资金策略；
6. 以样本外结果决定是否恢复“推荐”表述。

### 第 4 批：全市场与性能

1. 增加全市场股票池模式；
2. 接入批量行情接口；
3. 完善限流、断点、缓存和请求预算；
4. 进行多交易日真实运行验收；
5. 根据运行指标优化并发和供应商路由。

## 九、实施矩阵

任何业务代码修改前，必须按仓库规则对目标符号执行 GitNexus upstream impact；如果风险为 HIGH 或 CRITICAL，应先拆分变更并告知影响范围。

| 优先级 | 问题 | 主要目标符号/文件 | 必需测试 | 验收结果 |
|---|---|---|---|---|
| P0 | Stage B 原始顺序截断 | `ScreenerEngine.run`、`_run_stage_a` | Engine 顺序不变性测试 | 入选由显式轻量分数决定 |
| P0 | Stage A 上限未统一生效 | `ScreenerEngine.run` | 全模式参数化测试 | 请求前执行统一预算 |
| P0 | FULL 绕过时间保护 | `TimeValidator.validate` | 全模式时间矩阵 | 生产模式规则一致 |
| P0 | 交易日只按周末判断 | `_get_last_trading_day` | 节假日/休市测试 | 使用有版本的交易日历 |
| P0 | 固定涨跌幅异常规则 | `_run_stage_a`、交易规则模块 | 各板块参数化测试 | 合法涨跌停不等于脏数据 |
| P0 | 回测 T 日收益泄漏 | `equity_curve_from_holdings`、`BacktestEngine` | T/T+1 时序测试 | 信号从下一可成交时点生效 |
| P0 | 资格门禁语义不足 | `SignalEvidence`、聚合器、过滤器 | 必需/可选证据测试 | 缺必需证据不得正式推荐 |
| P0 | dry-run 状态混淆 | `DeepAnalyzer._dry_run`、`DeepAnalysisResult` | 状态枚举测试 | 三类执行结果可区分 |
| P1 | 股票池缓存过期 | `load_universe_cache` | 缓存日期/签名测试 | 过期缓存重建或降级 |
| P1 | 数据访问状态分裂 | `ScreenerEngine.run` | 单实例注入测试 | 健康、缓存、请求统计一致 |
| P1 | 回测能力不足 | `tradingagents/backtest` | 成交/成本/样本外测试 | 形成可信技术策略评价 |
| P2 | 全市场扫描 | Universe、批量行情适配器 | 规模和性能测试 | 不依赖逐股 N+1 请求 |

## 十、最终验收标准

Screener 至少满足以下条件后，才可以称为“完成第一版”：

- 能明确说明扫描范围，而不是把指数成分股称作全市场；
- 每个候选都能追溯到目标交易日、数据来源和最后有效日期；
- 旧数据、缺失数据和降级数据不会静默变成正式推荐；
- FULL 等生产模式不会绕过盘中和收盘后不稳定窗口；
- Stage A/Stage B 输入预算真实生效，Stage B 不按供应商原始顺序选取前 N 只；
- 合法涨跌停、ST、创业板/科创板和北交所规则不会被固定 9.9% 阈值误判；
- 供应商健康状态出现在 JSON 和 Markdown 产物中；
- Engine 级集成测试覆盖正常、部分失败、全部失败和无候选场景；
- DeepAnalyzer 的真实成功与 dry-run 状态严格区分；
- 现有 `tradingagents/backtest` 已修复 T/T+1 执行时序，并有至少一个固定基准和一组样本外结果；
- 回测明确处理交易成本、停牌、涨跌停、前视偏差和股票池偏差；
- 真实运行至少连续记录多个交易日，而不是只验证一次命令能够执行；
- 报告使用“候选发现”或“研究辅助”措辞，直到策略有效性得到量化验证。

## 十一、Codex 个人实施计划

> **执行约束：**实施时使用 `executing-plans` 逐批推进；每个业务符号修改前先执行 GitNexus upstream impact，每批结束运行针对性测试和受影响回归，全部完成后再运行全量测试及真实数据验收。

### 11.1 实施目标

我的目标不是一次性重写 Screener，而是在保持现有 CLI、策略和报告可运行的前提下，依次完成以下闭环：

```text
执行顺序正确
  → 数据日期可信
  → 证据资格可计算
  → 降级状态不误导
  → 回测不存在明显收益泄漏
  → 离线测试通过
  → 小股票池真实运行
  → 扩大股票池连续验收
```

在这些条件达成前，不扩展新的策略评分维度，也不优先开发全市场并发扫描，避免把未经验证的逻辑放大。

### 11.2 工作方式和边界

- 当前工作区已有大量未提交修改，实施时只修改本计划明确列出的 Screener、backtest 和对应测试文件；
- 不使用 `git reset --hard`、`git checkout --` 等方式覆盖现有工作；
- 每个批次保持可独立测试和回退，不把重构、功能新增和数据源扩展塞进同一个改动；
- 新状态优先向后兼容现有 JSON 字段，旧字段需要废弃时先保留兼容读取并在报告标记版本；
- 不在测试中调用真实外部 API；真实 API 仅用于最后验收；
- 不把一次真实成功当作稳定性证明，连续运行结果必须保留 run_id、供应商健康状态和数据日期；
- 由于当前工作区较脏，是否创建提交由用户在实施前决定；未获得明确指令时只形成可审查修改，不自动提交。

### 11.3 预计修改文件

| 文件 | 责任 |
|---|---|
| `tradingagents/screener/engine.py` | Stage A/B 编排、输入预算、漏斗指标、数据访问实例注入 |
| `tradingagents/screener/runtime_guard.py` | 全模式运行窗口、交易日校验、空候选语义 |
| `cli/screener/run_impl.py` | 最近交易日、CLI 配置契约、输出标签 |
| `tradingagents/screener/models.py` | 运行状态、聚合 freshness、证据资格、深度分析状态 |
| `tradingagents/screener/universe.py` | 股票池缓存版本、日期和失效策略 |
| `tradingagents/screener/merger/aggregation.py` | 聚合证据、验证模块和 freshness |
| `tradingagents/screener/merger/filters.py` | recommendation 模式资格门禁 |
| `tradingagents/screener/deep_analyzer.py` | 真实完成、主动 dry-run、失败回退状态 |
| `tradingagents/screener/report.py` | 状态、健康、数据日期和资格结果展示 |
| `tradingagents/backtest/engine.py` | 信号时间与成交时间建模 |
| `tradingagents/backtest/performance.py` | T+1 生效、成本和无法成交处理 |
| `tradingagents/backtest/report.py` | 执行假设、偏差和评价结果披露 |
| `tests/test_screener_engine.py` | 新增 Engine 端到端 fake-provider 测试 |
| `tests/test_screener_universe.py` | 新增股票池缓存和交易日测试 |
| `tests/test_screener_eligibility.py` | 新增证据资格和 freshness 测试 |
| `tests/test_screener_deep_analyzer.py` | 新增深度分析状态测试 |
| `tests/test_backtest.py` | 扩展 T/T+1、成本和成交约束测试 |
| `tests/test_merger_golden.py` | 保留并扩展合并规则回归基线 |

实际修改前以 GitNexus impact 和当前代码为准；如果已有更合适的测试文件或 canonical helper，优先复用，不机械创建重复模块。

### 11.4 第 0 批：建立基线

#### 任务 0.1：记录当前状态

- [x] 执行 `git status --short`，记录现有修改，避免误把用户工作纳入本批；
- [x] 执行 `python -m pytest -q tests/test_backtest.py tests/test_merger_golden.py`；
- [x] 执行 Screener CLI `--help`，确认入口仍可加载；
- [x] 保存当前全量测试数量和耗时；
- [x] 检查 GitNexus 索引是否过期，过期时先重新 analyze。

预期结果：现有针对性测试保持通过；如果基线已经失败，先定位既有失败，不能把它归因于后续修改。

#### 任务 0.2：建立影响分析清单

- [x] 对 `ScreenerEngine.run`、`_run_stage_a`、`TimeValidator.validate`、`build_screening_universe`、`_merge_card_group`、`_should_drop_card`、`DeepAnalyzer._dry_run`、`BacktestEngine.run`、`equity_curve_from_holdings` 分别执行 upstream impact；
- [x] 记录直接调用者、受影响流程和风险等级；
- [x] HIGH/CRITICAL 符号拆分为独立批次，修改前先向用户报告影响范围。

#### 第 0 批执行记录（2026-08-24）

| 项目 | 结果 |
|---|---|
| 当前分支 | `feat/phase2-agent-quality`，不是 main/master |
| 工作区 | 已有大量用户修改；第 0 批未修改业务代码 |
| 针对性测试 | `28 passed in 2.29s` |
| 全量离线测试 | `586 passed, 1 warning in 41.54s` |
| CLI | `python -m tradingagents screener run --help` 正常，默认模式为 FULL |
| GitNexus 索引 | 288 files、4569 symbols、300 processes；未提示 stale |
| 唯一警告 | `py_mini_racer` 间接使用已弃用的 `pkg_resources` |

影响分析结果：

| 目标 | 全深度风险 | 直接调用者/关键流程 | 后续处理 |
|---|---|---|---|
| `ScreenerEngine.run` | **HIGH** | `cli/screener/run_impl.py::run_screener`，影响 CLI/main menu 流程 | Engine 改动拆分，小步验证 CLI |
| `ScreenerEngine._run_stage_a` | **HIGH** | `ScreenerEngine.run` | 返回契约变化前先补 Engine 测试 |
| `TimeValidator.validate` | LOW | 索引未识别直接上游；实际由 `validate_screener_run` 包装调用 | 同时测试包装函数和 CLI |
| `build_screening_universe` | **HIGH** | `ScreenerEngine.run` | 缓存/注入修改独立成批 |
| `_merge_card_group` | LOW | `merge_signal_cards` | 由 merger golden tests 保护 |
| `_should_drop_card` | LOW | `merge_signal_cards` | 资格门禁修改独立测试 |
| `DeepAnalyzer._dry_run` | LOW | `DeepAnalyzer.analyze` | 状态模型保持 JSON 兼容 |
| `BacktestEngine.run` | LOW | backtest CLI、sensitivity runner、测试 | 与绩效函数分开修改 |
| `equity_curve_from_holdings` | **HIGH** | `BacktestEngine.run` 及 3 个直接单元测试 | T/T+1 修复单独一批并更新基线 |

第 1 批开始前的明确警告：`ScreenerEngine.run`、`_run_stage_a`、`build_screening_universe` 和 `equity_curve_from_holdings` 的全深度影响为 HIGH。不得在一个大改动中同时修改这些高风险符号；必须按任务拆分、测试先行，并在每个子任务结束后复核调用链。

### 11.5 第 1 批：修复执行正确性

#### 任务 1.1：让 Stage A 输入预算真实生效

**测试先行：**在 `tests/test_screener_engine.py` 增加 fake universe 150 只、`stagea_max_input=100` 的测试，记录 fake data access 的 `fetch_hist` 调用数。

- [ ] 先写断言：Stage A 只请求 100 只，漏斗记录原始 150、预算 100、实际 100；
- [ ] 运行该测试，确认当前实现失败；
- [ ] 在 Engine 去重后、网络请求前统一应用预算；
- [ ] 参数化验证 MVP、FULL、FOCUSED、CUSTOM；
- [ ] 运行新增测试和 Screener 相关回归。

验收：CLI 参数不再只是展示值，实际请求数与预算一致。

#### 任务 1.2：替换 Stage B 原始顺序切片

**设计：**让 Stage A 返回 `StageACandidate`，至少包含 ticker、数据完整性、流动性、基础动量、异常标签和 `stage_a_score`。

- [ ] 写两个相同股票集合、不同原始顺序的测试；
- [ ] 断言两次 Stage B 入选集合一致；
- [ ] 运行测试，确认当前切片行为失败；
- [ ] 实现稳定排序，明确同分时使用标准化 ticker 作为次级键；
- [ ] 在 metrics 中写入截断前后数量、最低入选分和截断原因；
- [ ] 验证 `stageb_max_input=0/1/大于候选数` 边界。

验收：Stage B 选择不依赖供应商或指数接口返回顺序。

#### 任务 1.3：修复运行窗口和交易日

- [ ] 写 FULL/MVP/EXTENDED/FOCUSED/CUSTOM/EXPERIMENTAL 参数化时间测试；
- [ ] 断言生产模式盘中和收盘后未稳定窗口被拒绝；
- [ ] 为交易日历定义可注入接口，测试法定节假日和本地日历过期；
- [ ] 修改 `_get_last_trading_day()` 使用交易日历，不再只按 weekday；
- [ ] 保留历史日期研究运行，但必须记录历史模式和数据日期告警；
- [ ] 运行 runtime guard 与 CLI 测试。

验收：默认 FULL 不再绕过生产保护；节假日不会被当成交易日。

#### 任务 1.4：修复固定涨跌幅异常规则

- [ ] 为主板、ST、创业板/科创板、北交所和新股样例写参数化测试；
- [ ] 复用现有交易规则模块解析限制，不在 Engine 重复编码；
- [ ] 将合法涨跌停记录为 market state/risk flag；
- [ ] 只把不可能值、字段错位和价格断层归为数据异常；
- [ ] 验证强势合法涨停不会被 Stage A 无条件删除。

### 11.6 第 2 批：数据新鲜度和证据资格

#### 任务 2.1：统一 freshness 聚合

- [ ] 为 `DataFreshness` 写 fresh/stale/missing/estimated 聚合测试；
- [ ] 保持每条 `SignalEvidence.freshness` 为来源级唯一事实；
- [ ] 在聚合器生成 `latest_required_data_date`、`max_required_data_lag_days`、`stale_required_sources`；
- [ ] 不在 `SignalCard` 创建第二套可独立写入的来源日期；
- [ ] 报告显示候选最旧关键数据和最大滞后。

验收：目标日期、实际数据日期和拉取时间三者可区分。

#### 任务 2.2：建立必需/可选证据模型

- [ ] 为三个策略分别列出 required 和 optional 模块；
- [ ] 写测试证明缺少必需证据会阻断 recommendation；
- [ ] 写测试证明可选证据降级不会错误否决其他完整策略；
- [ ] 增加 `verified_modules`、`missing_required_modules`、`degraded_modules` 和 `verified_strategy_count`；
- [ ] 在 research/recommendation 模式下产生不同但可解释的结果。

验收：不再依赖含义不一致的单一 `data_source_verified` 做全部决策；旧字段只作为兼容摘要。

#### 任务 2.3：修正空候选语义

- [ ] 测试正常过滤后零候选返回 `NO_CANDIDATE_VALID`；
- [ ] 测试关键数据降级导致零候选返回 `NO_CANDIDATE_DEGRADED`；
- [ ] 测试关键阶段异常返回 `PIPELINE_FAILED`；
- [ ] 只有 pipeline failed 进入 FATAL。

### 11.7 第 3 批：股票池、供应商和报告

#### 任务 3.1：修复股票池缓存契约

- [ ] 为缓存增加 schema/version、trade_date/as_of、source_signature、built_at/expires_at；
- [ ] 测试日期变化、配置变化、缓存过期和损坏 JSON；
- [ ] 正常缓存、降级缓存和不可用缓存使用不同状态；
- [ ] 过期缓存不得静默冒充当日股票池。

#### 任务 3.2：统一数据访问实例

- [ ] 写测试断言 Engine 构建的同一个 `ScreenerDataAccess` 被传给 universe 和策略；
- [ ] 修改 `build_screening_universe(..., data_access=data_access)` 调用；
- [ ] 验证健康状态、请求统计、缓存命中率和熔断状态属于同一 run；
- [ ] 不读取或输出 `.env` 中的密钥值。

#### 任务 3.3：完善供应商健康产物

- [ ] 在 Markdown 摘要展示 calls、failures、failure_rate、avg_seconds、last_status；
- [ ] 如实现 P95，使用有界样本或 histogram，不无限保存调用明细；
- [ ] 独立写入 `vendor_health.json`，并在主报告记录路径；
- [ ] 验证错误文本经过密钥脱敏。

### 11.8 第 4 批：DeepAnalyzer 状态和配置

#### 任务 4.1：增加明确状态枚举

- [ ] 测试 `GRAPH_COMPLETED`；
- [ ] 测试用户主动关闭得到 `DRY_RUN_REQUESTED`；
- [ ] 测试图执行异常得到 `FALLBACK_COMPLETED`；
- [ ] 测试无法形成任何可消费结果得到 `FAILED`；
- [ ] CLI、JSON 和 Markdown 使用同一状态语义。

#### 任务 4.2：统一配置层级

- [ ] 以 `deep_analyzer.enable_real_deep_analysis` 为 canonical 配置；
- [ ] 为旧顶层字段提供显式兼容读取和弃用提示；
- [ ] 验证 CLI `--no-deep` 完全跳过阶段；
- [ ] 验证环境变量优先级低于显式配置。

### 11.9 第 5 批：升级现有回测

#### 任务 5.1：先修复 T/T+1 收益泄漏

- [ ] 构造三天价格：T 日出现大涨并产生信号，T+1 才允许持仓；
- [ ] 断言策略净值不包含 T 日已经发生的涨幅；
- [ ] 运行测试，确认当前实现失败；
- [ ] 引入 signal date 与 effective date 的明确映射；
- [ ] 从下一可成交时点开始应用新持仓收益；
- [ ] 保持旧回测结果格式兼容或提高 artifact schema version。

验收：任何使用 T 日收盘数据的信号都不能获得 T 日收益。

#### 任务 5.2：增加执行成本和成交约束

- [ ] 增加 commission、stamp duty、slippage 配置；
- [ ] 测试买入、卖出和换仓成本；
- [ ] 测试停牌、涨停买不进、跌停卖不出；
- [ ] 报告列出实际成交、未成交和延迟成交数量；
- [ ] 将 turnover 纳入绩效指标。

#### 任务 5.3：增加 point-in-time 约束和样本外验证

- [ ] 回测 artifact 固定 config version、threshold snapshot、数据源和股票池 as_of；
- [ ] 当前成分股回测继续显著标记 survivorship bias；
- [ ] 有历史成分股数据后切换为 point-in-time universe；
- [ ] 划分训练、验证、测试窗口，阈值只能在验证集选择；
- [ ] 在历史快照不足前，不伪造 Policy/SmartMoney 全历史回测。

### 11.10 第 6 批：综合验证

#### 任务 6.1：离线质量门

- [ ] 运行新增 Screener 测试；
- [ ] 运行 `tests/test_backtest.py` 和 `tests/test_merger_golden.py`；
- [ ] 运行所有受 GitNexus detect_changes 影响的测试；
- [ ] 运行全量 `pytest -q`；
- [ ] 运行 `python -m compileall -q tradingagents cli tests`；
- [ ] 运行 `git diff --check`；
- [ ] 运行 GitNexus `detect_changes(scope="compare", base_ref="main")`，确认影响范围与计划一致。

#### 任务 6.2：真实运行阶梯

真实 API 验收按以下顺序扩大，不直接从 FULL 开始：

1. CUSTOM 3 只股票，`--no-deep`；
2. CUSTOM 3 只股票，启用 Agnes 深度分析 1 只；
3. FOCUSED 单指数或单概念；
4. MVP；
5. FULL，仅在前四级健康状态和时间预算达标后运行。

每一级检查：

- 实际数据日期是否等于目标交易日；
- recommendation eligibility 是否与证据状态一致；
- vendor health 是否记录成功率、延迟、降级路径；
- dry-run/fallback 是否没有伪装成 graph completed；
- Stage A/B 漏斗数量是否可解释；
- 输出中是否包含密钥或未脱敏错误。

#### 任务 6.3：连续运行验收

- [ ] 至少连续记录 5 个交易日；
- [ ] 每日保留 run_id、配置快照、股票池 as_of、供应商健康和候选资格；
- [ ] 汇总供应商成功率、空数据率、候选稳定性、运行耗时和降级次数；
- [ ] 任何一天出现旧数据正式推荐、状态误报或报告缺失，即视为验收失败并回到对应批次修复。

### 11.11 每批完成定义

每个批次必须同时满足以下条件才算完成：

- [ ] 修改前已完成目标符号影响分析；
- [ ] 新测试能够在旧实现上暴露问题；
- [ ] 最小实现使新测试通过；
- [ ] 相关旧测试没有回归；
- [ ] 报告、配置和输出契约同步更新；
- [ ] 没有把外部 API 失败静默吞成成功；
- [ ] 没有泄露 `.env` 或日志中的密钥；
- [ ] 变更范围经 GitNexus detect_changes 复核；
- [ ] 向用户报告已完成项、未完成项和下一批风险。

### 11.12 停止和升级条件

遇到以下情况，我会停止扩大修改范围并先报告：

- GitNexus impact 返回 HIGH/CRITICAL，且需要跨越 Screener 边界修改主分析链；
- 现有用户修改与目标文件发生无法安全合并的冲突；
- 真实数据源连续失败，无法区分代码问题和供应商问题；
- 需要新增付费数据源、扩大 API 权限或改变用户既定的 Tushare 禁用策略；
- 回测需要历史 point-in-time 数据但仓库和现有供应商都无法提供；
- 方案会改变 CLI 公共参数、JSON schema 或报告含义，且无法保持兼容。

在这些情况下，我不会用静默 fallback 掩盖问题，而会给出具体阻塞证据和可选方案。

### 11.13 第 1 批实施记录（2026-08-24）

本批已完成“执行正确性”四项修复：

- [x] `stagea_max_input` 在统一引擎入口生效：先按来源顺序去重，再执行预算截断；审计新增原始股票池数、去重数、预算、实际输入数和预算截断数；
- [x] Stage B 不再按供应商原始顺序截断：Stage A 为通过项生成数据完整度、流动性、基础动量及综合分，按“综合分降序 + 股票代码升序”稳定选择；审计新增 Stage B 预算、实际输入、选择依据和选中分数范围；
- [x] 生产运行时间保护覆盖 `MVP/EXTENDED/FULL/FOCUSED/CUSTOM` 等所有非 `EXPERIMENTAL` 模式；历史日期不再绕过非交易日检查；CLI 最近交易日改由缓存 A 股交易日历解析；
- [x] 固定 ±9.9% 异常规则替换为主板 10%、创业/科创 20%、北交所 30%、ST 5% 和上市前 5 日不限价规则；合法触及涨跌停不再被误判，只有超过法定边界与容差才属于异常数据；
- [x] 新增 9 项直接回归测试；相关专项测试 29 项通过；全量离线测试 `596 passed, 1 warning`；
- [x] GitNexus 变更审计结果为 HIGH：主要来自本报告事先声明的 `ScreenerEngine.run/_run_stage_a` 高风险漏斗主链；受影响流程集中在 Screener 运行链及复用 exchange rules 的 Trader/Portfolio Manager 提示链，全量回归未发现行为回退。

已知降级边界：A 股交易日历优先使用本地缓存，首次缓存缺失时通过 AkShare 获取；供应商不可用时退化到工作日规则，并在日历对象上保留 `source=weekday_fallback` 与 `degraded=True`。后续批次应把该健康状态写入最终运行 artifact，而不只保留在日历组件内部。

### 11.14 第 2 批实施记录（2026-08-24）

本批已完成“数据新鲜度、证据资格与空候选状态”闭环：

- [x] 新增来源级证据资格聚合，`SignalEvidence.freshness` 继续作为唯一来源日期事实；合并卡只保存派生摘要，不创建可独立写入的第二套来源日期；
- [x] 三策略证据契约明确化：Technical 必需 `hist_fetch/fund_flow`；Policy 必需 `concept_list`、News 可选；Smart Money 必需 `hist_fetch`，资金流、逐笔、估值和龙虎榜为可选增强；
- [x] 候选新增 `verified_modules`、`missing_required_modules`、`degraded_modules`、`verified_strategy_count`、`recommendation_eligible`；旧 `data_source_verified` 仅保留为兼容摘要；
- [x] 新鲜度派生新增关键数据最旧日期、最大滞后天数和过期关键来源；Markdown 与 CLI JSON 均展示这些字段；
- [x] 默认 `research` 模式允许保留研究候选但不会伪装成正式推荐；显式 `recommendation` 模式会阻断缺失或过期必需证据的候选；可选模块降级不会否决已有完整主路径；
- [x] 空候选细分为 `NO_CANDIDATE_VALID`、`NO_CANDIDATE_DEGRADED` 和 `PIPELINE_FAILED`，只有最后一种产生 FATAL；状态在 `ScreeningResult` 构造时即完成推导，确保 artifact 写入前已经正确；
- [x] 新增 7 项直接测试，专项及黄金回归 `25 passed`，全量离线测试 `605 passed, 1 warning`。

严格边界：当前策略尚未普遍提供按股票、按目标交易日验证的 `freshness` 记录，因此真实运行生成的卡片可以作为 research 候选，但在补齐来源级日期前不会获得正式推荐资格。接口 probe 成功不能替代目标日期证据，本批没有用 probe 时间伪造业务数据日期。

### 11.15 第 3 批实施记录（2026-08-24）

本批已完成“股票池缓存、单一数据访问实例与供应商健康产物”闭环：

- [x] Universe 缓存升级为 schema v2，写入 `trade_date/as_of/source_signature/built_at/expires_at`；读取时校验 schema、目标日期、来源签名和 TTL；
- [x] 损坏 JSON、旧 schema、日期变化、配置来源变化和过期缓存全部失败关闭并触发重建，不再静默冒充当日股票池；
- [x] `build_screening_universe` 接收并传播目标交易日，标准模式与 FOCUSED 模式使用同一缓存契约；
- [x] Engine 创建的同一个 `ScreenerDataAccess` 现在同时注入 Universe、Stage A、三策略和 NameResolver，单次运行内共享缓存、健康统计、熔断和请求状态；
- [x] capability summary 在策略与名称解析完成后刷新，避免最终报告只记录启动 probe、遗漏真实业务调用；
- [x] Markdown 增加“供应商健康状态”，展示 calls、failures、failure_rate、avg_seconds、last_status 和脱敏后的 last_error；
- [x] 每次运行独立生成 `vendor_health.json`，并在 artifact 路径映射中登记；主 `screening_result.json` 和 Markdown 同样执行防御性错误脱敏；
- [x] 新增 6 项直接契约测试；缓存、健康和 DataAccess 相关回归 `58 passed`；全量离线测试 `611 passed, 1 warning`。

严格边界：Universe 缓存失效时不会回退到过期缓存；如果供应商无法重建股票池，标准模式仍会明确失败并提示使用 CUSTOM，而不是把旧股票池标成当日有效。供应商健康统计是单次 run 的运行事实，不代表长期 SLA，长期稳定性仍需第 6 批连续多交易日验收。

## 十二、结论

Screener 当前最值得保留的是工程结构和可审计性，最需要补强的是数据可信度门禁与策略有效性验证。继续增加更多评分规则或更多 LLM 分析，并不能替代这两项工作。

建议先完成 P0 的执行正确性：Stage B 选择、输入预算、生产时间守卫、交易日历、涨跌停规则和回测 T/T+1 时序；随后完成“数据不可信就不能推荐”的结构化资格闭环，再升级现有回测。全市场扩展放在这些基础稳定之后。这样既能降低真实运行风险，也能让项目在面试中从“功能很多的 Demo”提升为“知道如何控制数据、执行时序、状态和验证边界的工程系统”。
