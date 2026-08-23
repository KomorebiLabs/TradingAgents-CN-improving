# TradingAgents 技术报告（架构演进版）

> 版本：v0.2.3（2026-08 架构治理后）
> 项目地址：https://github.com/KomorebiLabs/TradingAgents-CN-improving
> 本文不是功能介绍，而是讲清**这套系统为什么长成现在这样**——按一条主线：**上游架构问题 → Version 1 做了什么改变 → Version 1 仍存在的问题 → Version 2（本版）解决了什么、怎么解决、有什么意义**。
> 阅读顺序：先看 §0 一页主线，再细读 §1→§4（演进），之后 §5 是 V2 现状的技术实现细节（可用作手册查阅）。

---

## §0 一页主线（三代对照）

| 代际 | 定位 | 核心架构问题 | 关键解决 | 遗留 / 代价 |
|---|---|---|---|---|
| **上游** | TauricResearch/TradingAgents（~76k★） | Analyzer 是线性多智能体流程、无上下文压缩/路由/记忆、工具硬编码、纯美股数据 | — | 结构性问题被 V1 整体重建 |
| **V1** | 本仓库初始提交（Phase 1-5） | 上游缺陷 + 快速迭代新引入的结构问题 | 重构 Analyzer（LangGraph 路由/压缩/记忆）、新增 Screener 选股引擎、A 股数据、可观测性 | **状态双写、三套执行驱动器、静默换引擎、配置双中心、数据层反向依赖、双 CLI 分叉、百级吞异常、六大千行单文件** |
| **V2** | 本仓库 2026-08 架构治理 | V1 的七大根基 + 大文件职责灾难 | 入口/执行/状态/数据层逐层收口 + 契约层 + 大文件拆分 + 可靠性 + 验证体系 | 业务有效性（回测）待多窗口验证；免费数据源有漂移风险 |

**一句话概括 V2**：把"能跑的多智能体 demo"治理成"依赖单向、行为可验证、面向二开的演进平台"——439 个离线测试守护，六大千行文件全拆分，公开 API 零改动。

---

## §1 上游 TradingAgents 的架构问题（V2 的"起点"）

原始 Analyzer 的缺陷（V1 重建的根本原因）：

| 缺陷 | 原始实现 | 问题表现 |
|------|----------|----------|
| **辩论机械** | Bull/Bear 轮流发言，count-based 退出 | 缺乏真实推理，Agent 只是轮流输出文本 |
| **无上下文压缩** | 各阶段全量文本直接传递 | 上下文快速膨胀，token 消耗极高 |
| **无路由决策** | 所有标的走相同流程 | 简单标的和复杂标的没有区分 |
| **无记忆系统** | 仅一个 `TradingMemoryLog`（JSON 简单存储） | 无法积累跨会话经验 |
| **无工具抽象** | 工具直接硬编码在 Agent 内 | 无法根据标的类型动态选择工具 |
| **无 A 股数据** | 依赖 yfinance（美股为主） | 无法获取概念板块、资金流、龙虎榜 |

> 这些是"为什么这套系统需要被重建"的原始动因——**V1 的使命就是替掉这张表**。

---

## §2 Version 1：本仓库做了什么改变（承接旧版 §8.1 的叙事）

V1 对 Analyzer 做了根本性重构，并新增了 A 股选股引擎。核心对比：

| 维度 | 上游原始版本 | V1 重构版本 | 改进 |
|---|---|---|---|
| **辩论机制** | 49 行 `Reflector`，1 个方法 | 1117 行 `Reflector`，15+ 方法（逐 Agent 反思 + 路由洞察 + 混合总结） | 辩论质量质变 |
| **图结构** | 136 行 `setup.py`，14 节点，线性流程 | 753 行 `setup.py`，25+ 节点，4 个路由拦截器 + 4 个压缩总结节点 | 智能路由 + 上下文压缩 |
| **上下文压缩** | 无 | 每个阶段边界有 LLM 压缩（Token 阈值 ~18K） | token 消耗大幅降低 |
| **记忆系统** | 1 个 `TradingMemoryLog` | 6 个 `FinancialSituationMemory` + 1 个 `StructuredMemory` | 跨会话智能积累 |
| **工具系统** | 硬编码 | `get_tools_for_analyst()` + `instrument_profile` 按标的动态装配 | 灵活扩展 |
| **A 股数据** | 无 | Screener + `dataflows/akshare_interface` + `cn_*_tools` | A 股全面支持 |

V1 额外构建的子系统（初始提交 130 个 py 文件 vs 上游 64 个）：

- **Screener 选股引擎**（25+ 文件）：6 大策略、信号合并/冲突解决、Deep Analyzer
- **Harness 可观测性**（20+）：Skill 注入、成本追踪、Token 计数
- **A 股数据接口**（15+）：AkShare 中转、概念/资金流/龙虎榜
- **RAG 检索**（8+）：BM25 + 向量、CN 新闻增强
- **CLI / UI**（20+）：统一入口、Live Dashboard

---

## §3 Version 1 仍存在的问题（V2 的"为什么"）

V1 快速迭代把功能做出来了，但架构债同时被埋下。逐条（当年均有 file:line 实证，见 `docx/屎山清理/屎山报告-2`）：

| # | 根基问题 | 表现 | 为什么是根基 |
|---|---|---|---|
| 1 | **状态双写、无 canonical schema** | 同一份数据存平铺+结构化两套，三条路径来回抄 | 加一个字段成本 ×3，没人知道哪份是真的 |
| 2 | **三个平行的图执行驱动器** | `propagate()`、新 CLI 裸流循环、旧 app 各一套 | 同一改动要人肉同步三处 |
| 3 | **try/except ImportError 静默换引擎** | 新代码出错 → 安静切回旧引擎 | 你以为在测新的，实际跑旧的；排查按天计 |
| 4 | **配置双中心 + 全局可变单例** | 图局部 config 与数据层全局 `_config` 单向同步一次 | 部分配置即崩溃；双实例互相污染 |
| 5 | **数据层反向依赖 + 四模块环** | `dataflows` import `screener`；`interface→rag→tools→interface` 环 | 通用层依赖应用层；每次调用新建实例致限流/缓存失效 |
| 6 | **新旧 CLI 分叉 + 安装入口指向旧引擎** | `pip install` 后敲命令进旧 Analyzer | 双入口各自漂移，修复成本指数上升 |
| 7 | **吞异常 + 作文注释文化** | 171 处 `except Exception` 无日志；368 行文件 40 行代码 | 数据坏了静默返回空 |

**大文件单职责灾难**（V1 末期）：

| 文件 | 行数 | 一个文件里混了什么 |
|---|---|---|
| `screener/data_access.py` | 1905 | 供应商注册 + HTTP + 解析 + 探测 + 能力矩阵 + 限流 + 反爬 |
| `dataflows/akshare_interface.py` | 1619 | 全部"供应商"实现挤在单文件 |
| `graph/reflection.py` | 1302 | 反思 + 路由统计 + 记忆 + 结论摘要 |
| `agents/utils/memory.py` | 1124 | 存储 + BM25 + 过滤 + 统计 + 趋势 |
| `screener/merger.py` | 1050 | 聚合 + 冲突 + 硬过滤 + 语义 + 分散 + 排序 |
| `agents/utils/agent_utils.py` | 944 | 工具装配 + 语义槽位大杂烩 |

> 这一章就是 V2 的存在意义：**每一项都对应 §4 里一个具体的治理动作**。

---

## §4 Version 2：本阶段解决了什么、怎么解决、意义

按"入口 → 执行 → 状态 → 数据层 → 可靠性 → 验证"的依赖顺序逐层治理。

### 4.1 入口与执行收口（解决 §3.2 / §3.3 / §3.6）

- **解决**：三套驱动器 → 一套；静默换引擎 → 显式报错；双 CLI 分叉 → 单一入口。
- **怎么做**：
  - 删除全部 3 处 `try/except ImportError` 静默降级，新代码出错直接炸出 traceback（`tradingagents/__main__.py`、`cli/main_menu.py`）；
  - 安装命令改指 `tradingagents.__main__:app`，screener 用 `app.add_typer()` 注册，删掉 `sys.argv` 篡改；
  - `TradingAgentsGraph` 新增公开流式 API `stream_analysis()`，`propagate()` 重写为 4 行薄封装——**官方驱动与 CLI 驱动从此同一条执行路径**；CLI 不再触碰 `graph.graph` / `graph.propagator` / 私有方法（AST 测试钉死）。
- **意义**：执行路径可预测 → 调试可复现 → 后续一切验证可信。这是治理成本收益比最高的一步。

### 4.2 状态契约：Canonical State（解决 §3.1）

- **解决**：状态双写从"永久制度"降级为"迁移期兼容镜像"。
- **怎么做**：
  - `agent_states.py` 顶层声明 **Canonical State Policy**：`analyst_reports` / `debate_blocks` / `decision_blocks` / `ticker_info` 是唯一权威，平铺字段（`market_report`、`final_trade_decision`…）为 legacy 只读镜像；
  - 引入 `STATE_SCHEMA_VERSION = 2` + `AgentState.schema_version`；
  - `_synchronize_structured_state` 重写为 `_ensure_structured_state`：**双向只补缺失、冲突时结构化胜**（修复了旧逻辑"平铺无条件覆盖结构化"会让纯结构化写入被抹掉的隐患）；辩论两形状保持同一对象引用；
  - 日志瘦身：同一份报告不再记两遍（`_log_state`），仅保留 `final_trade_decision` 快取键。
- **意义**：加一个新状态字段现在只动一处（结构化块 + 一行映射），平铺镜像/legacy 读方/日志自动跟上——迁移成本从 ×3 → ×1。这是"接手遗留系统的契约化"标准示范。

### 4.3 数据层：MarketDataPort + 断环 + 类型化错误（解决 §3.5）

- **解决**：`dataflows → screener` 反向依赖、四模块环、"供应商"命名虚构。
- **怎么做**：
  - 新建 `ports/market_data.py`：按能力定义 Protocol（`fetch_hist` / `fetch_spot_snapshot` / `fetch_index_constituents` / `fetch_concept_*`…），方法名与 `ScreenerDataAccess` 对齐、零实现导入；`get_market_data_port()` 返回**进程级共享实例**（修复"每次调用新建实例 → 限流器/缓存报废"）；
  - `cn_indicators.py` 删掉顶层 screener import、改走端口（AST 测试钉死"永不回潮"）；
  - 删除废弃的 RAG 钩子（`route_to_vendor_with_rag` 及 6 个辅助函数，~80 行，零调用方）——环因此断掉：`rag → tools → interface` 单向；
  - 新增 `dataflows/errors.py`：`VendorError(RuntimeError)` 族（`VendorUnavailable`/`VendorRateLimited`/`DataNotFound`/`VendorSchemaChanged`），`interface` 抛类型化错误、限流识别 `isinstance(VendorRateLimited)`。
- **意义**：通用层不再依赖应用层；供应商失败从此有名字，编程错误继续冒泡——"吞异常文化"的第一块地基。

### 4.4 大文件拆分：六大千行 → 单一职责（解决 §3 大文件灾难）

全部通过 **AST 机械切块 + 名字解析检查 + 门面重导出** 完成，公开 API 零改动：

| 文件 | 拆分产物 | 等价性证据 |
|---|---|---|
| `data_access.py` 1905 | 门面 546 + `vendors/{tencent,sina,ths,misc,backup}` + `capability.py` + `response_parsers.py` + `ticker_formats.py` + `vendor_http.py` | +43 测试 |
| `akshare_interface.py` 1619 | 门面 41 + `dataflows/akshare/{stock,news,flow,macro,events,financials}` | +9 测试 |
| `reflection.py` 1302 | `graph/reflection/{extraction,route_analytics,reflector,conclusion}` | stub-LLM parity +9 |
| `memory.py` 1124 | `memory/{store,retrieval,analytics,basic}`（Mixin 组合） | parity +18 |
| `merger.py` 1050 | `merger/{constants,selectors,conflicts,semantic,explanations,filters,aggregation,pipeline}` | golden 17 + parity 8 |
| `agent_utils.py` 944 | 门面 37 + `tools/{tool_assembly,instrument_profile,semantic_prompts,output_rules}` | +9 |

- **怎么做（方法论，可复用）**：① grep 锁定外部调用面 ② 按 self 依赖分簇（纯函数簇先走、门面最后收敛）③ AST 机械切块（⚠️ 注意 `AnnAssign`、间隙语句、段落勿 dedent 的坑）④ 切完跑名字解析检查 ⑤ 门面重导出保 18 个消费方零改动；merger 用 "legacy 双跑 + `model_dump()` 逐字节比对" 作为最强等价性证据。
- **意义**：每个文件只为一个变化原因而变——这既是可维护性，也是面试里"你的重构怎么保证不破坏"的标准答案。

### 4.5 契约层与事件协议（解决"UI 消费引擎内部状态"）

- **解决**：UI/未来 Web/批处理不再复制"如何解释状态"的知识。
- **怎么做**：
  - `application/contracts.py`：`AnalysisRequest`（frozen dataclass，`from_questionnaire()` 兼容问卷、`to_graph_config()` 产出图配置）+ `AnalysisResult`（`to_dict()` 键集被测试冻结）；
  - `application/events.py`：**9 种执行事件**（`AnalysisStarted/Completed`、`MessageEmitted`、`ToolCallObserved`、`ReportSectionUpdated`、`AgentStatusChanged`、`TimelineNoted`、`StageMarked`、`MetricsUpdated`）+ `ChunkEventTranslator`——**全仓唯一允许理解 LangGraph chunk 内部的地方**；
  - `application/service.py`：`stream_events(request)` 事件流 / `run(request, on_event)` 无头执行；图急切构造（坏配置在任何 Live 上下文之前失败）。
- **意义**：`cli/analyze/run_impl.py` 退化为纯事件→UI 适配（AST 测试钉死"chunk 字段名永不回流"）。未来加 Web API 就是新增一个消费 `run()` 的客户端。

### 4.6 数据可靠性（解决"数据坏了静默返回空"）

- **失败可见性**：`vendors/_guard.py` 的 `@vendor_call` 装饰器给 27 个供应商函数统一记日志（异常类型/耗时/空结果），失败不再静默；`dataflows/interface` 对"无数据/不可用"占位文案统一 `logger.warning`（假成功可见）。
- **反爬重试**：`tencent_direct` 只用 `max_retries/retry_delay` 做**连接类错误**（ConnectionError/Timeout）指数退避重试；**HTTP 429/403/5xx 绝不重试**（重试 = 向反爬系统自曝爬虫），每次尝试前保留礼貌 sleep。
- **运行时熔断**：`fetch_hist`（5 源）/ `fetch_spot_snapshot`（3 源）维护每源失败计数，连续失败 3 次短路跳过——同 run 内不再全链盲试（修掉"4000 只 × 每只 15s"的爆炸）。
- **健康监控**：`VendorHealthTracker` 线程安全记录每源 calls/failures/elapsed/last_error，随每次 run 的 capability summary 输出健康表（失败率、均值耗时）。
- **修复潜伏 bug**：`vendors/__init__.py` 显式导入子模块（此前独立使用 `ScreenerDataAccess` 会 AttributeError）。
- **意义**：一个真实 reliability 案例——把"数据与代码失败混为一谈"拆开，失败有了名字、有了日志、有了统计。

### 4.7 验证体系：回测 / 敏感性 / 消融 / 评测

- **回测引擎**（`backtest/`）：自研信号驱动回测，**复用系统真实选股逻辑（TechnicalStrategy）**而非 ad-hoc proxy；每月度再平衡对 CSI300-80 池跑 top5 等权；绩效含总收益/夏普/最大回撤/对比基准；**未来函数显式审计**（`_load_histories` 的 `end_date = trade_date`）。真实产物：总收益 82.86% / 夏普 2.17 / 超额 +56.57%（单段、未计成本，限制已声明）；引擎参数化支持多窗口与 `cost_bps`。
- **参数敏感性**（`--sensitivity`）：动量权重 −22% → 收益腰斩 30.9%（实测）——把"感觉合理"的参数变成"有实测依据"。
- **消融框架**（`ablation/`）：分析师数 × 辩论深度矩阵，量化决策一致性（多数类占比）与成本。
- **正确性评测集**（`eval/`）：已知历史结局 → 前向收益标注（BUY ≥+10% / SELL ≤−10%）→ 混淆矩阵 + 方向准确率。
- **意义**：测试从"冻结行为"走向"验证方向"——这是"demo"与"可评估系统"的分界。

### 4.8 可信度与成本

- **模型祛魅**：`model_catalog.py` 丢弃虚构/超前模型名（GPT-5.4 / Claude Fable / Gemini 3 / DeepSeek V4…），改保守真实子集（gpt-4o / claude-3-5-sonnet / deepseek-chat…），docstring 诚实声明"以官方为准、系统接受任意 model id"；默认 `deep_think_llm=gpt-4o` / `quick_think_llm=gpt-4o-mini`；防回归测试锁定。
- **成本估算**（`llm_clients/cost.py`）：近似 $/MTok 估算每次分析成本。
- **结构化决策提取**：`process_signal` 正则优先（唯一决策词 + 否定防御）省一次 LLM 调用，歧义才走 LLM。
- **LLM 缓存**（`cache.py`）：LRU opt-in，尊重随机性。

---

## §5 V2 现状：技术实现细节（手册）

### 5.1 整体分层

```
CLI / Questionnaire
      ↓
Application Contracts + AnalysisService（契约/事件）
      ↓
TradingAgentsGraph / LangGraph StateGraph（状态机）
      ├── Analysts → Researchers 辩论 → Trader → Risk 辩论 → Portfolio Manager
      ├── AgentState canonical blocks
      └── Execution Events → Live Dashboard / Harness
Agent Tools → Tool Router → MarketDataPort → dataflows / vendor adapters
```

依赖只向右：`cli → application → graph/agents → ports → dataflows/screener`；AST 无环测试钉死。

### 5.2 Screener 数据访问（5 级降级链）

| 数据类型 | 供应商链（第一→末位） |
|---|---|
| 历史 K 线 | 腾讯直连 HTTP → AkShare腾讯 → AkShare新浪 → BaoStock → yfinance |
| 实时行情 | 腾讯直连 → AkShare腾讯 → AkShare新浪 |
| 概念板块 | THS → 新浪 |
| 概念成分 | THS HTML 爬虫 → THS API → 东方财富 |
| 资金流 | THS → 东方财富 |
| 指数成分 | AkShare CSIndex |

反爬：请求限速（`ThrottledRequester`：间隔 0.5s / burst 10 / 失败惩罚 1.5s）+ 浏览器头伪装 + 逐源礼貌 sleep（带抖动）。

### 5.3 三大策略（V2 保持公式不变，行为已冻结）

- **技术面**：趋势/动量/回撤韧性/波动率/一致性/结构风险/量能/突破/背离 9 维加权（0.22/0.18/0.14/0.10/0.12/0.11/0.07/0.04/0.02），clamp [20,95]。
- **主力资金**：tick 失衡 + 大单 + 人气 + 估值 + 龙虎榜 + 连续性 + 质量稳定 加权，clamp [20,100]。
- **政策**：概念热度 + 个股强度 + 相对排名 + 板块领导 + 概念地位（指数成分层级）加权。

### 5.4 信号合并与冲突（Merger 包）

- 同 ticker 多策略合并：`screening_score = min(100, weighted + resonance((源数-1)×5) + semantic_bonus)`；
- 冲突分层：aligned ≤6 / moderate 7-12 / high 13-20 / severe >20；
- 10 重硬过滤（ST / 近跌停 / 流动性 / 市值 / PE / 投机资金流 / 热度断层 / 技术结构 / 冲突否决）+ 同板块分散（≤2 只）。

### 5.5 Analyzer 状态机（LangGraph）

- **状态聚合**：`Annotated[..., operator.add]` 追加辩论历史；结构化块为 canonical。
- **辩论**：多空 `Bull↔Bear` count 制（`count >= 2×rounds` 退出）；风控三方循环（full coverage）；**轮数自适应**（政策 top/高质量冲突 → +1 轮；投机资金 → -1 轮）。
- **记忆**：6 个 `FinancialSituationMemory`（Bull/Bear/Trader/Judge/Portfolio）+ `StructuredMemory`（结构化 metadata + BM25 + 反向索引）——本地实现，刻意不引向量库（离线、兼容任何 LLM）。
- **反思**：`Reflector` 拆为 extraction / route_analytics / conclusion 纯函数 + 反射服务。

### 5.6 LLM 多提供商 & 双模型

- 工厂模式支持 OpenAI / Google / Anthropic / DeepSeek / Qwen / GLM / xAI / OpenRouter / Azure / Ollama；
- 双模型：`deep_think_llm`（Research/Portfolio Manager，复杂推理）+ `quick_think_llm`（Analysts/Researchers/Trader）；
- 真实模型目录 + 成本估算 + 结构化决策提取（见 §4.8）。

### 5.7 技术栈

`Python 3.10+ · LangGraph ≥0.4 · LangChain · pandas · backtrader(可选) · AkShare / yfinance · stockstats · Rich · rank-bm25 · requests`

---

## §6 边界与诚实声明（V2 的"不吹牛"）

| 项 | 状态 |
|---|---|
| 回测 82.86% | 单段（2025-07→2026-06）、未计交易成本、仅技术因子、存续偏差——方法论演示，非预测保证；引擎支持多窗口/成本参数复现 |
| 端到端 LLM 链路 | **未用真实 Key 在本轮运行**（框架就绪，工具 cut-off 的 point-in-time 对技术因子已核，其余待验证） |
| 消融 / 正确性评测 | 框架已落地 + 真实历史标注，真实运行需 LLM Key（见 `ablation/` `eval/` CLI） |
| 数据源 | 免费数据（腾讯/新浪/THS/东财/百度/CSIndex/BaoStock），2 家当前因 AkShare 接口漂移失效；健康监控已可观测、熔断已降级 |

---

## §7 演进路线与文档导航

- **已收口**：入口 ✅ / 执行 ✅ / 状态契约 ✅ / 数据端口+环 ✅ / 大文件 ✅ / 契约层 ✅
- **下一步**（见 `docx/开发文件/治理报告-6`）：多窗口回测与成本显式化、vendors 类型化（随 bug）、point-in-time 全链路审计、消融/评测实跑、README 作品化
- **Phase 6/7**（规划）：HTML 报告、回测正式集成

| 文档 | 用途 |
|---|---|
| `docs/architecture.md` | V2 分层与证据标签（架构岗深读） |
| `docs/interview-notes.md` | 面试 60 秒介绍 + FAQ + 诚实应答 |
| `docx/屎山清理/屎山报告-1..5` | 诊断与施工记录（V1 遗留的原始证据） |
| `docx/开发文件/治理报告-6` | 残余不足与下一阶段方案 |
| `README.md` | 项目门面（亮点 + 快速开始） |
