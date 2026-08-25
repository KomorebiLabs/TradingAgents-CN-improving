# AI Agent / LLM 工程面试导航

> 这份笔记用于面试前快速复习。回答以当前代码、离线测试和仓库内报告为边界。
>
> **重要声明：仓库已经用 Agnes 2.5 Flash 完成一次真实 Analyzer headless 运行，并完成一次 DeepAnalyzer 合同夹具真实验收。** 这只能证明指定配置下的执行链、报告落盘和部分供应商降级可工作；不能推导真实模型正确率，也不能替代 HITL 暂停/恢复和多日稳定性验收。

## 1. 60 秒项目介绍

这是一个面向 A 股的多智能体 LLM 交易分析框架。它不是简单地把几个 Prompt 串起来，而是用 LangGraph `StateGraph` 编排一条有状态的决策流程：先由 Market、Social、News、Fundamentals 分析师形成基础报告，再经过 Bull / Bear Researcher 辩论、Research Manager 裁决、Trader 生成交易计划，最后由三方风险分析师和 Portfolio Manager 完成风险审议与最终决策。

工程上，我重点做的是把 Agent 系统变成可演进的平台：用 `AnalysisRequest` / `AnalysisResult` 作为应用层契约，用 `AgentState` 的结构化块作为 canonical 状态，用 `Tool Router → MarketDataPort → Dataflows` 隔离数据能力和供应商，用 `stream_analysis()` 和 Application Events 把 LangGraph 内部状态转换成 UI、无头 API 和观测系统都能消费的稳定事件。与此同时，我处理了历史系统中的多入口、三套图驱动器、状态双写、数据层反向依赖和 1905 行 God Class 等问题，并用离线 contract / golden / parity 测试保护行为不漂移。

目前可以证明的是架构边界、682 个离线护栏、部分回测产物，以及 Agnes 配置下的一次 Analyzer headless 运行和一次 DeepAnalyzer 合同验收；我仍不会把这些证据包装成真实模型准确率或生产级交易效果。

## 2. 项目地图

```text
CLI / Questionnaire
        ↓
AnalysisRequest / AnalysisService
        ↓
TradingAgentsGraph / StateGraph
        ├── Analyst Team
        ├── Research Debate
        ├── Trader
        └── Risk Debate / Portfolio Manager
                ↓
        AgentState + Execution Events
                ├── Live Dashboard / Summary
                ├── Harness metrics / cost
                └── Reports

Agent Tools
        ↓
Tool Router / MarketDataPort
        ↓
Dataflows / vendor adapters
```

深度架构说明见 [`docs/architecture.md`](architecture.md)。

---

## 3. LangGraph 与多智能体问答

### Q1：为什么使用 LangGraph，而不是自己写一串函数调用？

**短答：**

因为这个系统不是线性调用，而是有阶段、状态、条件路由、辩论轮次和阶段交接的有状态工作流。LangGraph 的 `StateGraph` 能把节点、状态和边显式化，让流程结构可以测试，也让 UI 和无头执行共享同一套图内核。

**追问展开：**

- `GraphSetup.setup_graph()` 负责节点和阶段装配；
- `AgentState` 是整个 DAG 的上下文；
- `conditional_logic.py` 和编排节点决定阶段交接；
- `TradingAgentsGraph.stream_analysis()` 对外提供稳定的流式执行入口；
- `propagate()` 是兼容性薄封装，而不是另一套图驱动器。

我不会说 LangGraph 自动解决了 Agent 的正确性；它解决的是流程显式化、状态管理和执行边界问题。

### Q2：多智能体之间如何协作？

**短答：**

我把协作分成多个职责阶段，而不是让所有 Agent 共享一个无限增长的对话。分析师先生成不同视角的报告；研究员围绕这些报告进行多空辩论；Research Manager 形成投资计划；Trader 把计划变成交易方案；风险团队再从不同风险偏好审议，Portfolio Manager 最终裁决。

**追问展开：**

- 分析师负责事实和视角的收集；
- Researcher 负责对立论证；
- Manager 负责阶段性压缩和裁决；
- Trader 负责把研究结论转成行动计划；
- Risk team 负责从风险角度重新审议，而不是简单重复研究结论。

阶段之间通过结构化 `AgentState` 和图路由连接，不依赖某个 CLI 的临时全局变量。

### Q3：Agent 是并行执行还是串行执行？

**短答：**

我会以当前图定义和实际配置为准，不把“多智能体”自动等同于“所有节点并行”。架构上，分析师属于同一阶段，研究、交易和风控属于后续阶段；具体的并行或条件路由由 StateGraph 的边和配置决定。面试时我会展示图的阶段边界，而不是承诺未经当前实现验证的并行度。

### Q4：quick model 和 deep model 为什么要分开？

**短答：**

这是任务复杂度和成本的分层：常规分析、研究员响应等任务使用 quick model；Research Manager、Portfolio Manager 等需要综合多个上下文的裁决使用 deep model。它是资源分配策略，不是“deep model 一定更准确”的业务保证。

---

## 4. 状态管理问答

### Q5：`AgentState` 为什么要有 canonical schema？

**短答：**

历史系统同时维护平铺字段和结构化字段，同一份报告可能有两种形状，新增字段容易漏同步。我把 `ticker_info`、`analyst_reports`、`debate_blocks`、`decision_blocks` 定义为 canonical，旧的平铺字段保留为兼容镜像。新代码优先写读结构化块，迁移期通过 `schema_version` 和兼容同步保护旧消费者。

**追问展开：**

- 结构化状态冲突时胜出；
- 平铺字段暂时不能立即删除，因为旧路由、日志或报告消费者仍存在；
- 迁移策略是“先确立权威，再逐步迁移读方，最后退役镜像”；
- canonical 测试覆盖结构化-only、平铺-only、冲突和日志形状。

### Q6：如果要新增一个 Agent，需要改哪些地方？

**短答：**

先定义它的状态输入输出，再在 `agents/` 下实现节点；然后在 `GraphSetup` 注册节点并在路由逻辑中接入阶段；如果它需要新能力，则增加工具或 Port 契约；最后补事件、状态和离线契约测试。不会直接在 CLI 里复制一套执行逻辑。

**追问展开：**

- 状态字段应加入结构化块；
- 图节点负责局部决策；
- Application 层只负责请求、事件和结果；
- UI 通过事件消费，不读取图内部私有字段；
- 新 provider 或新数据源落在工厂、Port 或 adapter 扩展点上。

### Q7：状态会不会无限增长？

**短答：**

会话状态和辩论历史存在增长风险，所以图中有阶段交接和上下文压缩相关的编排元数据，`state_helpers` 也把交接阈值命名化。工程上还需要持续关注 Token 成本和上下文预算；我不会声称当前已经解决所有长上下文问题。

---

## 5. Tool、数据和错误治理问答

### Q8：为什么 Agent 不能直接调用供应商 SDK？

**短答：**

因为那会把业务节点和数据源实现焊死：供应商接口变化时需要修改多个 Agent，测试也必须访问网络。当前通过工具、路由和 `MarketDataPort` 把“需要什么能力”和“能力由谁实现”分开，测试可以注入 stub，默认实现也可以在组合点选择具体数据访问门面。

**具体链路：**

```text
Agent → tool → route_to_vendor / method registry
      → MarketDataPort
      → dataflows / vendor adapters
```

### Q9：供应商失败时怎么处理？

**短答：**

预期的供应商不可用、限流、数据不存在和 schema 变化应该通过类型化错误表达，再由路由层决定降级、换源或记录失败。项目已经建立 `VendorError` 层级和部分路由识别，但 vendors 底层仍存在较宽的捕获范围，因此目前的准确说法是“类型化错误地基已建立，逐链路治理仍在进行”。

**追问展开：**

- 429 / 403 等反爬或限流情形不能和普通网络错误混为一谈；
- 假成功的“无数据”结果需要可观测；
- 健康监控应记录供应商失败率、耗时和错误细节；
- 编程错误不应该被宽泛捕获后伪装成正常数据。

### Q10：`MarketDataPort` 具体解决了什么问题？

**短答：**

它解决了通用数据层直接依赖上层 Screener 的方向错误，也修复了每次调用新建数据访问对象导致限流器和历史缓存失效的问题。Port 通过 Protocol 定义市场数据能力，默认工厂集中处理运行时组合，测试可以注入 stub。

---

## 6. 可观测性、成本和评测问答

### Q11：如何观察一次 Agent 运行？

**短答：**

LangGraph 原始 chunk 不直接给 UI。`ChunkEventTranslator` 把它转换成稳定的 Application Event，例如消息、工具调用、报告分段、Agent 状态、阶段标记和指标更新。Dashboard、无头 API 和未来 Web API 都消费事件，而不是各自解析图内部结构。

**可观察维度：**

```text
LLM 调用次数 / 工具调用次数
输入 Token / 输出 Token / 成本估算
Agent 状态 / 阶段时间线
报告分段 / 错误与降级
Skill 注入与使用审计
```

### Q12：测试体系如何分层？

| 测试类型 | 主要回答的问题 |
|---|---|
| Import / smoke | 入口、版本和关键模块是否可加载 |
| Contract test | 状态、事件、Port 的接口形状是否稳定 |
| Golden test | 固定输入下的业务规则和解析结果是否稳定 |
| Parity test | 重构前后的公开输出和报告形状是否漂移 |
| Dependency graph test | 分层边界和无环约束是否被破坏 |
| Eval framework | 如何评估决策方向和结果标签 |

这些测试可以在无网络、无 LLM 条件下运行。评测框架已存在不等于已经产生真实评测结论。

### Q13：为什么不直接做一个端到端 API smoke？

**短答：**

真实 smoke 对确认 provider、权限、配额和报告落盘很有价值。本项目已经用 Agnes 2.5 Flash 完成一次 Analyzer headless 运行和一次 DeepAnalyzer 合同夹具验收；这证明指定配置下的执行路径可工作，但不等价于模型正确率、多日稳定性或 HITL 长链路已经通过。

如果进入下一阶段，我会先补真实 HITL pause/comment/resume 和五个不同交易日的 Screener 监控，再考虑消融和正确性评测。

### Q14：有真实 API 运行后，如何证明 Agent 工程质量？

**回答：**

分三层：**代码能力、离线验证、业务证据**。

- 代码能力：LangGraph 状态编排、canonical AgentState、Tool / Port 分层、Application Events，这些是可以在源码里直接看到的结构；
- 离线验证：682 个离线测试覆盖状态迁移、图流、依赖无环、供应商路由、证据门禁、评测数学和工具参数契约，全部不需要网络和 LLM；
- 业务证据：已有一次 Agnes headless 运行、一次 DeepAnalyzer 合同验收和 Screener 真实阶梯运行，但真实模型评测仍需要单独预算，我明确标注为"未形成统计结论"。

面试官真正想确认的是我**分得清这三层**，而不是把一次真实运行包装成模型准确率。离线工程能力和证据边界意识恰恰是 Agent Runtime 岗位最看重的部分。

### Q15：如何避免评测标签泄漏？

**回答：**

标签和 Agent 输入是严格隔离的。

- 标签由 `eval_date` **之后**的历史价格算出 forward-return 映射而来；
- Agent 的 request 使用 `eval_date` 作为 `trade_date`，`build_case_set` 用确定性 seed、去重、封顶 n；
- 有离线测试断言：request 的 ticker/trade_date 只来自 eval case，标签和 horizon 数据不会进入 request；
- 报告里显式区分 `framework_ready` 和 `real_model_run`，避免把离线框架验证误当成模型 benchmark。

### Q16：Tool failure 如何进入可观测路径？

**回答：**

分两层。

- 事件层：`ChunkEventTranslator` 把工具调用转成 `ToolCallObserved` 事件，消息去重保证同一工具调用不会被重复计数；
- 数据层：`VendorError` 层级（不可用/限流/数据缺失/schema 变化）给预期失败命名；连接类错误会重试、429/403 不重试；占位"无数据"文本会被记录而不是伪装成正常结果。

同时有工具契约测试验证 `curr_date`、`start_date`、`end_date` 这类参数在 Tool → router → provider 全链路不被丢失或错位——这是时间 grounding 的工程化保障。

### Q17：如何区分 LLM cost 和 trading cost？

**回答：**

这是两个不同的问题。

- **LLM cost（Agent 运行经济性）**：Token 消耗、模型单价、调用次数、缓存命中/未命中、延迟。`CostTracker`、`llm_clients/cost.py`、`llm_clients/cache.py` 处理这部分，可以离线验证；
- **Trading cost（金融回测成本）**：手续费、滑点、印花税、换手率，属于回测场景的金融成本，是后续治理项。

我的岗位是 Agent 工程，所以简历和面试重点讲 LLM 运行经济性，金融成本只作为业务场景的限制说明，不混淆两者。

### Q18：为什么不直接宣称模型准确率？

**回答：**

因为我没有跑真实 LLM 评测，宣称准确率就是造假。评测框架（已知结局案例、混淆矩阵、方向准确率、`real_model_run` 标志）已经就绪并有离线测试，但真实模型运行需要 API key、预算和可复现的报告。我把它列为待验证工作，而不是伪造数字。这种边界意识本身是面试加分项——Agent 系统最重要的就是知道自己的证据边界。

---

## 7. “铲屎山”重构故事

### 7.1 STAR 版本

**Situation：**

项目原本能运行，但存在多套入口、多套 LangGraph 驱动器、状态平铺/结构化双写、数据层反向依赖和一个 1905 行的 `ScreenerDataAccess`。更危险的是，导入错误可能触发静默 fallback，导致开发者以为在运行新代码，实际走了旧引擎。

**Task：**

在不破坏公开行为和既有报告形状的前提下，让执行路径可预测、状态可解释、数据依赖可替换，并为后续 Agent 扩展建立测试护栏。

**Action：**

1. 先移除静默 ImportError fallback，统一安装入口和版本来源；
2. 提取 `stream_analysis()`，让 `propagate()`、CLI 和 Dashboard 共享图执行内核；
3. 将结构化 AgentState 块确立为 canonical，引入 `schema_version` 和兼容镜像；
4. 用 `MarketDataPort` 打断 `dataflows → screener` 的反向依赖；
5. 将 1905 行门面按变化原因拆成 vendor、parser、capability、ticker format 和 HTTP 层；
6. 每一步用离线 smoke、contract、golden、parity 和依赖图测试验证。

**Result：**

施工记录显示，入口、图流、状态、Port、解析器、Application Contract 和事件协议逐步获得离线护栏；`ScreenerDataAccess` 的公开方法、签名、返回值和 fallback 顺序保持，结构边界变得可以单独测试。后续交接材料记录测试护栏达到 439 个，并在评测契约与工具契约收口后增长到 453 个。

**边界：**

这证明的是工程结构和离线行为护栏，不证明本轮真实 LLM provider 已经跑通，也不证明交易策略具有普遍预测能力。

### 7.2 面试追问：你为什么不直接重写？

**回答：**

因为这是有外部消费者和历史产物的系统，推倒重写会同时改变状态形状、报告格式、fallback 顺序和入口行为，无法判断问题来自重构还是功能变化。我选择先锁定调用面，再按一个边界一次移动，保留公开 API，用 parity 和 golden 测试确认行为不漂移。重构的目标不是让目录看起来漂亮，而是让下一次改动的影响范围可预测。

### 7.3 面试追问：你如何证明“拆分”不是机械搬文件？

**回答：**

我是按变化原因拆的：解析格式变化只影响 parser，供应商实现变化只影响 vendor，探测策略变化只影响 capability，礼貌策略和请求头只影响 HTTP 层，门面只负责公开 API 和 fallback 编排。如果一个文件仍会因为四五种不同原因同时修改，就说明边界还没有真正建立。

---

## 8. 敏感数字的诚实回答

### Q19：回测收益 82.86% 是否说明模型很准？

**回答：**

不能这样解释。这个数字来自一个 12 个月单窗口的 Technical 因子实验，使用 CSI300 当前成分池子集、月度再平衡 top5，未计交易成本，并存在存续偏差。它能说明回测和报告链路有真实产物，也能用于参数敏感性讨论，但不能直接证明 LLM 决策准确率或策略在不同市场环境下普遍有效。下一步需要多窗口、point-in-time 和成本显式化验证。

### Q20：682 个测试是不是说明系统已经可靠？

**回答：**

它说明很多接口、状态迁移、图流、供应商路由、解析器、证据门禁和回测数学有离线护栏，但测试数量不是业务有效性的充分条件。当前测试仍以结构和冻结行为为主，真实 provider 漂移、多日稳定性、模型正确率和交易成本影响仍需要单独验证。

### Q21：真实 LLM 链路跑过吗？

**回答：**

跑过一次 Agnes-only 的 Analyzer headless 链路，也跑过一次固定候选的 DeepAnalyzer 合同验收。当前可以确认 `AnalysisRequest`、`AnalysisService`、`stream_analysis()`、事件协议和报告落盘路径在指定配置下能完成运行；但我不会把单次运行描述成真实 provider 的稳定性或正确率证明。HITL 暂停/恢复和多日稳定性仍需要单独验收。

---

## 9. 当前不足与下一步

以下内容是治理计划，不是本轮交付：

- 小规模真实正确性评测（框架已就绪，当前仍未形成真实统计结论）；
- 小规模消融实验；
- 多窗口回测；
- 交易成本 `cost_bps` 敏感性；
- 真实 HITL pause/comment/resume/abort 运行证据；
- Screener 连续五个不同交易日稳定性证据；
- vendors 逐链路类型化错误；
- AkShare 接口漂移探测；
- 关键业务路径 golden 覆盖提升；
- 配置全局单例和低优先级技术债治理。

已完成但需持续维护：技术指标路径的 point-in-time 截止防御、工具参数契约测试和评测框架的 `framework_ready / real_model_run` 边界。

建议顺序是：先补真实 HITL 和五日 Screener 监控，再做真实评测和消融，最后扩展多窗口回测和成本；面试展示则使用封箱报告与演示手册，保持事实边界。

## 10. 最后复述版

> 我做的不是简单加几个 Agent，而是把一个多入口、多状态、多供应商的 LangGraph 系统逐步收口成可验证的 Agent 平台。流程上用 StateGraph 管阶段和路由，状态上用 canonical AgentState 管契约，能力上用 Tool 和 MarketDataPort 隔离数据源，接口上用 Application Events 解耦 UI 和图内部，工程上用离线 contract / golden / parity 测试保护重构。现在我能明确区分哪些是代码能力、哪些是离线证据、哪些是业务实验、哪些还需要真实运行验证。
