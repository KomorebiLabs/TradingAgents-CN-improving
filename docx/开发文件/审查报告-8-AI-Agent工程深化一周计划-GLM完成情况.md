# 《AI-Agent 工程深化一周计划》GLM 完成情况审查报告

审查日期：2026-08-24
审查对象：[开发报告-8-AI-Agent工程深化一周计划.md](D:/cursor/HarmonyOS/Github%20project/TradingAgents-main/docx/%E5%BC%80%E5%8F%91%E6%96%87%E4%BB%B6/%E5%BC%80%E5%8F%91%E6%8A%A5%E5%91%8A-8-AI-Agent%E5%B7%A5%E7%A8%8B%E6%B7%B1%E5%8C%96%E4%B8%80%E5%91%A8%E8%AE%A1%E5%88%92.md)
审查范围：当前工作区未提交代码、测试、已有报告产物及 GitNexus 索引结果。

## 一、结论

结论：**没有全部完成，不能按计划文件第 10 行“全部落地”验收。**

当前实现中，A2、A3 的基础仪表化、E1/E7 的主要骨架、E2 的 OpenAI SDK 重试、部分 A4/A6/B2/B3/B5 已经存在；但 A5 的真实 CLI 恢复链路是坏的，E3 还引入了可复现的 `NameError` 回归，A4/A6/B3/B5 的关键验收条件也没有实现或没有被真实集成测试证明。

计划文件自己已经承认 B2 数据治理、A5 向导前置问题、E3 批二、E5、B6 的降级或延期，但这不能覆盖下列“已声称落地却实际不成立”的问题。

## 二、验证证据

### 1. 测试与静态检查

- 针对性测试：`80 passed, 1 warning`。
- 全量测试：`541 passed, 1 warning in 34.88s`。
- `python -m compileall -q tradingagents cli tests` 通过。
- 测试数量与计划文件声明的“540 离线测试”不一致；当前实际收集到 541 个测试。
- GitNexus 索引显示仓库约 4569 个符号、8633 条关系、300 条执行流。当前工作区变更经 `detect_changes()` 评估为 `critical` 风险，涉及 61 个变更符号、63 个受影响符号/执行流；本次审查没有修改业务代码。

### 2. 两个最小运行复现

#### A5 恢复参数断链

执行：

```text
AnalysisService().stream_events(..., resume_payload={'action': 'proceed'})
```

实际结果：

```text
TypeError: AnalysisService.stream_events() got an unexpected keyword argument 'resume_payload'
```

CLI 在 [cli/analyze/run_impl.py:219-222](D:/cursor/HarmonyOS/Github%20project/TradingAgents-main/cli/analyze/run_impl.py:219) 传入了 `resume_payload`，但 [tradingagents/application/service.py:45-102](D:/cursor/HarmonyOS/Github%20project/TradingAgents-main/tradingagents/application/service.py:45) 的应用层接口没有接收、保存或转发该参数；底层 [tradingagents/graph/trading_graph.py:87-96](D:/cursor/HarmonyOS/Github%20project/TradingAgents-main/tradingagents/graph/trading_graph.py:87) 虽然支持 `Command(resume=payload)`，但实际 CLI 到不了那里。

#### E3 Alpha Vantage 日期格式回归

执行：

```text
format_datetime_for_api('2024-01-15 14:30')
```

实际结果：先捕获日期格式不匹配，随后在 [tradingagents/dataflows/alpha_vantage_common.py:209-210](D:/cursor/HarmonyOS/Github%20project/TradingAgents-main/tradingagents/dataflows/alpha_vantage_common.py:209) 访问未定义的 `logger`，抛出：

```text
NameError: name 'logger' is not defined
```

新增的 `import logging` 和 `logger` 被错误插入文件末尾的示例文档字符串中，并没有成为可执行模块代码。

## 三、逐项验收矩阵

| 项目 | 审查结论 | 证据与缺口 |
|---|---|---|
| A2 收敛驱动辩论 | **基本完成** | 有 8000 字符预算、头尾截断、截断分数下限、收敛日志、路由和针对性测试。当前未发现阻断性缺口。 |
| A3 压缩仪表化/校准 | **部分完成** | 已移除旧 `compression_threshold_tokens`，有 36000 字符阈值和 `context_stats.json`。但产物字段使用 `context_estimate` 而非计划要求的 `estimated_chars`；当前 27 个产物中只有 1 个有非空阶段数据，没有看到基于约 10 次运行计算 P75 的证据，仍是临时锚点。 |
| A4 证据校验 | **部分完成** | 已有句子级抽取、单位/语义/范围校验、最多 20 条 warning 和集成节点。缺少 `[derived]` 等级；工具证据没有 `as_of`/来源日期，无法验证计划要求的时间错配陷阱；增长类断言直接跳过而不是形成明确的 unverified 记录；没有 600519 真实运行统计证据。 |
| A5 HumanGate | **未完成且真实链路损坏** | 节点级 `interrupt()` 和 `Command(resume=...)` 测试通过，但 CLI 恢复调用必然触发上述 `TypeError`。`abort` 分支只打印消息，随后仍执行 `assert active_result_stream.result is not None`，未生成计划要求的 abandoned artifact、已消耗成本和完整审计记录。CLI `--hitl` 存在，但向导前置选择已被计划明确降级。 |
| A6 Prompt 注入防御 | **部分完成，高风险缺口** | 通用 dataflow 路由会包裹新闻文本，但 `get_rag_news`/`get_rag_sector_news` 在 RAG 直接命中时直接返回格式化内容，绕过 [tradingagents/dataflows/interface.py:125-133](D:/cursor/HarmonyOS/Github%20project/TradingAgents-main/tradingagents/dataflows/interface.py:125) 的过滤。盐是模块进程级 `_SALT`，不是每次运行生成；未发现 `injection_filtered` 应用事件或盐值审计产物，只有 Python logger。 |
| B1 产品定位 | **部分完成** | README 等主要文案已调整，但 [tradingagents/dataflows/alpha_vantage_indicator.py:56](D:/cursor/HarmonyOS/Github%20project/TradingAgents-main/tradingagents/dataflows/alpha_vantage_indicator.py:56) 仍保留“是量化交易和算法交易的核心工具”，与计划要求的全局清理不一致。 |
| B2 PIT/时间可信度 | **部分完成，且与计划声明一致** | 已有 prompt 时间声明和回测语言 lint；但 `as_of`、PIT 等级注册、请求日期钳制、违规事件、来源 A/B 注册表均未实现。当前 lint 只扫描少数固定回测短语，不能替代数据治理。 |
| B3 组合上下文/硬约束 | **部分完成** | 有组合 prompt 和 ConstraintEnforcer，但实现读取 `~/.tradingagents/portfolio.json`，计划要求的是 YAML。硬约束只处理 `max_single`，依赖狭窄的中文仓位正则；没有 `max_industry`、`cash_ratio` 的程序化强制，也没有对多种输出格式的可靠解析。 |
| B5 A 股执行规则 | **部分完成** | prompt 中有 T+1、涨跌停、摩擦成本和收盘价锚定价文字；配置使用 JSON 而非计划要求的 YAML。未实现止损/挂单价的输出后硬校验、T+1 语义检查、价格钳制、偏离收盘价超过 2% 的 warning，因此目前主要是软约束。 |
| B6 基线对账 | **延期，不计为本轮已完成** | 计划已明确说明被移出终版执行清单；当前未发现本轮完成 BaoStock CSI300 买入持有、20 日动量及净优势报告的证据。 |
| E1 断点续跑 | **骨架完成，真实验收不足** | 有按 run_id 的 SQLite checkpointer、`thread_id=run_id`、`--resume` 和离线断点测试。但测试是内存/模拟图级场景，没有真实 CLI kill/resume 证据；checkpointer 构建失败时还会降级为无 checkpointer。 |
| E2 分类重试 | **部分完成** | OpenAI SDK 的 `max_retries=3`、429/5xx/连接异常与认证错误测试通过。供应商 HTTP 层只重试连接/超时；没有读取 `Retry-After`，429 没有单独长退避，重试退避没有使用随机抖动，403 只是返回并记录日志而非明确的熔断状态。计划要求没有全部满足。 |
| E3 异常收窄/可观测 | **未完成，且有回归** | AkShare 若干路径增加日志，但仍保留宽泛 `Exception`；计划延期的 semantic_prompts 批二未做。更严重的是 Alpha Vantage 新增日志引用未定义变量，已由最小运行复现确认。 |
| E5 mypy | **按计划跳过** | 计划明确标记为可选并跳过；不作为本轮失败项，但不能对外宣称完整达标。 |
| E7 run-id 全链路追踪 | **基本完成** | 有 12 位 run_id、事件、结果、报告目录、request.json、message_tool.log 前缀和 summary 展示；现有测试覆盖了事件、产物和结果。真实长链路运行证据仍未提供。 |

## 四、需要优先修复的问题

### P0：阻断 HumanGate 实际使用

统一 `AnalysisService.stream_events`、`AnalysisEventStream`、`TradingAgentsGraph.stream_analysis` 三层的 `resume_payload` 参数，并补一个应用层/CLI 集成测试：首次运行暂停、传入 comment、PM 看见 comment、最终报告包含 comment。另行实现 abort 的 abandoned artifact、成本和审计事件，不能只在 CLI 打印提示。

### P0：修复 Alpha Vantage 回归

把 `logging` 导入和 `logger = logging.getLogger(__name__)` 放到模块可执行区域；增加 `format_datetime_for_api('YYYY-MM-DD HH:MM')` 的回归测试。

### P1：补齐 A6 审计闭环

所有 RAG 直返结果必须经过同一层过滤/盐定界；盐应绑定 run_id 并写入运行产物；过滤命中应产生应用层 `injection_filtered` 事件，而不是只有普通日志。增加 RAG 命中、伪造闭合标签、跨运行盐变化和审计产物测试。

### P1：把 B3/B5 从 prompt 约束升级为硬校验

统一计划中的 YAML 配置格式；B3 至少实现单票、行业、现金比例的结构化校验和可审计修正；B5 增加价格、T+1、涨跌停及 2% 偏离检查，并覆盖 XML/中文自然语言/结构化输出三类输入。

### P1：补 A4 时间与 derived 语义

为 ToolMessage 保存来源和 `as_of` 信息，明确区分 verified/derived/unverified；时间无法证明的数字必须进入 unverified，而不是被静默跳过。补齐计划列出的三个陷阱 fixture 和一次真实 600519 运行产物校验。

## 五、审查范围说明

本报告只新增了本报告文件，没有修改 GLM 已产生的业务代码、测试或计划文件。当前仓库仍保持原有未提交修改状态；因此本报告评价的是“当前工作区中 GLM 方案的实际可验收程度”，不是某个干净提交的理论状态。

## 六、聊天记录反查出的额外线索

用户提供的聊天记录与仓库产物交叉后，进一步得到以下结论：

1. GLM 的测试过程主要是节点级/纯函数级测试。聊天记录中的“521 passed”“540 passed”“19/19 一次全过”没有对应到 A5 的应用服务恢复测试、CLI 交互测试或真实中断后续跑测试；这与当前 `resume_payload` 断链相吻合。
2. 聊天记录显示真实运行至少经历了 OpenAI key 缺失、Agnes key 未加载、DeepSeek 模型大小写错误等失败尝试。最终宣称成功的 `run_id=54b7c7ba076e` 目前只留下： [request.json](D:/cursor/HarmonyOS/Github%20project/TradingAgents-main/reports/600519/2026-08-21/54b7c7ba076e/request.json) 和 [context_stats.json](D:/cursor/HarmonyOS/Github%20project/TradingAgents-main/reports/600519/2026-08-21/54b7c7ba076e/context_stats.json)。该目录没有报告文件、`message_tool.log`、verification summary 或收敛/约束审计文件，因此不能独立证明“完整跑通并完成全部验收”。
3. 上述运行的 `request.json` 中 `hitl_mode` 为 `null`，所以即使它确实产生了 577 个事件、`OVERWEIGHT` 决策，也没有验证 HumanGate 的暂停、comment、abort 或 resume 链路。
4. 聊天记录末尾明确记载：真实运行结束后才发现“全新运行传给图的 run_id=None”，随后才修复 E1。也就是说，这次真实运行本身不能作为修复后的 E1 验收证据；并且记录结束时没有看到修复后完整长链路的可核验产物。
5. 聊天记录将 E3 批一概括为“14 处数据路径可见化”，但机械修改过程中多次出现 import 定位失败、`continue` 变体和单行 `except: pass` 被弄坏等善后记录。最终 Alpha Vantage 日期格式路径仍留下 `logger` 未定义回归，说明“编译通过”没有覆盖异常分支运行测试。

因此，这段聊天记录不是完成证明，反而说明验收流程存在“先做局部绿灯、再进行不完整真实运行、真实运行后才发现集成缺陷”的过程性风险。

## 七、接力修复结果（Codex，2026-08-24）

在保留 GLM 未提交工作区修改的前提下，按 [接力实施计划](../../docs/superpowers/plans/2026-08-24-ai-agent-handoff.md) 分阶段修复并验收。没有执行 reset、checkout 或 commit。

### 已完成并有离线证据的项目

| 项目 | 本次处理 | 验收证据 |
|---|---|---|
| A5 / E1 | `resume_payload` 从 `AnalysisService` 透传到图；HumanGate abort 写入 `abandoned.json`；流结束写入安全审计 | `tests/test_handoff_fixes.py`、`tests/test_run_resume.py`、`tests/test_phase3.py` 相关测试通过 |
| A6 | run-scoped salt、过滤计数、RAG 直返统一定界、`security_audit.json`、`injection_filtered` 时间线事件 | A6、RAG、工具契约测试通过 |
| E3 | 修复 Alpha Vantage `logger` 异常路径；日期字符串回归覆盖 | `format_datetime_for_api("2024-01-15 14:30")` 测试通过 |
| E2 | 连接/超时退避加入 jitter；429 记录 `Retry-After` 且不盲目重试；保留 403 单次尝试语义 | 数据可靠性与供应商测试通过 |
| B3 | `portfolio.yaml` 优先、JSON 兼容、负仓位/总仓位校验；单票、行业、现金比例硬钳制并留痕 | YAML、约束函数及 ConstraintEnforcer 测试通过 |
| B5 | 卖出 T+1 语义、涨跌停价格钳制、收盘锚点偏离 warning、盈亏平衡锚点 warning | 4 个执行校验测试及阶段测试通过 |
| A4 / B2 | `verified/derived/unverified` 三态；有 `as_of` 时拒绝未来证据；缺少来源日期时在 PIT 请求中保持 unverified；未来交易日入口钳制并写 warning | 时间错配、derived、缺日期和未来日期测试通过 |
| A2 / A3 | 保留原有收敛逻辑；`context_stats.json` 增加 `estimated_chars`，兼容旧字段；补充最小样本数为 10 的离线 P75 计算 | 收敛与阈值校准测试通过 |

### 最终验证结果

- 仓库自带虚拟环境全量测试：`562 passed, 1 warning in 76.95s`。
- `compileall -q tradingagents cli tests`：通过。
- `git diff --check`：通过；仅有 Git 关于工作区换行符的提示。
- 系统 Python 的全量测试曾因缺少 `questionary` 在收集阶段失败；改用仓库 `venv` 后全量通过。唯一 pytest warning 来自第三方 `py_mini_racer` 对 `pkg_resources` 的弃用提示。
- GitNexus `detect_changes(scope=all)`：整体工作区为 `critical`，`22` 个变更文件、`82` 个变更符号、`79` 个受影响符号。该结果包含 GLM 原有未提交修改，不能解释为本次接力代码单独的风险；因此没有据此宣称可直接合并。

### 仍未完成或不能宣称完成的事项

1. 没有执行真实 API 长链路或真实 CLI kill/resume/HITL 运行。本次验证均为离线 stub、纯函数和 LangGraph 内存 checkpointer 场景；既没有新增真实 `reports/<ticker>/<date>/<run_id>/` 验收目录，也没有证明真实模型会写齐 `message_tool.log`、最终报告、验证摘要和各类审计文件。
2. A4 的严格来源日期规则在 state 提供 `trade_date` 时生效；为保持历史私有调用兼容，缺少 `trade_date` 的旧式直接调用仍保留旧证据匹配行为。真实图状态应始终提供 `trade_date`，但仍建议后续把该契约做成类型级必填。
3. E3 的“异常收窄”和 B2 完整来源注册表、B1 全仓库文案清理、B6 对账、E5 mypy 仍不属于本次已完成项；其中 E5 按原计划为可选跳过，B6 按原计划延期。
4. `detect_changes` 仍报告整体工作区 critical；在 GLM 改动被拆分、提交或建立干净基线前，不应把当前工作区作为低风险 PR 直接合并。

本轮结论：GLM 报告中列出的主要 P0/P1 缺口已获得离线实现和回归证据，但“全部任务真实运行验收完成”仍不成立；下一步应在用户明确提供可用模型/API 与运行预算后，单独执行一次 headless 真实运行和一次 HITL 暂停/恢复运行。

## 八、真实 Agnes 运行复核（Codex，2026-08-24）

上述“尚未执行真实 API 长链路”的结论已因本节运行而更新：用户配置 Agnes API key 后，使用 Agnes-only 配置执行了一次完整的无交互真实运行；没有使用 DeepSeek。官方模型/网关配置依据为 [Agnes-2.5-Flash 文档](https://agnes-ai.com/zh-Hans/docs/agnes-25-flash)。

### 1. 运行身份与结果

- API 预检返回 `AGNES_OK`；密钥未写入报告或终端输出。
- 请求快照确认：`llm_provider=agnes`、`deep_think_llm=agnes-2.5-flash`、`quick_think_llm=agnes-2.5-flash`、网关为 `https://apihub.agnes-ai.com/v1`。
- 运行目录：[reports/600519/2026-08-20/25e30f4ec605](../../reports/600519/2026-08-20/25e30f4ec605)。
- 最终决策：`HOLD / CAUTIOUS ACCUMULATE`，置信度 `60%`；26 次 LLM 调用、37 次工具调用，约 9 分 37 秒。
- 已生成最终交易决策、研究计划、交易计划、四类分析报告、验证摘要、`context_stats.json` 和 `security_audit.json`。
- 本次为 `--no-interactive`，因此没有宣称完成 HumanGate 的暂停/comment/resume 验收；A5 的真实人工交互验收仍未完成。

### 2. 真实运行暴露的问题

- 第一次无交互启动曾错误落到静态默认 OpenAI 配置并触发缺失 `OPENAI_API_KEY`；接力修复了 `AnalysisRequest.default_for()` 的环境配置读取，第二次才真正以 Agnes 完成运行。
- 第一次运行还暴露模型生成未来 `get_news` 日期的问题；接力修复 vendor 路由边界后，第二次运行的 40 条工具调用中，没有任何请求日期超过 `2026-08-20`。日志中的 `2026-08-24` 仅是数据源“retrieved on”时间，不是请求日期。
- 新闻数据多次返回 no news；财务三表返回 unavailable，Agnes 随后生成了带不确定性说明的基本面报告。这证明降级路径能继续完成流程，但不证明数据源质量达标。
- 日志出现 1 次非法 ticker 被安全拒绝、3 次模型调用了当前 analyst 工具集不存在的工具；流程没有崩溃，但这应作为工具契约与模型提示改进项，而非成功取数证据。
- `verification_summary.md` 检查了 5 项数字断言，0 项被工具数据验证，5 项保持 unverified；因此最终决策不能被解释为“已完成基本面数据核验”。
- `security_audit.json` 的本次 `filtered_count=0`，表示本次没有命中注入过滤事件，不表示输入数据天然可信。

### 3. 最终回归结果

- 仓库虚拟环境全量测试：`564 passed, 1 warning`。
- `compileall -q tradingagents cli tests`：通过。
- `git diff --check`：通过。
- 为避免本机 `.env` 污染静态默认值测试，新增测试隔离：测试显式清除 `LLM_PROVIDER` 等环境覆盖后再检查 `DEFAULT_CONFIG`；真实 CLI 仍按用户环境使用 Agnes。

### 4. 更新后的验收结论

真实 Agnes headless 长链路现在已有可核验产物，GLM 原先“没有真实运行证据”的问题已由本节补足；但“全部任务已完成”仍不能成立：HumanGate 真实暂停/恢复、数据源完整可用性、A4 数字证据充分性以及整体工作区 critical 变更风险仍需单独处理。报告中第七节关于“尚未执行真实 API 长链路”的表述，以本节为后续更新后的结论为准。

## 九、数据供应商与证据链修复复核（Codex，2026-08-24）

针对真实运行中暴露的“新闻多次无数据、财务三表 unavailable、基本面数字 0/5 被验证”问题，本轮继续完成了数据路由、供应商适配和 A4 证据链修复。这里区分“供应商返回了数据”和“报告数字被安全验证”两个不同验收层次。

### 1. 已定位的根因

1. `600519.SH` 直接传给 yfinance 时不会映射到 Yahoo 的 `600519.SS`，导致 yfinance 财务接口误判为空；AkShare 财务接口本身在本机环境中会返回 `NoneType` 异常占位文本。
2. 路由层原先把 `No ...`、`unavailable` 和 Alpha Vantage 的空新闻 JSON (`items=0, feed=[]`) 当成成功结果，后备供应商无法接管；同时 `ths_data` 与 `legacy_akshare` 可能重复调用同一实现。
3. 工具契约用 `ticker=` 调用新闻适配器，而 AkShare 适配器参数名为 `symbol`，导致真实工具链出现 `unexpected keyword argument 'ticker'`；此前单独用位置参数探针无法发现这个集成缺陷。
4. A4 校验器对真实 ToolMessage 缺少来源日期时会安全地全部保持 `unverified`；此外，小数点会被切句，`823.20` 等财务数字无法被识别。三表 CSV 也只有裸数字，没有在同一证据句中标明单位和财务期间。

### 2. 本轮修复

- [tradingagents/dataflows/stockstats_utils.py](../../tradingagents/dataflows/stockstats_utils.py)：增加中国 A 股代码到 yfinance `.SS/.SZ` 的规范化。
- [tradingagents/dataflows/y_finance.py](../../tradingagents/dataflows/y_finance.py)：财务和基本面调用统一使用规范化代码；三表增加“指标名 + 财务期间 + CNY 单位”的 evidence-ready 摘要，同时保留原始 CSV；利润表补充毛利率证据行。
- [tradingagents/dataflows/akshare/news.py](../../tradingagents/dataflows/akshare/news.py)：新闻适配器接受工具契约的 `ticker=` 关键字，并对 EastMoney 新闻快照做 5 分钟缓存，减少重叠查询造成的 403。
- [tradingagents/dataflows/interface.py](../../tradingagents/dataflows/interface.py)：识别文本占位、空新闻 JSON 和重复实现；后备耗尽时返回包含方法、各供应商尝试结果及“不得据此推断公司事实”的 `[DATA_UNAVAILABLE]` 审计提示，并记录 runtime failure、rate limit 和 fallback 日志。
- [tradingagents/agents/utils/evidence_verifier.py](../../tradingagents/agents/utils/evidence_verifier.py)：识别供应商输出中的财务期间，避免小数点切句，补充 gross profit 语义族；只有期间不晚于交易日且同句有单位/指标锚点时才验证。

### 3. 验收证据

- 全量离线测试：`575 passed, 1 warning in 17.43s`；`compileall` 和 `git diff --check` 均通过。
- 真实数据探针（未输出 API key）：
  - `get_balance_sheet("600519.SH", "annual", "2026-08-20")` 返回约 6.6 KB 的 yfinance 财务表；
  - `get_cashflow(...)` 返回约 4.5 KB；
  - `get_income_statement(...)` 返回约 5.2 KB，包含 2025 年营收、毛利润、营业利润和净利润；
  - `get_akshare_news(ticker="600519", ...)` 返回约 522 字节真实 AkShare 新闻，`route_to_vendor("get_news", ticker=...)` 返回约 586 字节、已定界的新闻内容，而不是空 feed。
- 将真实利润表输出交给 A4 校验器并使用实际 600519 基本面报告片段测试，16 项数字断言中 8 项安全验证、8 项保持 unverified；这证明验证器不再因全局缺日期而把历史三表证据全部丢弃，也没有放宽单位和 PIT 约束。
- Agnes-only 真实运行 `32ea5af171da` 已证明修复前的财务后备路径能返回三表；该运行发生在新闻 `ticker` 关键字修复前，因此其中新闻仍记录为 `[DATA_UNAVAILABLE]`。关键字修复后的真实 AkShare/路由探针已成功，但尚未再次消耗完整 Agnes 长链路预算，因此不能把 `32ea5af171da` 的旧 `0/7` 摘要改写成修复后的完整长链路统计。

### 4. 当前结论与剩余风险

本项任务已经完成“根因定位、供应商接管、新闻空结果识别、财务三表可用性恢复、缺失降级提示和证据校验修复”，不再是原来的静默 fake success。新闻供应商受 EastMoney/网络 403 影响时仍可能暂时没有文章；此时系统会明确返回 `[DATA_UNAVAILABLE]`，下游必须保持新闻结论为未验证，而不能把空 feed解释为“没有重大新闻”。

尚未宣称完成的是：使用最新代码再跑一次完整 Agnes 长链路并取得新的最终 `verification_summary.md`。当前已有真实供应商探针、真实 Agnes 运行产物和 575 个离线测试，足以证明本次修复有效，但不足以声称“最新代码的完整报告已经重新生成”。

## 十、官方公告源、独立财务源与统一供应商健康状态（Codex，2026-08-24）

针对“可靠的信息来源必须优先接入，并统一建立供应商健康状态”的新要求，本轮完成了独立的官方披露链路和可降级的独立财务链路。这里不把媒体新闻、监管披露和财务报表混为一个可信度等级。

### 1. 来源选择与现实边界

- 公告优先采用 [巨潮资讯网（CNINFO）](https://www.cninfo.com.cn/) 的上市公司公告查询接口；它提供公告标题、公告日和官方 PDF 文档链接。对沪市公司也保留 [上海证券交易所上市公司公告入口](https://www.sse.com.cn/assortment/stock/list/info/announcement/index.shtml?productId=600909) 作为来源依据。当前实现先接入 CNINFO 的统一查询端点，避免把搜索引擎或自媒体文章当成监管披露。
- 独立财务源采用可选的 [Tushare Pro 财务指标接口](https://tushare.pro/document/2?doc_id=79)、[现金流量表接口](https://tushare.pro/document/2?doc_id=44) 和官方 [API 请求协议](https://tushare.pro/document/2?doc_id=130)。Tushare 权限按账号和积分控制，因此适配器必须允许“已配置但无接口权限”这一非健康状态，并自动回退既有供应商。
- yfinance、AkShare 仍作为后备数据源使用；它们不是本轮新增的监管公告源，也不被健康状态中的 `ok` 解释为“所有字段都已被证据验证”。

### 2. 本轮实现

- 新增 [tradingagents/dataflows/cninfo_announcements.py](../../tradingagents/dataflows/cninfo_announcements.py)：规范化 A 股代码、公告日期、标题、公司名和 CNINFO 官方文档 URL；网络异常和响应结构变化会进入路由降级链。
- 新增 [tradingagents/dataflows/tushare_financials.py](../../tradingagents/dataflows/tushare_financials.py)：支持利润表、资产负债表和现金流量表，输出报告期、发布日期、单位和供应商标记；缺少 token、权限不足和无数据均保持可审计文本。
- 新增 [tradingagents/dataflows/vendor_health.py](../../tradingagents/dataflows/vendor_health.py)：统一维护 `ok`、`empty`、`not_configured`、`rate_limited`、`blocked`、`auth_error`、`schema_error`、`timeout`、`exception` 状态，保留调用次数、失败率、平均耗时、状态计数和脱敏后的最后错误。
- [tradingagents/screener/vendors/_guard.py](../../tradingagents/screener/vendors/_guard.py) 兼容导出同一个 tracker，选股器和主数据路由不再各自维护两套健康模型。
- [tradingagents/application/service.py](../../tradingagents/application/service.py) 在每次运行结束写入 `vendor_health.json`；摘要只包含供应商聚合状态，不保存 token 或 Authorization header。
- 新闻分析工具新增官方公告工具，Tushare Pro 财务适配器已注册为显式可选；当前 `.env` 的 `TUSHARE_ENABLED=false`，默认继续使用 AkShare/yfinance 回退链。公告源单独归类为 `announcement_data`，不会冒充普通媒体新闻。

### 3. 真实只读探针

- CNINFO：对 `600519` 查询 `2026-08-01~2026-08-24`，HTTP 请求成功，返回 6 条公告；输出包含 `cninfo.official` 和官方文档链接，健康状态为 `ok`。
- Tushare：对 `600519.SH` 查询年度利润表，当前本机 token 已配置，但账号返回“没有 income 接口访问权限”；路由将该响应记录为 `auth_error`，随后继续回退，最终 `legacy_yfinance` 返回约 5.2 KB 的利润表数据。没有输出 token。
- 这说明“供应商接入”与“供应商账号已经拥有全部权限”是两个不同事实：CNINFO 当前可用；Tushare 适配器和健康监控已可用，但要让独立财务源真正提供数据，仍需给当前 Tushare 账号开通相应接口/积分，或配置另一家有授权的独立财务 API。

### 4. 最终验证

- 全量离线测试：`586 passed, 1 warning in 31.35s`。
- 针对官方源、健康状态、路由、分析产物的回归测试：`39 passed`。
- 真实探针再次确认 Tushare 的权限失败不会阻断分析，并且健康快照能同时显示 `tushare_pro=auth_error` 与 `legacy_yfinance=ok`。
- 代码未执行 commit；保留工作区已有未提交修改。未打印或写入任何 API key。

### 5. 用户配置决定：暂不启用 Tushare

用户当前只有 122 积分，低于利润表、资产负债表和现金流量表各自要求的 2000 积分，因此已选择暂不启用 Tushare 财务源。项目在 `.env` 中保留 `TUSHARE_TOKEN` 字段，同时新增 `TUSHARE_ENABLED=false`；Token 可以保存，但默认路由不会调用 Tushare。以后达到权限要求后，将该开关改为 `true` 才会显式启用。

### 6. 本项结论

“官方公告源 + 独立财务源适配器 + 统一供应商健康状态”已经完成代码接入、回退逻辑、运行产物和真实只读验证；但按照当前用户选择，Tushare 处于关闭状态，不参与默认运行。下一步若要启用，需要积分达到官方接口要求并将 `TUSHARE_ENABLED` 改为 `true`，而不是继续增加未经授权的免费抓取站点。
