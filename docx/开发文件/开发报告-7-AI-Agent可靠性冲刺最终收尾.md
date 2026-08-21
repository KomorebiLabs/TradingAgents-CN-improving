# 开发报告 7：AI Agent 工程可靠性冲刺 —— 最终收尾

> 日期：2026-08-21
> 分支：`docs/agent-sprint-wrapup`（阶段 4 已提交 `dd26ddd`）
> 前置：PR #9（面试文档）、PR #10（治理文档整理）、PR #11（point-in-time 审计）、PR #12（评测+工具契约）
> 数据：GitNexus 索引 4,232 节点 / 7,998 边 / 172 clusters / 300 flows；453 个离线测试全绿

---

## 一、这份报告回答什么

项目从"能写进简历的工程系统"收尾为"面试时经得起追问的 AI Agent Runtime"。本报告说明：

1. 最终架构长什么样（基于 GitNexus 图谱审查，不是文档自我描述）；
2. 本轮冲刺到底改了什么（阶段 0/1/2/4）；
3. 收尾与封装的内容；
4. 哪些是证据、哪些是边界、哪些绝不能宣称。

---

## 二、最终架构审查（GitNexus 图谱视角）

索引重新分析后：**4,232 个符号节点、7,998 条关系边、172 个功能簇、300 条执行流**。核心符号在图谱中确认存在且有真实连接：

### 2.1 分层结构（已收口为单向依赖）

```text
cli/  ──►  tradingagents.application ──►  tradingagents.graph ──►  tradingagents.agents
                                                                    │
                                     tradingagents.ports ──────────┤
                                                                    ▼
                                     tradingagents.dataflows ──►  vendor adapters
                                                                    │
                                     tradingagents.llm_clients ────┘（provider 工厂独立）
```

图数据确认：`TradingAgentsGraph`（`tradingagents/graph/trading_graph.py`）被 `main.py`、`service.py`、`deep_analyzer.py` 等真实消费；`AnalysisService`（`tradingagents/application/service.py`）被 `eval/__main__.py` 消费——评测框架走的是与 CLI 相同的应用层入口，不是旁路。

### 2.2 关键执行流（图谱中 300 条 flow 的代表）

| 流 | 入口 | 出口 | 状态 |
|---|---|---|---|
| Screener 候选发现 | `cli/screener` | 候选股票报告 | ✅ 离线测试覆盖 |
| Analyzer 多智能体决策 | `AnalysisRequest` → `AnalysisService` → `TradingAgentsGraph.stream_analysis` | BUY/HOLD/SELL + 报告 | ✅ 图流测试覆盖 |
| Evaluation 评测 | `eval/runner.run_case_set` → `service.run` | 混淆矩阵 + 方向准确率 | ✅ 契约测试覆盖 |
| Tool 数据路由 | Tool wrapper → `route_to_vendor` → provider | 结构化文本 | ✅ 参数契约测试覆盖 |

### 2.3 状态契约（canonical）

`AgentState` 结构化块（`ticker_info` / `analyst_reports` / `debate_blocks` / `decision_blocks` / `orchestration`）为权威，平铺字段降级为兼容镜像；`schema_version` 标记迁移期契约。图谱显示 canonical 测试（`test_state_canonical.py`）作为消费者存在。

---

## 三、本轮冲刺的修改清单

### 阶段 0：证据同步（随 PR #12 合并）

- README 测试数从 439 → 453；
- README「验证与治理成果」新增 Point-in-time 审计入口；
- 消除指向未合并 `docx/` 的失效链接。

### 阶段 1：Agent Evaluation Contract（随 PR #12 合并）

| 文件 | 变更 |
|---|---|
| `tradingagents/eval/matrix.py` | 新增 `normalize_decision`（`neutral/未知/空值 → HOLD`，大小写无关）+ `decision_warning`（未知决策审计） |
| `tradingagents/eval/runner.py` | 新增 `EvaluationRecord` TypedDict：raw/normalized decision、normalization warning、confidence、Token、tool calls、latency、warnings、provider、research depth |
| `tradingagents/eval/report.py` | 报告显式渲染 `framework_ready` / `real_model_run`；`real_model_run=false` 时标注"非 LLM benchmark 结果" |
| `tradingagents/eval/cases.py` | **修复真实 bug**：`build_case_set` 在 ticker 重复时用去重前长度抽样 → `ValueError: Cannot take a larger sample than population`；改为 `min(n, len(unique))` |
| `tests/test_eval.py` | +6 测试：归一化、warning、元数据传递、request 锚定 eval_date、确定性、去重/封顶/空输入、报告边界 |

### 阶段 2：Tool Reliability + Temporal Grounding（随 PR #12 合并）

| 文件 | 变更 |
|---|---|
| `tests/test_tool_contracts.py`（新增） | 4 测试：① indicator router 保留 `curr_date`；② news router 保留 `start/end_date`；③ indicator Tool wrapper 全链路参数转发；④ news Tool wrapper 全链路参数转发。全部 stub，零网络 |
| `docs/point-in-time-audit.md` | 补充 Tool Contract 覆盖说明 |

### 阶段 4：面试材料收口（本分支 `dd26ddd` 待 PR）

| 文件 | 变更 |
|---|---|
| `README.md` | 评测行补充决策归一化/元数据/`real_model_run`；新增工具契约行；成本明确为 LLM cost；AI Agent 视角新增可靠性与评测段 |
| `docs/architecture.md` | 新增 6.4（LLM cost vs trading cost 分开）+ Section 7（Agent Evaluation & Tool Reliability：7.1 评测边界 / 7.2 Tool Contract / 7.3 失败语义）；后续章节重编号 7→8、8→9、9→10、10→11 |
| `docs/interview-notes.md` | 新增 Q14-Q18（无真实 API 如何证明 / 标签防泄漏 / Tool failure 可观测 / LLM vs trading cost / 为何不宣称准确率）；原 Q14-16 → Q19-21；测试数 439→453 |

---

## 四、收尾与封装

### 4.1 封装成"一句话可讲清"的能力

```text
一个可编排、可观测、可评估的 Agent Runtime：
  LangGraph 多阶段编排（分析师→研究→交易→风控→决策）
+ canonical AgentState（状态即契约）
+ Tool / Port / Dataflows（能力与供应商解耦）
+ Execution Events + Cost/Cache（运行可观测）
+ Evaluation Contract（输出可评测、证据边界明确）
```

### 4.2 证据分层封装

| 标签 | 内容 | 简历表述 |
|---|---|---|
| ✅ 已验证 | 453 离线测试、图流/契约/golden/parity、point-in-time 截止防御、回测产物（带限制） | "450+ 离线测试" |
| 🧱 已实现/离线验证 | 评测框架、工具契约、事件/成本/缓存护栏 | "评测框架已就绪" |
| 🧭 待验证 | 真实 LLM 评测、消融实跑、多窗口回测、成本显式化 | "真实评测未实跑" |

### 4.3 已从叙事中排除（防止喧宾夺主）

- 交易成本 `cost_bps` 生产改造 —— 延后，不进入本轮；
- 滑点/盘口/多窗口/Walk-forward —— 延后；
- vendors 全量类型化 —— 作为后续治理项，不宣称完成。

---

## 五、验证结果（本报告全部来自真实运行）

```text
完整离线测试：453 passed, 1 warning（pkg_resources 弃用，非失败）
聚焦测试：20 passed（eval + tool contracts + point-in-time）
Markdown 链接检查：通过
git diff --check：通过
GitNexus detect-changes：纯文档变更，0 受影响流程，风险 low
```

---

## 六、边界与诚实声明（必须保留）

1. **未执行真实 LLM/API 运行**。453 测试证明的是框架行为被冻结、评测数学正确、工具参数不丢失，**不证明**模型决策在真实数据上准确；
2. `82.86%` 回测是单窗口、未计成本、技术因子、存续偏差下的方法论演示，不是预测能力；
3. 上游约 99k★ 是本项目的工程基线，本项目是独立 fork 演进，未向上游提交 PR；
4. 报告口径与仓库事实必须一致：测试数、star 数、`real_model_run=false`。

---

## 七、给面试的最终定位

> 我做的是一个多智能体 LLM Agent Runtime：用 LangGraph 管编排，用 canonical AgentState 管契约，用 Tool/Port/Dataflows 管能力边界，用事件+成本+缓存管观测，用 Evaluation Contract 管评测。重构了一个 1905 行 God Class 和一个多入口的遗留系统，全程离线可验证，明确区分"代码能力 / 离线证据 / 真实业务效果"。

这条表述每一句都有仓库代码或测试支撑，面试官追问三层仍能守住。

---

## 八、待办（需用户确认）

1. ~~审批本报告~~ ✅ 已批准执行；
2. 阶段 4 分支 `docs/agent-sprint-wrapup` 的 commit（`dd26ddd`）已就绪，待 push + PR（见本报告尾部命令）；
3. ✅ 简历 Trading Agent 段落测试数已从"440+"改为"450+"，与仓库 453 对齐；
4. ✅ README 顶部上游 star 数已从 `~76k★` 更新为 `~99k★`，与简历一致。

---

## 九、最终提交命令（用户自行执行）

```bash
git add README.md docs/architecture.md docs/interview-notes.md "docx/开发文件/开发报告-7-AI-Agent可靠性冲刺最终收尾.md"
git commit -m "docs: wrap up agent reliability sprint with final development report"
git push -u origin docs/agent-sprint-wrapup
gh pr create --repo KomorebiLabs/TradingAgents-CN-improving --base main --head docs/agent-sprint-wrapup --title "docs: agent reliability sprint wrap-up" --body "..."

# 验证
venv/Scripts/python.exe -m pytest tests/ -q
git diff --cached --check
```

> ⚠️ 不要执行 `git add -A`：`README_TECH.md` 的既有修改与两个简历文件不应进入本 PR。
