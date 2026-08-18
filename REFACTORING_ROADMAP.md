# TradingAgents-CN-improving 重构路线图

> 目标：在不推倒核心业务、不一次性重写的前提下，把当前迁移中间态收口为可测试、可发布、可扩展的 A 股研究与决策编排平台。  
> 原则：先建立行为护栏，再收口入口和契约，再改变依赖方向，最后拆巨型实现。  
> 配套体检：[`PROJECT_ARCHITECTURE_REVIEW.md`](PROJECT_ARCHITECTURE_REVIEW.md)

## 一、重构的北极星

重构完成后的系统应满足：

```text
CLI / Python API / future HTTP API
                │
                ▼
      Application Services
      ├─ ScreeningService
      └─ AnalysisService
                │
     ┌──────────┴──────────┐
     ▼                     ▼
 Domain                  Ports
 Screening              MarketDataPort
 Analysis               ModelPort
 Signal/Merger          MemoryPort
 Run/Artifact           ArtifactPort
     │                     │
     └──────────┬──────────┘
                ▼
             Adapters
  Tencent / AkShare / Yahoo / AlphaVantage
  OpenAI / Anthropic / Google / Azure
  JSON / filesystem / Rich terminal
```

依赖只能向内：

```text
adapters → application → domain
```

禁止：

```text
dataflows → screener
UI → LangGraph internal state
provider adapter → domain decision rules
compatibility shim → old full implementation
```

## 二、目标代码结构

这是方向，不要求第一天一次搬完：

```text
tradingagents/
├─ application/
│  ├─ analysis_service.py
│  ├─ screening_service.py
│  ├─ contracts.py
│  └─ events.py
├─ domain/
│  ├─ analysis/
│  │  ├─ state.py
│  │  ├─ result.py
│  │  ├─ routing.py
│  │  └─ prompts/
│  ├─ screening/
│  │  ├─ models.py
│  │  ├─ strategies/
│  │  ├─ merger/
│  │  └─ universe.py
│  └─ shared/
│     ├─ errors.py
│     └─ identifiers.py
├─ ports/
│  ├─ market_data.py
│  ├─ model.py
│  ├─ memory.py
│  ├─ artifact.py
│  └─ telemetry.py
├─ adapters/
│  ├─ market_data/
│  │  ├─ registry.py
│  │  ├─ tencent.py
│  │  ├─ akshare.py
│  │  ├─ yfinance.py
│  │  └─ capability_probe.py
│  ├─ models/
│  │  ├─ openai.py
│  │  ├─ anthropic.py
│  │  ├─ google.py
│  │  └─ azure.py
│  ├─ memory/
│  ├─ artifacts/
│  └─ telemetry/
├─ graph/
│  ├─ runtime.py
│  ├─ analyst_subgraph.py
│  ├─ research_subgraph.py
│  ├─ trading_subgraph.py
│  ├─ risk_subgraph.py
│  └─ portfolio_subgraph.py
├─ cli/
│  ├─ app.py
│  ├─ analyze.py
│  ├─ screener.py
│  └─ report.py
└─ compatibility/
   ├─ legacy_analyze.py
   └─ legacy_screener.py
```

不建议现在先大规模移动文件。应先在现有路径中建立 `contracts` / `ports`，让依赖方向改变后再移动，避免产生只改路径、不减复杂度的大型 PR。

---

## 三、执行原则

### 1. 不做大爆炸重写

每一步都应保留可运行主链，并可比较重构前后的输出。任何 PR 最好只改变一个边界。

### 2. Characterization tests 先于清理

第一批测试不是证明代码“正确”，而是冻结当前可接受行为：同一输入、固定 fixture、相同配置应得到相同的标准化结果、筛选顺序或状态迁移。

### 3. 兼容层必须是薄转发

允许旧 import path 暂时存在，但最多做：

```python
from new_location import public_api

__all__ = ["public_api"]
```

禁止复制实现、捕获宽泛异常后切换完整旧引擎、在 import 时执行 CLI。

### 4. 先端口，后拆文件

拆 `ScreenerDataAccess` 前，先定义 `MarketDataPort`；拆 `run_analysis()` 前，先定义 `AnalysisRequest/Result/Event`。否则只会制造更多互相调用的小文件。

### 5. 每个迁移字段都要有删除日期

Legacy state 双写、旧 CLI 和旧配置键都应记录：

- canonical 版本；
- 兼容适配器；
- 不再写入的版本；
- 删除的版本。

---

## 四、Phase 0：止血与可发布基线（预计 3–5 个小 PR）

### 目标

不改变核心业务结果，先让仓库可导入、可测试、版本一致、边界可见。

### 工作包 0.1：建立最小 CI 与活跃测试目录

新增：

```text
tests/
├─ unit/
├─ characterization/
├─ contract/
└─ smoke/
```

第一批必须有：

1. `import tradingagents` 不产生输出、不退出；
2. `import cli.main` 不退出进程；
3. `python -m tradingagents --version` 与 package metadata 相同；
4. `create_llm_client()` 的 provider 分发测试（mock SDK，不发网络）；
5. `SignalCard` 合并 fixture 测试；
6. `ScreenerEngine` dry-run 主链测试；
7. `TradingAgentsGraph` 初始状态 schema 测试；
8. 所有有效 Python 文件编译测试。

CI 最少运行：

```text
ruff check
pytest -q
python -m build
```

可暂不追求覆盖率阈值；先要求所有未来 Bug 修复都附回归测试。

### 工作包 0.2：单一版本源

建议让 `pyproject.toml` 或 `importlib.metadata.version("tradingagents")` 成为唯一来源，删除手写 `2.0.0` 常量漂移。

验收：

- README、CLI、包元数据和 `--version` 完全一致；
- 项目规范仓库身份（GitHub owner/repository）只有一个，README clone 链接、本地 `origin`、徽章和发布元数据与之对应；
- CI 中加入版本一致性测试。

### 工作包 0.3：清理 import 副作用

把 `cli/main.py` 改为只有 `main()`，并仅在：

```python
if __name__ == "__main__":
    main()
```

中运行。依赖错误通过异常或退出码在真正调用时返回，不在 import 时 `sys.exit()`。

### 工作包 0.4：固化有效/垃圾边界

你已经用 `-no` 做人工排除，这是有效止血，但应转成正式治理：

- 决定 `*-no` 是删除、移出仓库，还是进入 `archive/`；
- 在 `.gitignore` 中排除报告、缓存、临时输出；
- 禁止 `build/`、`*.egg-info/`、临时 commit message 进入提交；
- 文档只保留 `README.md`、架构文档、贡献指南和少量 ADR；
- 调试脚本若有长期价值，转成测试或 `scripts/diagnostics/`。

本阶段不要读取或迁移 `-no` 内容，先定义政策，由你之后人工决定是否删除。

### Phase 0 完成标准

- 基础导入无副作用；
- 一个版本号；
- wheel/sdist 可构建；
- 至少 15–25 个快速离线测试；
- CI 不访问真实金融网站或 LLM；
- 新 PR 不再增加重复入口。

---

## 五、Phase 1：收口单一入口与运行契约（预计 4–6 个 PR）

### 工作包 1.1：定义类型化用例契约

建议使用 Pydantic 或 dataclass，但只选一种：

```text
AnalysisRequest
AnalysisOptions
AnalysisResult
ScreeningRequest
ScreeningResult
ReportArtifact
RunWarning
ProviderSettings
```

`AnalysisRequest` 至少包含：

- ticker；
- trade_date；
- selected analysts；
- research depth；
- model profile；
- output language；
- optional screener context。

`AnalysisResult` 至少包含：

- final decision；
- optional confidence（未实现时是 `None`，不伪造 0）；
- analyst reports；
- debate summaries；
- route summary；
- artifacts；
- warnings/errors；
- usage snapshot。

### 工作包 1.2：建立 `AnalysisService`

从 `cli/analyze/run_impl.py` 中抽出与 Rich UI 无关的 application service：

```python
result = analysis_service.run(request, event_sink=...)
```

CLI 只负责：

```text
输入 → request
事件 → Dashboard
result → summary
```

Python API 可直接调用同一 service。

### 工作包 1.3：建立稳定执行事件

不要让 UI 读取 LangGraph chunk。由 runtime 将内部状态转成：

```text
AnalysisStarted
PhaseChanged
NodeStarted
ToolCalled
ToolCompleted
ReportUpdated
DebateUpdated
UsageUpdated
ArtifactWritten
AnalysisCompleted
AnalysisFailed
```

事件可以先用 dataclass + callback，不必引入消息队列。

### 工作包 1.4：旧 Analyzer 变薄 shim

迁移顺序：

1. 新旧入口都调用 `AnalysisService`；
2. characterization tests 证明结果一致；
3. 删除旧 `run_analysis()` 实现；
4. 保留旧 import path 一个发布周期并发 DeprecationWarning；
5. 删除宽泛 fallback。

### 工作包 1.5：统一 ticker/date 初始化时序

Graph 所需的 ticker、date、instrument profile、历史记忆和工具配置必须来自同一个 `AnalysisRequest`，在 Graph 构造前确定。

当前新 CLI 在状态创建时才注入 ticker，但 Graph 初始化已可能读取 `company_of_interest`。应让 Graph runtime 接受明确 request，而不是从全局 config 猜测。

### Phase 1 完成标准

- 一个 `AnalysisService`；
- CLI 和 Python API 共享它；
- 旧路径只有转发；
- UI 不再读取裸 Graph state；
- `--ticker/--date/--no-interactive` 真正工作；
- 一个 `AnalysisResult` 贯穿 summary 和 report。

---

## 六、Phase 2：建立 Canonical State 与阶段子图（预计 5–8 个 PR）

### 工作包 2.1：定义状态版本

保留结构化字段作为 canonical：

```text
ticker_info
analyst_reports
debate_blocks
decision_blocks
execution_control
route_decision
telemetry
messages
```

短期 legacy adapter 可以读取旧字段，但业务节点停止双写旧字段。

建议增加：

```python
schema_version: Literal[2]
```

### 工作包 2.2：拆分 `orchestration`

当前 `orchestration` 同时承载控制、路由、压缩、事件和置信度。拆成：

```text
ExecutionControl
RouteDecision
CompressionTelemetry
ExecutionTrace
```

不要把观察数据反写成业务决策字段。

### 工作包 2.3：阶段子图

按现有清晰阶段拆：

```text
AnalystSubgraph
ResearchSubgraph
TradingSubgraph
RiskSubgraph
PortfolioSubgraph
```

根 Graph 只连接阶段。每个子图具有独立输入/输出 contract 和测试 fixture。

### 工作包 2.4：PromptContext 边界

节点不再直接从大状态字典拼几十个字段。每个角色通过：

```text
ContextRenderer
RolePrompt
ToolPolicy
OutputContract
```

生成请求。

Skill 注入、Screener semantic context、memory context 和 output language 都进入 typed `PromptContext`。

### 工作包 2.5：反思与记忆生命周期

区分：

1. run 内临时记忆；
2. 分析完成摘要；
3. 有真实 outcome 后的归因反思；
4. 跨 run 的 ticker 历史结论。

不要在没有收益结果时把“生成摘要”命名为“反思有效性”。

拆分：

```text
MemoryStore
MemoryRetriever
ReflectionService
RouteAnalytics
ConclusionRepository
```

保留本地 BM25 实现作为 adapter。

### Phase 2 完成标准

- canonical state 只有一套写路径；
- legacy adapter 有删除版本；
- 每个阶段子图可独立测试；
- UI 和报告只依赖事件/result；
- `Reflector` 和 `StructuredMemory` 不再是千行多职责类。

---

## 七、Phase 3：纠正数据层依赖方向（预计 6–10 个 PR）

这是最难也最关键的阶段。不要与 Phase 1 同时大改。

### 工作包 3.1：定义 `MarketDataPort`

按能力而不是网站组织接口：

```text
get_price_history
get_spot_snapshot
get_index_constituents
get_concept_boards
get_concept_constituents
get_fund_flow
get_policy_news
get_tick_data
get_valuation
```

返回统一领域 DTO，不返回供应商原始 DataFrame 列名。

### 工作包 3.2：供应商 adapter

每个 adapter 只负责：

- 请求；
- 响应解析；
- 字段标准化；
- 将供应商异常转为 typed error。

例如：

```text
TencentPriceAdapter
AkShareMarketAdapter
YFinanceAdapter
THSConceptAdapter
BaiduNewsAdapter
```

### 工作包 3.3：Fallback policy 独立化

供应商优先级、重试、节流和降级不应散落在 adapter 和 Screener 中。

```text
VendorRegistry
CapabilityMatrix
FallbackPolicy
RetryPolicy
RateLimiter
```

`ScreenerDataAccess` 最终变成薄的 screening query service，或直接被 `MarketDataPort` 替代。

### 工作包 3.4：探测和缓存外移

拆出：

```text
CapabilityProbeService
ProbeCache
MarketDataCache
```

运行 Screener 不应无条件把 live probe、文件写入和业务筛选揉在同一调用里。Probe 应可通过配置运行、复用或禁用，并产生显式事件。

### 工作包 3.5：消除反向依赖和依赖环

最终必须满足：

- `dataflows` 不导入 `tradingagents.screener`；
- `cn_indicators` 依赖 `MarketDataPort`；
- 新闻/RAG 工具通过端口读取数据，不回调 `dataflows.interface` 的大路由器；
- 模块依赖扫描不再出现当前四模块环。

### 工作包 3.6：供应商 contract tests

保存脱敏的响应 fixture，测试：

- schema 变化；
- 空数据；
- 限速；
- 代码格式转换；
- 日期/时区；
- 单位和复权；
- 降级顺序。

测试默认离线；真实网络探测进入手动/定时 integration job。

### Phase 3 完成标准

- 通用数据层不依赖 Screener；
- 每个供应商 adapter 独立 contract test；
- 预期失败类型化；
- `ScreenerDataAccess` 不再超过约 300–500 行，且只承担一个变化原因；
- 依赖环为 0；
- 同一行情请求在 Screener 和 Analyzer 使用同一标准化契约。

---

## 八、Phase 4：把 Screener 规则变成可测试管道（预计 5–8 个 PR）

### 工作包 4.1：拆 Merger 阶段

建议纯函数管道：

```text
normalize_cards
  → aggregate_strategy_scores
  → evaluate_conflicts
  → apply_hard_filters
  → apply_semantic_policy
  → diversify_by_sector
  → rank_candidates
  → build_decision_explanations
```

每阶段输入/输出不可变，避免在多个 helper 中重复计算 conflict 和 semantic context。

### 工作包 4.2：规则配置化，但不过度 DSL 化

适合配置：阈值、权重、行业上限、开关。

不适合立即配置：复杂业务判断树。先用命名纯函数表达，不要创建通用规则引擎。

### 工作包 4.3：策略协议

```python
class ScreeningStrategy(Protocol):
    name: str
    required_capabilities: set[MarketDataCapability]
    def evaluate(context: ScreeningContext) -> StrategyOutcome: ...
```

Engine 只发现策略、并发/串行执行并收集 outcome。

### 工作包 4.4：Golden fixtures

建立 10–20 组候选卡片 fixture，冻结：

- 冲突规则；
- hard drop reason；
- 行业分散；
- policy focus；
- score ordering；
- explanation payload。

### Phase 4 完成标准

- `merger.py` 主入口可在一屏内读懂；
- 规则阶段分别可测；
- 策略新增不改 Engine；
- 所有 drop 都有结构化 reason code；
- 报告文案不参与决定是否丢弃候选。

---

## 九、Phase 5：模型能力层、可观测性与报告治理（预计 4–7 个 PR）

### 工作包 5.1：内部 `ModelPort`

不要永久把所有 provider 返回压成字符串。定义：

```text
ModelRequest
ModelResponse
TextBlock
ThinkingBlock
ToolCallBlock
Usage
StopReason
ModelCapabilities
```

Provider adapter 可以继续使用 LangChain，但必须保留 typed semantics。

### 工作包 5.2：能力矩阵

模型选择不只验证字符串，应表达：

- tool calling；
- structured output；
- reasoning/thinking；
- streaming；
- context/output limits；
- usage/caching metadata。

CLI 根据能力展示选项，业务层不直接判断 provider 名称。

### 工作包 5.3：Observability

将 `CostTracker` 扩展为 run-level telemetry：

```text
run_id
provider/model
node/phase
latency
input/output/cache tokens
tool calls
retry/fallback
error category
artifact paths
```

价格属于带版本的可选计算器，原始 token/usage 才是事实。

### 工作包 5.4：统一 Artifact 模型

`ReportArtifact` 统一 Markdown、JSON、日志和未来 HTML。一个输出根目录、一套命名、一份 manifest。

HTML 未实现时，命令应明确显示“不支持”，不能保留看似完成的入口。当前 TODO 位于 `tradingagents/ui/summary.py:254`。

### Phase 5 完成标准

- provider 特性不泄漏到业务层；
- typed content 不被无条件压平；
- 每次 run 可追踪模型、token、阶段、工具和工件；
- 报告 viewer 只读取 artifact manifest；
- README 的能力声明由测试或 capability matrix 支撑。

---

## 十、建议的 PR 切分顺序

不要创建一个“重构整个项目”的大分支。建议前 12 个 PR：

1. `test: add offline import and packaging smoke tests`
2. `chore: unify package version source`
3. `fix(cli): remove import-time execution from legacy entrypoint`
4. `test: characterize analyzer request and result behavior`
5. `refactor(analyzer): introduce typed AnalysisRequest and AnalysisResult`
6. `refactor(analyzer): extract AnalysisService without UI changes`
7. `refactor(ui): consume execution events instead of graph chunks`
8. `refactor(cli): make legacy analyzer a forwarding shim`
9. `test: add market-data adapter contract fixtures`
10. `refactor(data): introduce MarketDataPort and typed vendor errors`
11. `refactor(data): route CN indicators through MarketDataPort`
12. `refactor(data): remove dataflows-to-screener dependency`

之后再拆 `ScreenerDataAccess`、Merger、GraphSetup、Reflector。

---

## 十一、量化验收指标

不要用“文件都变小了”作为成功标准。建议追踪：

### 架构指标

- 活跃模块依赖环：`1 → 0`；
- 完全/近似重复的新旧 CLI 实现：逐步归零；
- UI 对 Graph state 字段的直接读取：归零；
- `dataflows` 对 `screener` 的导入：归零；
- canonical state 双写字段：归零。

### 复杂度指标

- 新增函数圈复杂度目标 `< 15`；
- 超过 30 的函数必须有拆分 issue 或明确理由；
- 千行多职责类逐步归零；
- 宽泛异常捕获只允许出现在边界 adapter，并有日志/错误分类。

### 测试指标

- 核心领域模块覆盖率先达到 70%，不强求全仓；
- Merger、状态迁移、vendor 标准化达到 85%+；
- 单元测试默认 30 秒内；
- 网络/LLM integration tests 与默认 CI 分离；
- 每个生产 Bug 都有回归测试。

### 发布指标

- 一个版本源；
- wheel/sdist 可安装；
- 所有 CLI 子命令可 `--help`；
- import 无输出、无网络、无退出；
- README 命令由 smoke test 验证。

### 产品指标

- 同一 request 可从 CLI 和 Python API 获得等价 `AnalysisResult`；
- 所有降级都有可见 warning，而不是静默吞错；
- 报告能指出数据来源、降级路径和模型配置；
- 未实现 confidence 时明确为 `N/A`，不伪造数值。

---

## 十二、明确禁止的重构方式

1. 不要一次性重写成微服务。
2. 不要为了“整洁”引入通用 DI 容器、事件总线或规则 DSL。
3. 不要先移动全部文件再修依赖。
4. 不要在没有 characterization tests 时删除旧路径。
5. 不要把所有供应商异常继续归为 `Exception`。
6. 不要把业务规则搬进 Prompt 来减少 Python 条件。
7. 不要用更多注释掩盖不清晰的边界。
8. 不要同时新增回测、实盘和 Web UI。
9. 不要把上游所有更新直接 merge 进当前重构分支；先建立 upstream sync 策略。
10. 不要让自动生成报告、缓存、debug artifact 进入源码包。

---

## 十三、未来 90 天建议

### 第 1–2 周

只做 Phase 0。目标是：导入健康、版本一致、测试目录、CI、构建成功。

### 第 3–5 周

完成 Phase 1：`AnalysisService`、typed request/result、执行事件、新旧入口收口。

### 第 6–9 周

完成数据端口第一段：行情历史、实时快照、CN indicators；消除 `dataflows → screener` 依赖。

### 第 10–12 周

拆 Merger 的纯函数阶段并增加 golden fixtures；不要急着拆所有策略。

90 天后再决定是否继续：

- 深化记忆/反思；
- 增加 Web API；
- 引入回测验证；
- 扩展更多 Provider。

决定依据必须是测试稳定度和真实用户需求，而不是目录是否看起来“高级”。

## 最终建议

这个项目的命运不应是“推倒重来”，也不应是“继续叠功能”。正确路线是：

> **收缩定位，冻结行为，收口入口，建立契约，纠正依赖方向，然后逐个拆除巨型职责。**

只要前 3 个阶段完成，项目就会从难以预测的二开仓库，变成可以持续迭代的研究平台；后面的 Prompt、模型和策略优化才真正值得投入。
