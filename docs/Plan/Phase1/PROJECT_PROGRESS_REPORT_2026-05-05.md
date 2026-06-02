# TradingAgents Harness 重构项目进展交付说明

更新时间：2026-05-05（第二次更新：添加 route_history 功能）  
项目目录：`D:\cursor\HarmonyOS\Github project\TradingAgents-main`  
基线来源：`TauricResearch/TradingAgents` 的本地改造版本  
重构参考：`HKUDS/OpenHarness` 的 Harness 架构思路

## 1. 报告目的

这份文档用于把当前项目迭代工作完整迁移到 Cursor 环境继续开发。  
文档覆盖：

- 最初四大模块计划与当前实际推进情况
- 从开始到现在的关键改造路径
- 已新增/修改文件及其目的、效果
- 当前可交付成果、验证结果、已知边界
- 下一步建议执行任务


- 原计划：TradingAgents 项目 Harness 架构重构计划（V1.0）详见注释

<!-- 一、 L1：Prompt Engineering（信息边界层）★☆☆☆☆
核心定位：主要是 Prompt Tuning。利用 XML 标签和角色定义来裁剪信息。
角色与格式约束（完全采纳）
深度专家设定：不仅是简单的 Risk Manager，应将其设定为具有 20 年 A 股量化风控经验的合规官。
XML 标签化思维：在 Prompt 中强制使用 XML 标签（如 <thinking>、<analysis>、<decision>）来分隔模型的思考过程与最终指令，减少模型在长链决策中的注意力涣散。
少样本提示 / Multi-shot（完全采纳）
为 Trader Agent 提供 3-5 个典型的高质量交易决策报告示例，向模型展示如何权衡辩论双方的观点，从而确保最终输出符合预期的专业金融风格。
结构化置信度评分（待商榷/持保留意见）
构思：强制要求模型在输出末尾对自己的决策打分（Confidence Score），并说明评分依据（如数据支持度、逻辑自洽性）。
现状：目前尚不能确定该方案是否能够真正有效地提升系统或模型的准确率，需进一步测试。
二、 Context Engineering ＆ L4：状态与记忆层 ★★★☆☆
核心定位：按需供给与信息防腐。涉及 LangGraph 的 AgentState 设计，通过结构化存储防止上下文腐烂。（本模块整体采纳）
重构 AgentState (L4 记忆与状态层)
思路：拒绝把所有聊天记录无脑塞在一起。在 LangGraph 的状态类中明确区分信息区块，如 ticker_info（基础信息）、analyst_reports（中间产物）和 final_decision（最终决策）。
极度注意：AgentState 绝对不能够轻易或随便修改，必须是有意义的修改。上述方案仅为初步构思，并非最终定稿。
动态上下文获取 (MCP 插件化 / Agent Skills)
系统绝不应一次性将所有分析工具塞给模型。
针对不同类型的股票（如科创板与红利股），动态加载 AkShareInterface 中的特定 API。例如：分析宁德时代时，系统才自动挂载碳酸锂价格监控工具。
CN Stack 本地化数据重构 (信息裁剪与 Chunking)
针对 A 股宏观政策和龙虎榜数据，利用 RAG 机制进行**先检索、再重排 (Re-ranking)**。确保送入模型窗口的是最核心的政策导向，而不是冗长的公告全文。
上下文压缩与交接 (Context Reflect)
痛点：多、空双方辩论会产生大量 Token，极易导致模型产生上下文焦虑从而急于敷衍收尾。
机制：当 Token 达到安全阈值时，触发专门的总结 Agent将辩论精华进行压缩，并交接给下一个新的 Agent，实现类似重启进程的效果以恢复干净状态。
三、 L2：工具系统层 (Tool System)
核心定位：规范模型的手与底层数据的纯净度。
数据源切换与预处理 (Pruning)（完全放心/维持现有优秀架构）
任务：将原有 yfinance 切换为 AkShare 或 TuShare。
处理标准：编写 Python 函数对工具返回的原始 JSON 数据进行硬核预处理，仅保留核心指标（如主力资金流向、异动龙虎榜），坚决避免全量数据塞入上下文。这部分原项目的架构做得比较好，可以放心沿用其处理逻辑。
按需挂载 / Agent Skills（计划纳入）
在 LangGraph 中增加动态路由逻辑，根据个股所属的特定行业（如白酒、半导体），动态将特定的行业分析脚本注入上下文环境。
四、 L3：执行编排层 (Execution Orchestration)
核心定位：解决下一步干什么，构建任务闭环。
整体态度：本环节概念采纳，但坚决不赞同此前过于简单直率的细化落地建议。
下一步要求：
必须构建**完整轨道**：需要系统性地重构 LangGraph 的运行流程。
核心探讨方向：多步骤任务到底应该怎么串起来？条件边（Conditional Edges）如何基于原有的图基础进行科学搭建？这些问题必须在后续展开专门且深入的讨论，拒绝草率决定。 -->


## 2. 原始重构目标回顾

本轮重构围绕四个模块展开：

1. `L1 Prompt Engineering`
   目标：强化角色定义、XML 结构化输出、few-shot 风格约束。
2. `L2 Tool System`
   目标：将工具系统向中国大陆股票数据场景收敛，推进 AkShare 化、数据裁剪化、工具按需挂载。
3. `L3 Execution Orchestration`
   目标：重构 LangGraph 运行轨道，让阶段跳转、压缩交接、条件边真正受状态驱动。
4. `L4 State & Memory`
   目标：把状态从散乱的聊天上下文改为结构化状态块，支撑后续编排、压缩、记忆、日志和反思。

## 3. 当前总体完成度

- `L1 Prompt Engineering`：`100%`
- `L2 Tool System`：`约 85%`
- `L3 Execution Orchestration`：`约 92%`
- `L4 State & Memory`：`约 72%`

说明：

- `L1` 已完成本轮目标，后续仅可能有局部 prompt 微调，不属于主线阻塞项。
- `L2` 已完成中国大陆股票数据主干、工具纯净化、按 profile/skill 路由，但更细颗粒 CN 专项工具仍可继续扩展。
- `L3` 已完成主要闭环、可变轨道、observability 接入。本轮新增 event_trail，记录每次 stage/phase/next_stage 转换。剩余尾差：reflection 基于 event_trail 生成更强路由洞察。
- `L4` 已完成结构化 state 主干、字符串拼接式 memory 接入。剩余尾差：memory schema 结构化改造（存储和检索都支持结构化字段）。

## 4. 阶段推进复盘

### 4.1 第一阶段：L1 Prompt Engineering

本阶段的核心不是多写 prompt，而是给后续 Harness 化改造打一个统一的输出边界。

已完成内容：

- 为关键决策节点引入统一 XML 结构 prompt。
- 强化角色人设，尤其是风险/组合决策角色向具有 20 年 A 股量化风控经验的合规官靠拢。
- 为 Trader 引入高质量 few-shot 示例，提升交易结论的专业金融表达风格。
- 把 `Confidence Score` 设计成实验性开关，而不是全局硬要求，避免无效约束污染主流程。

阶段效果：

- 输出格式更稳定，便于后续 handoff、压缩、日志记录。
- 决策节点的专业语气和结构一致性明显增强。
- 给后续 `L3` 的压缩代理和状态机提供了更可消费的上游产物。

### 4.2 第二阶段：L4 State & Memory 基础改造

本阶段优先处理状态结构问题，因为如果 state 还是散乱的，后面的路由、handoff、动态工具挂载都会很脆弱。

已完成内容：

- 引入结构化状态块：
  - `ticker_info`
  - `analyst_reports`
  - `debate_blocks`
  - `decision_blocks`
  - `orchestration`
- 保留原项目 legacy 顶层字段，同时做双写/回填，降低改造风险。
- 补齐 state 初始化逻辑与同步逻辑，确保新旧字段可并存。

阶段效果：

- 为 `L2` 的 instrument profile / skills / CN 市场路由提供了承载位置。
- 为 `L3` 的 `phase`、`next_stage`、`compression_required` 等执行编排字段提供了正式落点。
- 降低所有信息都堆在消息列表里的上下文腐烂问题。

### 4.3 第三阶段：L2 Tool System 主干改造

该阶段围绕中国大陆股票数据优先推进，不再默认把系统当成以 `yfinance` 为核心的美股场景。

已完成内容：

- 引入/重构 AkShare 数据接口，作为 CN 股票数据主干来源。
- 对 AkShare 返回结果做裁剪和结构化整理，避免把原始大 JSON 直接塞进模型上下文。
- 保留 vendor fallback 机制，避免依赖缺失时系统直接崩。
- 引入 instrument profile：
  - `cn_main_board_equity`
  - `cn_chinext_equity`
  - `cn_star_equity`
  - `cn_bse_equity`
- 引入 style bucket：
  - `dividend_style_candidate`
  - `growth_style_candidate`
- 引入 skills 路由机制，让不同标的可以挂载不同工具能力。
- 增加 CN 专项工具入口：
  - `get_cn_policy_news`
  - `get_cn_market_flow`

阶段效果：

- 项目现在已经具备较清晰的中国大陆股票分析底盘。
- 相同 LangGraph 框架下，不同中国股票可以带出不同工具集合和提示约束。
- 数据纯净度显著提高，更适合后续压缩、辩论和决策节点消费。

### 4.4 第四阶段：L3 Execution Orchestration 主干改造

这是本轮改造的主战场，目标是把原本偏线性的 TradingAgents 流程，推进成真正的 Harness 式状态驱动轨道。

已完成内容分三层：

#### 第一层：编排状态字段引入

- 引入 `orchestration` 控制块关键字段：
  - `stage`
  - `phase`
  - `next_stage`
  - `compression_notes`
  - `compression_required`
  - `completed`
  - `final_route`
  - `final_reason`

#### 第二层：阶段路由节点引入

- 增加新的编排节点：
  - `Route Research Phase`
  - `Route Trader Phase`
  - `Route Risk Phase`
  - `Route Portfolio Phase`
- 增加 handoff summary 节点：
  - `Summarize Analyst Phase`
  - `Summarize Research Phase`
  - `Summarize Trader Phase`
  - `Summarize Risk Phase`
- 增加风险收口专用节点：
  - `Finalize Risk Debate`

#### 第三层：从固定跳转升级为状态驱动跳转

- `Research Manager` 不再一律固定跳到 trader，而是根据：
  - 辩论长度
  - 决策输出长度
  - 是否已有 `compression_notes`
  来决定走 `trader` 还是 `trader_handoff`
- `Trader` 不再固定跳到 risk，而是根据：
  - `investment_plan` 长度
  - 交易计划长度
  - 是否已有 `compression_notes`
  来决定走 `risk` 还是 `risk_handoff`
- 风险层不再固定结束，而是先判断：
  - 三方观点是否完整
  - 是否达到辩论轮次上限
  - 是否需要二次压缩
- `Portfolio Manager` 出口会显式把 orchestration 收口到：
  - `stage=completed`
  - `phase=completed`
  - `next_stage=completed`
  - `completed=True`
  并保留：
  - `final_route`
  - `final_reason`

阶段效果：

- LangGraph 轨道已经从固定 research -> trader -> risk -> portfolio推进成基于状态的可变轨道。
- 当上下文变长时，系统会自动先压缩再交接，而不是硬塞给下游节点。
- 风险层结束逻辑变成真正有闭环判断的状态机，而不是简单靠轮次数终止。
- 日志和反思系统现在已经可以知道流程为什么这样收口，而不只知道最终结论是什么。

## 5. 已新增/修改文件清单与作用说明

以下为本轮改造中最关键的文件。

### 5.1 核心状态与工具辅助

#### [tradingagents/agents/utils/agent_states.py](/abs/path/placeholder)

实际路径：`D:\cursor\HarmonyOS\Github project\TradingAgents-main\tradingagents\agents\utils\agent_states.py`

主要作用：

- 定义结构化状态块。
- 扩展 `OrchestrationState`，承载阶段、压缩、完成态、最终路径、最终原因。

带来的效果：

- 全部 Harness 级编排信息有了统一状态落点。

#### [tradingagents/agents/utils/state_helpers.py](/abs/path/placeholder)

实际路径：`D:\cursor\HarmonyOS\Github project\TradingAgents-main\tradingagents\agents\utils\state_helpers.py`

主要作用：

- 提供结构化 state 双写助手。
- 提供 `next_stage` 动态判断逻辑：
  - `determine_research_manager_next_stage`
  - `determine_trader_next_stage`
  - `determine_risk_next_stage`
- 提供风险闭环辅助逻辑：
  - `has_full_risk_debate_coverage`
  - `determine_risk_follow_up_speaker`
  - `determine_risk_debate_exit_stage`

带来的效果：

- 状态驱动路由逻辑不再散落在各个节点里，便于维护和测试。

### 5.2 Prompt / 决策层

#### `tradingagents/agents/prompts/*`

主要作用：

- 统一 XML 决策 prompt 模板。
- 增加 Trader few-shot 示例。

带来的效果：

- 输出结构、风格、可消费性增强。

#### `tradingagents/agents/managers/research_manager.py`

主要作用：

- 消费 `compression_notes`
- 使用统一 XML 决策模板
- 动态写入 `next_stage`

带来的效果：

- Research 阶段结束后是否直达 Trader，已由状态决定。

#### `tradingagents/agents/trader/trader.py`

主要作用：

- 消费 research handoff notes
- few-shot 风格强化
- 动态写入 `next_stage`

带来的效果：

- Trader 阶段是否需要进入压缩交接，已进入真实判断。

#### `tradingagents/agents/managers/portfolio_manager.py`

主要作用：

- 增强风险合规角色设定
- 消费 `compression_notes`
- 最终写回 orchestration 完成态与审计字段

带来的效果：

- 最终节点不再只是给出结论，而是显式结束整条轨道。

### 5.3 风险辩论层

#### `tradingagents/agents/risk_mgmt/aggressive_debator.py`

主要作用：

- 消费上游压缩 notes
- 根据风险辩论体量和状态动态设置 `next_stage`

带来的效果：

- 风险层也参与到闭环编排，不再只是单纯产生辩论文本。

#### `tradingagents/agents/risk_mgmt/conservative_debator.py`

主要作用：

- 保留原风险辩论逻辑，作为风险覆盖完整性判断的一部分。

带来的效果：

- 与风险状态机配合，保证三方意见有条件地补齐。

#### `tradingagents/agents/risk_mgmt/neutral_debator.py`

主要作用：

- 保留原平衡视角逻辑，参与风险完整性闭环。

带来的效果：

- 避免风险层在三方未齐的情况下过早收口。

### 5.4 Graph 编排层

#### `tradingagents/graph/setup.py`

主要作用：

- 新增 orchestration router 节点工厂
- 新增 phase handoff 节点工厂
- 新增 `Finalize Risk Debate`
- 重构条件边，将原固定链路替换为可变轨道路由

带来的效果：

- 这是本轮 Harness 化最核心的图结构改造文件。

#### `tradingagents/graph/conditional_logic.py`

主要作用：

- 管理阶段路由逻辑
- 优先判断 `compression_required`
- 风险辩论结束时判断是继续补辩论还是进入 finalize

带来的效果：

- 执行轨道从静态 DAG变为状态驱动 DAG。

#### `tradingagents/graph/propagation.py`

主要作用：

- 初始化新的结构化 state 和 orchestration 审计字段

带来的效果：

- 所有新逻辑从初始态就可用，不依赖运行中补洞。

#### `tradingagents/graph/trading_graph.py`

主要作用：

- 同步 legacy 字段与 structured state
- 为最终状态补齐 orchestration 默认值
- 让日志记录包含新的 orchestration 信息

带来的效果：

- 运行结果、日志、结构化状态之间的一致性更强。

### 5.5 L2 CN 数据与工具系统

#### `tradingagents/dataflows/akshare_interface.py`

主要作用：

- 新增或增强 AkShare 数据接口能力。

带来的效果：

- 中国大陆股票分析从工具底盘上变得更合理。

#### `tradingagents/dataflows/interface.py`

主要作用：

- 统一抽象数据接口与 vendor fallback。

带来的效果：

- 多数据源/降级兼容更稳定。

#### `tradingagents/agents/utils/agent_utils.py`

主要作用：

- 增加 instrument profile 识别
- 增加 tool mounting 与 skills 路由
- 增加 CN 相关工具入口与上下文构建

带来的效果：

- 不同股票市场/板块/风格可以携带不同能力集合。

#### `tradingagents/agents/utils/news_data_tools.py`

主要作用：

- 增加中国大陆政策新闻、市场流向类工具封装。

带来的效果：

- 新闻与资金相关输入更贴近中国股票场景。

### 5.6 测试文件

#### `tests/test_harness_state.py`

主要作用：

- 验证 structured state、orchestration 初始化与回填逻辑。

#### `tests/test_akshare_interface.py`

主要作用：

- 验证 AkShare 接口与数据裁剪输出。

#### `tests/test_vendor_fallback.py`

主要作用：

- 验证 vendor 缺失或降级场景。

#### `tests/test_tool_mounting.py`

主要作用：

- 验证工具挂载行为是否与 analyst/profile/skills 对齐。

#### `tests/test_instrument_profile.py`

主要作用：

- 验证中国大陆股票 profile、segment、style bucket 识别逻辑。

#### `tests/test_orchestration_logic.py`

主要作用：

- 验证 L3 新增路由、压缩、handoff、risk finalize、completed 审计逻辑。

#### `tests/test_confidence_flag.py`

主要作用：

- 验证 experimental confidence 开关行为。

## 6. 到目前为止实际达成的能力效果

### 6.1 对中国大陆股票的适配能力增强

真实场景举例：

- 分析 `600519.SH` 这类主板股票时，系统会识别为 `cn_main_board_equity`，可挂载更适配 CN 市场的工具与提示。
- 后续如果继续补 CN 工具，现有 profile/skill/router 基础已经够用，不需要推倒重来。

### 6.2 对长上下文的抗腐烂能力增强

真实场景举例：

- 如果 Bull/Bear 辩论过长，系统不会把整段辩论直接丢给 Trader，而会先生成 trader-ready handoff memo。
- 如果风险辩论过长，系统可以先生成 portfolio memo，再交给 Portfolio Manager。

### 6.3 对运行轨道的可解释性增强

真实场景举例：

- 最终日志里现在不仅能看到结论，还能看到：
  - 是直接 `portfolio`
  - 还是 `portfolio_handoff`
  - 为什么这么选

### 6.4 对后续 Cursor 持续开发的友好度增强

真实场景举例：

- 你在 Cursor 里继续开发时，可以直接围绕 `orchestration`、`ticker_info`、`analyst_reports` 等结构化块扩展，不必再先清理老状态结构。

## 7. 验证与测试结果

当前已确认通过的关键回归：

- `venv\Scripts\python -m unittest tests.test_ticker_symbol_handling tests.test_model_validation tests.test_google_api_key tests.test_harness_state tests.test_confidence_flag tests.test_akshare_interface tests.test_vendor_fallback tests.test_tool_mounting tests.test_instrument_profile tests.test_orchestration_logic`
- 结果：`52/52 OK`

编译检查：

- `venv\Scripts\python -m compileall tradingagents tests cli main.py`
- 结果：通过

说明：

- 目前这轮重构后的主线状态是稳定可运行、可测试、可继续扩展的。

## 8. 当前未完成项与边界

### 8.1 L2 未完成点

- 中国大陆专项工具还不够细。
- 目前已有 CN policy news / market flow，但还没有进一步细化到更多行业或专题工具。
- RAG + rerank 还没有正式落地。

### 8.2 L3 未完成点

- event_trail 已记录完整 stage/phase/next_stage 转换历史。
- 剩余尾差：reflection 基于 event_trail 生成更强路由洞察，评估哪种轨道对结果有帮助/有伤害。

### 8.3 L4 未完成点

- structured state 主干已完成，orchestration 上下文通过字符串拼接方式进入了 memory。
- 剩余尾差：memory schema 结构化改造，使存储和检索都支持结构化字段（event_trail、final_route、final_reason）。

## 9. 下一步建议任务

建议下一阶段优先顺序如下。

### 9.1 优先任务 A：基于 event_trail 增强 reflection（这是 L3 最后 3%）

目标：

- 基于 route_history/event_trail 生成更强的 route insight
- 让反思明确评估"哪种轨道对结果有帮助/有伤害"
- 而不是重做已经完成的 `_extract_orchestration_context`

建议修改方向：

- `tradingagents/graph/reflection.py`：新增 `_generate_route_insight_from_trail()` 方法
- 利用 `event_trail` 统计压缩触发频率、路径分布

预期效果：

- 后续可以统计哪些场景最容易触发 handoff，哪些路径的最终决策质量更好。

### 9.2 优先任务 B：回到 L2 数据纯净度深化

目标：

- 对中国大陆股票增加更强的专题工具能力
- 推进先检索、再重排的信息裁剪思路

建议修改方向：

- 增加 CN 行业/政策专题工具
- 为 news/policy 数据增加更强的筛选逻辑
- 逐步准备 RAG + rerank 框架

预期效果：

- 进一步压缩无用噪音，让模型只看到最相关的 A 股信息。

### 9.3 优先任务 C：推进 L4 记忆层深化

目标：

- 把 orchestration 从"拼进字符串"升级成"结构化可检索字段"
- 修改 memory schema，使存储和检索都支持结构化字段

建议修改方向：

- memory 存储 schema 扩展（支持 event_trail、final_route 等字段）
- retrieval 返回 schema 扩展
- 所有消费 rec["recommendation"] 的节点适配新 schema

预期效果：

- 后续同类股票或同类风险场景的决策可复用性更强。
- 可以按 segment/style_bucket/route 等结构化字段进行精准检索。

## 10. 建议的 Cursor 接手方式

建议你在 Cursor 中继续开发时按以下方式接手。

1. 先阅读本文件。
2. 再重点阅读以下代码文件：
   - `tradingagents/agents/utils/agent_states.py`
   - `tradingagents/agents/utils/state_helpers.py`
   - `tradingagents/graph/setup.py`
   - `tradingagents/graph/conditional_logic.py`
   - `tradingagents/agents/managers/research_manager.py`
   - `tradingagents/agents/trader/trader.py`
   - `tradingagents/agents/managers/portfolio_manager.py`
   - `tradingagents/agents/utils/agent_utils.py`
   - `tradingagents/dataflows/akshare_interface.py`
3. 运行现有测试，确认 Cursor 环境与当前环境一致。
4. 从 `L3 收官` 或 `L2 深化` 二选一继续推进，不建议同时大范围改动两个模块。

## 11. 当前结论

到目前为止，这个项目已经不再只是TradingAgents 的轻微修改版，而是已经形成了一个初步的 Harness 化重构版本，尤其体现在：

- prompt 边界更清晰
- 中国大陆股票工具底盘更明确
- LangGraph 编排已经具备真实的状态驱动能力
- structured state 已经成型
- 风险收口与最终完成态具备审计性

当前最适合的下一步，不是大范围推翻，而是在现有稳定骨架上继续把 `L3` 和 `L4` 做深，把 `L2` 做专。
