# AI Agent 面试作品化文档 Implementation Plan

> **For agentic workers:** Execute this plan inline in the current session. Do not dispatch subagents, do not use a worktree, and do not commit unless the user separately requests a commit.

**Goal:** 将项目已有的 LangGraph、多智能体、工具路由、状态契约、可观测性、评测护栏和“铲屎山”重构成果，整理成面向 AI Agent / LLM 工程岗位的 README 入口、架构文档和面试问答材料。

**Architecture:** 采用增量文档层，不改变业务代码。`README.md` 只增加 AI Agent 视角的导航与核心叙事；`docs/architecture.md` 负责事实化解释系统分层、数据流、状态流和重构案例；`docs/interview-notes.md` 负责可直接复述的项目介绍、技术问答和限制性回答。三份文档共享同一套证据分层，避免数字和验证状态漂移。

**Tech Stack:** Markdown、Mermaid、Git diff 静态检查；不运行真实 LLM API，不引入依赖，不修改 Python 业务代码。

## Global Constraints

- 文档正文使用中文，保留 `LangGraph`、`StateGraph`、`AgentState`、`Tool Router`、`MarketDataPort` 等英文技术术语。
- `README.md` 只做增量修改，保留用户已有的未提交内容。
- 不修改业务代码，不删除文件，不整理现有删除项或未跟踪项。
- 不运行真实 API、真实 LLM、消融实跑、正确性评测实跑、多窗口回测或交易成本改造。
- 所有数字必须来自当前源码、测试或 `reports/` 产物，并附带适用边界。
- 统一区分：`✅ 已验证`、`🧱 已实现 / 离线验证`、`🧭 待验证`、`⚠️ 限制`。
- “屎山”故事必须写成增量架构治理案例，不写成推倒重写或夸大宣传。
- 不提交 Git；完成后只保留工作区变更供用户审阅。

---

## 文件地图

- Modify: `README.md` — 在现有项目亮点区之后增加 AI Agent / LLM 工程入口和深度文档链接；不重写已有亮点。
- Create: `docs/architecture.md` — 事实化说明系统分层、LangGraph 执行图、状态契约、工具与数据链、可观测性、Screener/Analyzer 关系、重构案例和验证边界。
- Create: `docs/interview-notes.md` — 60 秒介绍、AI Agent 技术问答、重构故事、证据边界和诚实回答话术。
- Create: `docs/superpowers/specs/2026-08-20-ai-agent-interview-docs-design.md` — 已完成并获用户确认的设计记录，不再改动。
- Create: `docs/superpowers/plans/2026-08-20-ai-agent-interview-docs.md` — 本实施计划。

---

### Task 1: 固定文档事实与证据口径

**Files:**
- Read: `README.md`
- Read: `README_TECH.md`
- Read: `tradingagents/application/contracts.py`
- Read: `tradingagents/application/service.py`
- Read: `tradingagents/graph/setup.py`
- Read: `tradingagents/graph/trading_graph.py`
- Read: `tradingagents/agents/utils/agent_states.py`
- Read: `tradingagents/application/events.py`
- Read: `tradingagents/ports/market_data.py`
- Read: `tradingagents/dataflows/interface.py`
- Read: `tradingagents/llm_clients/factory.py`
- Read: `tradingagents/harness/`
- Read: `docx/屎山清理/屎山报告-4-重构施工记录.md`
- Read: `docx/屎山清理/屎山报告-5-异常治理清单.md`
- Read: `docx/开发文件/交接报告-给Claude.md`
- Read: `docx/开发文件/治理报告-6-残余不足与治理方案.md`

**Interfaces:**
- Consumes: 当前源码、已读的重构施工记录和交接/治理报告。
- Produces: 写作时可引用的符号、文件路径、测试数字和限制清单；不产生代码变更。

- [x] **Step 1: 建立事实表**

  将内容分为四列：事实、来源、验证状态、限制。例如：

  | 事实 | 来源 | 状态 | 限制 |
  |---|---|---|---|
  | `stream_analysis()` 统一图流 | `trading_graph.py`、施工记录 | 🧱 离线验证 | 本轮不做真实 LLM 运行 |
  | 结构化状态为 canonical | `agent_states.py`、canonical 测试 | ✅ 契约验证 | legacy 平铺字段仍兼容 |
  | `82.86%` 回测收益 | `reports/backtest/`、交接报告 | ✅ 产物存在 | 单窗口、未计成本、存续偏差 |

- [x] **Step 2: 记录历史基线和当前状态的区别**

  将报告 1/2 的 `0 测试`、`171 处异常`标为历史诊断基线，不把它们写成当前状态；将报告 4/5 和交接报告中的后续数字作为施工记录或当前治理边界，并对存在不同快照的数字使用明确日期/阶段描述。

- [x] **Step 3: 确认引用路径**

  所有新增文档中的源码引用使用仓库相对路径和符号名；README 只引用稳定的模块入口，不引用已退役的旧路径作为当前架构。

---

### Task 2: 编写系统架构文档

**Files:**
- Create: `docs/architecture.md`

**Interfaces:**
- Consumes: Task 1 的事实表。
- Produces: 面试官可从入口读到实现边界的架构文档；后续 README 和面试笔记链接到本文件。

- [x] **Step 1: 写入项目定位和证据标签说明**

  开头明确：这是面向 A 股的多智能体 LLM 交易框架；本文件描述当前代码结构与离线验证边界，不声称本轮完成真实 API 运行。定义四个标签：`✅ 已验证`、`🧱 已实现 / 离线验证`、`🧭 待验证`、`⚠️ 限制`。

- [x] **Step 2: 写入整体分层 Mermaid 图和文本降级图**

  Mermaid 图至少包含以下节点和边：

  ```mermaid
  flowchart TD
      CLI[CLI / Questionnaire] --> APP[Application Contracts + AnalysisService]
      APP --> GRAPH[TradingAgentsGraph / LangGraph StateGraph]
      GRAPH --> AGENTS[Analysts / Researchers / Trader / Risk / Portfolio]
      AGENTS --> STATE[AgentState canonical blocks]
      AGENTS --> TOOLS[Tool Router / Tool Assembly]
      TOOLS --> PORTS[MarketDataPort]
      PORTS --> DATA[dataflows / vendor adapters]
      GRAPH --> EVENTS[Execution Events]
      EVENTS --> UI[Live Dashboard / Summary]
      EVENTS --> OBS[Harness: tokens, cost, latency, errors]
      GRAPH --> REPORTS[Reports]
  ```

  Mermaid 图之后提供同一方向的纯文本版本，说明 UI 不直接访问图内部，工具不直接绑定具体供应商。

- [x] **Step 3: 写入 Analyzer LangGraph 执行链**

  解释 `GraphSetup.setup_graph()` 的阶段装配：选定分析师 → 分析师节点 → 研究辩论 → Trader → 风控辩论 → Portfolio Manager。标明 quick model 用于常规分析，deep model 用于复杂裁决；不要把节点并行性写成未经源码确认的实现细节。

- [x] **Step 4: 写入 AgentState canonical 数据流**

  使用以下结构说明状态契约：

  ```text
  ticker_info
  analyst_reports
  debate_blocks
  decision_blocks
  semantic_prompt_slots / screener_context
  ```

  说明结构化块是 canonical，legacy 平铺字段是兼容镜像；`schema_version` 用于迁移期契约；写入、读取、日志和 UI 读取的责任边界分别落到对应文件。

- [x] **Step 5: 写入 Tool Router → Ports → Dataflows 链**

  解释 Agent 通过工具获取能力，工具通过路由/端口访问数据，数据层再选择供应商或降级路径。说明 `MarketDataPort` 消除了 `dataflows → screener` 的直接依赖，并使共享限流器/缓存可复用；不要宣称所有 vendors 错误已经完成类型化。

- [x] **Step 6: 写入 LLM Client 和 Harness**

  说明 `llm_clients.factory` 负责 provider 创建和模型目录约束，quick/deep 是任务分层而非模型质量保证；Harness 记录 Token、成本、调用、延迟、错误、Skill 和决策节点事件。明确本轮没有真实 API 运行数据。

- [x] **Step 7: 写入 Screener 与 Analyzer 的边界**

  说明 Screener 的候选发现链和 Analyzer 的单股票深度决策链分别承担什么职责，以及 Screener context 如何作为分析状态的输入之一；不要把筛选评分等同于 LLM 决策准确率。

- [x] **Step 8: 写入“铲屎山”重构案例**

  按“诊断根因 → 选择收口顺序 → 逐步验证 → 保持行为”的结构写入四个案例：静默 ImportError fallback、三套图驱动、AgentState 双写、数据层反向依赖与 1905 行 God Class。明确这是一段历史施工记录，不把早期基线数字当作当前状态。

- [x] **Step 9: 写入验证边界和面试讲解顺序**

  提供测试、golden、parity、评测框架的职责划分；列出未执行的真实 API、消融、正确性评测、多窗口回测和成本改造；最后给出 5 分钟讲解顺序：问题 → 架构 → 一条数据流 → 一个重构案例 → 证据与限制。

- [x] **Step 10: 做文档内部检查**

  检查 Mermaid 节点名称与源码名称一致，检查所有内部链接和文件路径，检查每个数字是否有边界；不运行网络调用。

---

### Task 3: 编写 AI Agent 面试问答文档

**Files:**
- Create: `docs/interview-notes.md`

**Interfaces:**
- Consumes: `docs/architecture.md` 和 Task 1 的事实表。
- Produces: 可直接复述的面试材料，所有技术结论与架构文档保持一致。

- [x] **Step 1: 写入 60 秒项目介绍**

  使用以下信息顺序：项目目标 → Agent 流程 → 工程化难点 → 治理成果 → 证据边界。结尾明确本轮没有执行真实 API 链路，避免把离线护栏说成线上效果。

- [x] **Step 2: 写入 LangGraph 和多智能体问答**

  覆盖：为什么使用 StateGraph、阶段如何路由、分析师/研究员/Trader/风控如何分工、quick/deep 如何分配、状态如何在阶段之间传递。每个回答同时给出“短答”和“追问展开点”。

- [x] **Step 3: 写入工具、数据和错误治理问答**

  覆盖：为什么需要 Tool/Port 分层、如何避免 Agent 直接 import vendor、供应商失败如何降级、`VendorError` 解决了什么、哪些 vendors 仍有治理空间。不得承诺 vendors 全部已类型化。

- [x] **Step 4: 写入状态、可观测性和评测问答**

  覆盖：canonical AgentState、schema version、事件流、Live Dashboard、Token/成本/延迟、离线测试/golden/parity/eval 的职责边界。明确评测框架“已就绪”和“已产生真实评测结论”的差别。

- [x] **Step 5: 写入“铲屎山” STAR 故事**

  用 Situation / Task / Action / Result 结构描述：历史系统存在多个入口和执行驱动 → 先收口入口 → 统一 stream API → canonical state → Port 和 God Class 拆分 → 用增量测试验证。Result 只使用实际有记录的结构变化和测试护栏，不夸大业务收益。

- [x] **Step 6: 写入敏感数字与限制性回答**

  为 `82.86%`、夏普 `2.17`、超额 `+56.57%` 准备诚实回答：它们是单段、未计成本、技术因子、存在存续偏差的工程实验结果，不代表 LLM 或策略的普遍预测能力。为“真实 API 是否跑过”准备明确回答：本轮没有跑，不把框架就绪说成端到端验证。

- [x] **Step 7: 写入当前不足和下一步**

  列出 point-in-time 审计、多窗口回测、交易成本、供应商漂移、异常边界和 golden 业务覆盖等后续方向；标明它们是治理计划，不是本轮交付。

- [x] **Step 8: 做问答一致性检查**

  逐项对照 `docs/architecture.md`，确保同一概念的名称、验证状态和限制句完全一致；删除所有暗示真实 API 结果的措辞。

---

### Task 4: 增量更新 README 入口

**Files:**
- Modify: `README.md`，现有“项目亮点”区之后、开发阶段表格之前

**Interfaces:**
- Consumes: `docs/architecture.md` 和 `docs/interview-notes.md` 的最终标题与链接。
- Produces: 面试官从 README 第一屏即可进入 AI Agent 深度材料的导航入口。

- [x] **Step 1: 保留用户已有项目亮点区**

  不重写、不删除当前 README 中已有的回测、敏感性、439 测试、供应商健康和重构数字；只在其后插入新段落。

- [x] **Step 2: 插入 AI Agent 工程视角摘要**

  摘要用 3-5 个 bullet 说明：LangGraph 状态编排、多智能体阶段协作、Tool/Port 数据隔离、事件/成本可观测性、离线契约测试与增量重构。明确“真实 API 端到端本轮未执行”。

- [x] **Step 3: 插入深度文档导航**

  使用相对链接：

  ```markdown
  - [系统架构与数据流](docs/architecture.md)
  - [AI Agent 面试导航](docs/interview-notes.md)
  ```

- [x] **Step 4: 检查 README 差异边界**

  运行 `git diff -- README.md`，确认 diff 只包含新的 AI Agent 入口，不覆盖用户原有未提交的项目亮点改动。

---

### Task 5: 静态验证与交付审阅

**Files:**
- Read: `README.md`
- Read: `docs/architecture.md`
- Read: `docs/interview-notes.md`
- Read: `docs/superpowers/specs/2026-08-20-ai-agent-interview-docs-design.md`

**Interfaces:**
- Consumes: Tasks 2-4 的三份最终文档。
- Produces: 可供用户审阅的工作区变更；不创建提交。

- [x] **Step 1: 检查空链接和拼写路径**

  在仓库根目录运行：

  ```bash
  python - <<'PY'
  from pathlib import Path
  import re

  files = [Path('README.md'), Path('docs/architecture.md'), Path('docs/interview-notes.md')]
  missing = []
  for path in files:
      text = path.read_text(encoding='utf-8')
      for target in re.findall(r'\]\(([^)#]+)', text):
          if target.startswith(('http://', 'https://', '#', 'mailto:')):
              continue
          resolved = (path.parent / target).resolve()
          if not resolved.exists():
              missing.append(f'{path}: {target}')
  if missing:
      raise SystemExit('\n'.join(missing))
  print('markdown relative links: OK')
  PY
  ```

  Expected: `markdown relative links: OK`。

- [x] **Step 2: 检查差异空白**

  ```bash
  git diff --check
  ```

  Expected: no output and exit code 0。

- [x] **Step 3: 检查禁用措辞和未验证声明**

  ```bash
  python - <<'PY'
  from pathlib import Path

  text = '\n'.join(Path(p).read_text(encoding='utf-8') for p in (
      'README.md', 'docs/architecture.md', 'docs/interview-notes.md'
  ))
  required = ['真实 API', '未执行', '82.86%', 'AgentState', 'stream_analysis']
  missing = [item for item in required if item not in text]
  if missing:
      raise SystemExit(f'missing evidence-boundary terms: {missing}')
  print('evidence-boundary wording: OK')
  PY
  ```

  Expected: `evidence-boundary wording: OK`。

- [x] **Step 4: 检查最终变更范围**

  ```bash
  git status --short
  git diff --stat
  git diff -- README.md docs/architecture.md docs/interview-notes.md
  ```

  Expected: 只有 `README.md` 的增量修改、两个新增文档和设计/计划文件；不应出现 Python 业务文件的修改或删除操作。

- [x] **Step 5: 向用户交付审阅结果**

  报告：新增和修改的文件、静态检查结果、未运行真实 API 的事实，以及工作区中原有删除/未跟踪项未被触碰。不要声称测试或端到端链路已通过。

## Completion Checklist

- [x] `docs/architecture.md` 已完成并包含 Mermaid + 文本降级图。
- [x] `docs/interview-notes.md` 已完成并包含 60 秒介绍、问答和限制性回答。
- [x] `README.md` 只新增 AI Agent 入口，没有覆盖已有亮点。
- [x] “铲屎山”故事包含根因、治理顺序、公开 API 保持和离线验证。
- [x] 所有数字和验证状态都有边界说明。
- [x] Markdown 相对链接检查通过。
- [x] `git diff --check` 通过。
- [x] 未运行真实 API，未修改业务代码，未删除文件，未提交 Git。
