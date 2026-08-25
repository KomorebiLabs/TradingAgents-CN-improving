# TradingAgents-CN Future Doing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `executing-plans` to implement one work package at a time. For a package with three or more independent tasks, `subagent-driven-development` may be used, but the main Agent must review every result. All steps use checkbox syntax for tracking.

**Goal:** 把 [Future.md](Future.md) 中的长期方向拆成可以独立建分支、实施、验证和提交的工作包，使未来维护者无需重新读取整个仓库即可开工。

**Architecture:** 继续维护现有 Analyzer 与 Screener 两条主链，不新建平行框架。数据改进进入 `ports/dataflows`，证据改进进入 `eval/ablation/backtest`，运行验收复用现有 CLI 与 artifact；所有高风险共享入口在修改前必须通过 GitNexus impact 分析。

**Tech Stack:** Python 3.10+、LangGraph、LangChain、Typer、pandas、pytest、uv、GitHub Actions、Agnes `agnes-2.5-flash`、GitNexus。

---

## 0. 使用说明

这是一份执行手册，不是完成情况报告。除非工作包的“完成证据”已经真实产生，否则不要勾选完成，也不要修改基线数字。

### 0.1 一次只领取一个工作包

1. 从“工作包总表”选择依赖已经满足的任务；
2. 阅读该工作包列出的文件，不要加载整个仓库；
3. 运行 GitNexus query/context；修改 symbol 前运行 upstream impact；
4. 建立该工作包指定的独立分支；
5. 按测试先行顺序实施；
6. 完成专项测试、全量测试和真实验收；
7. 更新本文件中该工作包的状态与证据；
8. 单独提交 PR，不顺手夹带其他工作包。

### 0.2 状态格式

每个工作包标题下使用以下记录：

```text
状态：NOT_STARTED
负责人：未分配
开始提交：无
完成提交：无
PR：无
证据等级：无
artifact：无
```

允许状态只有 `NOT_STARTED / IN_PROGRESS / BLOCKED / VERIFIED / SUPERSEDED`。完成时必须同时补齐 commit、PR、测试结果和 artifact 路径。

### 0.3 通用开工命令

```powershell
git status --short --branch
git fetch fork
git log --oneline --decorate -5
venv\Scripts\python.exe -m pytest tests/ -q
venv\Scripts\python.exe -m compileall -q tradingagents cli tests
```

预期基线：工作区干净、全量离线测试不少于封箱基线 `682 passed`。如果测试减少或失败，先解释基线变化，不直接开始开发。

### 0.4 通用完成检查

```powershell
venv\Scripts\python.exe -m pytest tests/ -q
venv\Scripts\python.exe -m compileall -q tradingagents cli tests
git diff --check
git status --short
```

随后执行 GitNexus `detect_changes(scope="compare", base_ref="main")`。出现 HIGH 或 CRITICAL 风险时，PR 必须列出受影响流程和针对性回归测试。

### 0.5 真实调用预算

- 没有用户明确授权时，不执行批量 Agnes 调用；
- 首次 smoke 最多 1 个 ticker、1 次重复、research depth 1；
- eval 首批最多 5 个案例，ablation 首批最多 1 ticker × 2 配置 × 2 次；
- 每次运行设置可观察的超时，连续两次出现同一错误即停止；
- 不读取、打印、提交 `.env`；日志和 artifact 必须脱敏；
- 用户当前要求使用 Agnes，不得静默切到 DeepSeek。

## 1. 工作包总表

| ID | 工作包 | 优先级 | 依赖 | 建议分支 | 主要产物 |
|---|---|---:|---|---|---|
| F0-01 | 恢复开发基线审计 | P0 | 无 | 无需分支 | 新基线记录 |
| F0-02 | 修复 eval/ablation provider 与证据语义 | P0 | F0-01 | `codex/future-eval-truth-contract` | 可信实验 runner |
| F1-01 | Screener 五交易日真实验收 | P0 | F0-01 | `codex/future-screener-multiday` | 5 日 acceptance artifact |
| F1-02 | HumanGate 与 checkpoint 真实恢复验收 | P0 | F0-01 | `codex/future-hitl-recovery` | pause/resume/abort 证据 |
| F2-01 | 可复现依赖、环境示例与 CI | P0 | F0-01 | `codex/future-reproducible-runtime` | extras、锁文件、Windows smoke |
| F2-02 | Provider capability manifest | P0 | F2-01 | `codex/future-provider-contracts` | 供应商能力契约 |
| F2-03 | Provenance sidecar 与 PIT 门禁 | P0 | F2-02 | `codex/future-data-provenance` | 数据来源与时间证据 |
| F2-04 | 财务主源选型与 shadow 验证 | P0 | F2-02、用户选择 | `codex/future-financial-provider` | ADR、适配器、对比报告 |
| F3-01 | Golden cases v1 | P0 | F2-03 | `codex/future-golden-cases` | 冻结评测集 |
| F3-02 | Agnes 正确性小样本评测 | P0 | F0-02、F3-01、用户预算 | `codex/future-live-eval` | 混淆矩阵与失败案例 |
| F3-03 | 多窗口、成本与历史成分股回测 | P1 | F2-03 | `codex/future-backtest-evidence` | walk-forward 报告 |
| F3-04 | 消融、敏感性与置信度校准 | P1 | F0-02、F3-01、用户预算 | `codex/future-ablation-calibration` | 多智能体增益证据 |
| F4-01 | 节点级 Token/时延优化 | P1 | F3-02 小基线 | `codex/future-llm-efficiency` | 优化前后对照 |
| F5-01 | 每日研究调度与差异报告 | P1 | F1-01、F2-03 | `codex/future-daily-research` | 可重入日任务 |
| F5-02 | 模拟组合与风险预算 | P2 | F3-03 | `codex/future-paper-portfolio` | paper portfolio |
| F5-03 | 本地运营与证据面板 | P2 | F1-01、F4-01 | `codex/future-ops-dashboard` | 静态 HTML / 本地面板 |

推荐顺序：`F0-01 → F0-02 + F1-01 + F1-02 + F2-01 → F2-02 → F2-03/F2-04 → F3 → F4 → F5`。

## 2. F0-01：恢复开发基线审计

状态：`NOT_STARTED`。此包默认只读，不创建 PR，预计 30～60 分钟。

**目标：** 确认未来恢复开发时，代码、文档、供应商和测试基线是否仍与 2026-08-25 封箱状态一致。

**只读文件：**

- `Future.md`
- `Future Doing.md`
- `docx/开发文件/封箱总结-项目完成情况与面试验收.md`
- `docs/architecture.md`
- `docs/point-in-time-audit.md`
- `pyproject.toml`
- `.github/workflows/ci.yml`

- [ ] **步骤 1：确认分支和远端差异**

```powershell
git status --short --branch
git fetch fork
git log --oneline --decorate -10
git diff --stat fork/main...HEAD
```

预期：明确当前 HEAD、main 与未提交修改；不自动 reset 或覆盖用户工作。

- [ ] **步骤 2：检查 GitNexus 新鲜度**

读取 `gitnexus://repo/TradingAgents-CN-improving/context`。如果索引落后，运行：

```powershell
node .gitnexus/run.cjs analyze
```

预期：索引对应当前 HEAD，能够 query Analyzer、Screener 和 provider 路由。

- [ ] **步骤 3：运行离线基线**

```powershell
venv\Scripts\python.exe -m pytest tests/ -q
venv\Scripts\python.exe -m compileall -q tradingagents cli tests
```

预期：测试不少于 `682 passed`；若测试数变化，记录新增、删除和原因。

- [ ] **步骤 4：运行不消耗 LLM 的能力检查**

```powershell
venv\Scripts\python.exe -m tradingagents screener run --help
venv\Scripts\python.exe -m tradingagents analyze --help
venv\Scripts\python.exe -m tradingagents.screener.acceptance --reports-dir reports\Screener --required-days 5 --output reports\Screener\acceptance_latest.json
```

acceptance 在未满 5 日时退出码 1 是预期行为，不得改 artifact 伪造成功。

- [ ] **步骤 5：形成基线记录**

在本工作包状态区记录日期、HEAD、测试数、acceptance 天数、Python 版本、GitNexus 节点数和已知阻塞。只有事实变化时才修改文档并提交 PR。

**停止条件：** 发现未解释的业务代码修改、测试失败、密钥泄露或主分支尚未合并封箱 PR时，停止后续工作包并先处理基线。

## 3. F0-02：修复 eval/ablation provider 与证据语义

状态：`NOT_STARTED`。这是未来恢复开发后第一个推荐代码 PR。

**问题：** `tradingagents/eval/__main__.py`、`eval/runner.py`、`ablation/__main__.py` 和 `ablation/runner.py` 仍默认 DeepSeek；真实 eval CLI 未给 `build_report` 传 `real_model_run=True`；报告中的随机基线文字也不够严谨。

**Files:**

- Modify: `tradingagents/eval/__main__.py`
- Modify: `tradingagents/eval/runner.py`
- Modify: `tradingagents/eval/report.py`
- Modify: `tradingagents/ablation/__main__.py`
- Modify: `tradingagents/ablation/runner.py`
- Test: `tests/test_eval.py`
- Test: `tests/test_ablation.py`

- [ ] **步骤 1：执行影响分析**

对 `run_case_set`、`build_request`、eval `main`、ablation `main` 和 `build_report` 分别运行 upstream impact。预期影响局限在实验 CLI、runner、报告和测试；若触及 Analyzer 主执行流程，先重新拆包。

- [ ] **步骤 2：先写失败测试**

测试必须覆盖：

```python
def test_ablation_inherits_provider_from_environment(monkeypatch):
    from tradingagents.ablation.configs import build_matrix
    from tradingagents.ablation.runner import build_request

    monkeypatch.setenv("LLM_PROVIDER", "agnes")
    request = build_request(
        "600519",
        "2026-08-20",
        build_matrix()[2],
        provider=None,
    )
    assert request.llm_provider == "agnes"


def test_eval_report_can_mark_real_model_run():
    from tradingagents.eval.report import build_report

    markdown = build_report(
        "live",
        [{"label": "BUY", "decision": "BUY"}],
        real_model_run=True,
    )
    assert "Real model run: True" in markdown
    assert "not an LLM benchmark result" not in markdown
```

可以按现有 fixture 风格替换辅助函数名，但断言语义不能降低。

- [ ] **步骤 3：统一 provider 解析**

runner 不再使用字符串字面量 `deepseek` 作为兜底。使用 `AnalysisRequest.default_for(ticker, trade_date)` 获取环境和默认配置，再通过 `dataclasses.replace` 覆盖研究深度、分析师和显式 provider：

```python
base = AnalysisRequest.default_for(ticker, trade_date)
request = replace(
    base,
    selected_analysts=config.selected_analysts,
    research_depth=config.research_depth,
    llm_provider=provider or base.llm_provider,
)
```

eval runner 使用同一原则。CLI 的 `--provider` 默认值改为 `None`，帮助文本说明“不传时读取 `LLM_PROVIDER` / 项目默认配置”。

- [ ] **步骤 4：修复报告真实性**

真实 eval CLI 调用：

```python
build_report(
    title,
    results,
    horizon_days=args.horizon,
    note="Real LLM runs — token costs apply.",
    framework_ready=True,
    real_model_run=True,
)
```

删除“随机策略固定约 50%”之类未经类别分布支持的表述，改为报告多数类基线、样本量和小样本限制；如果尚未实现多数类基线，就只保留小样本限制，不发明数字。

- [ ] **步骤 5：验证**

```powershell
venv\Scripts\python.exe -m pytest tests\test_eval.py tests\test_ablation.py tests\test_agnes_provider.py -q
venv\Scripts\python.exe -m pytest tests\ -q
venv\Scripts\python.exe -m compileall -q tradingagents cli tests
git diff --check
```

本包不需要真实 Agnes 调用。

**完成定义：** 代码中实验路径不再隐式选择 DeepSeek；真实与离线报告标签一致；所有测试通过。

**建议提交：** `fix(eval): 统一Agnes配置继承与真实实验标签`

## 4. F1-01：Screener 五交易日真实验收

状态：`NOT_STARTED`，封箱基线已有 2/5 个不同交易日。本包首先是运行任务，不预设代码修改。

**Files:**

- Execute: `tradingagents/screener/acceptance.py`
- Inspect on failure: `tradingagents/screener/engine.py`
- Inspect on failure: `tradingagents/screener/report.py`
- Test: `tests/test_screener_acceptance_monitor.py`
- Artifact: `reports/Screener/<run_id>/screening_result.json`
- Artifact: `reports/Screener/<run_id>/vendor_health.json`
- Artifact: `reports/Screener/acceptance_latest.json`

- [ ] **步骤 1：每个真实交易日运行一次低成本 FOCUSED**

```powershell
$tradeDate = Get-Date -Format 'yyyy-MM-dd'
venv\Scripts\python.exe -m tradingagents screener run `
  --mode FOCUSED `
  --focus-type index `
  --focus-value 000300 `
  --date $tradeDate `
  --stagea-max-input 5 `
  --stageb-max-input 3 `
  --max-stocks 3 `
  --no-deep
```

若当天不是交易日，runtime guard 拒绝运行是正确结果，不使用 `--allow-weekend` 计入正式验收。

- [ ] **步骤 2：运行 acceptance**

```powershell
venv\Scripts\python.exe -m tradingagents.screener.acceptance `
  --reports-dir reports\Screener `
  --required-days 5 `
  --output reports\Screener\acceptance_latest.json
```

- [ ] **步骤 3：逐日人工抽查**

确认 `trade_date`、`completed_at`、`run_id`、配置快照、股票池来源、vendor health、候选资格和 stale source 门禁。没有候选不是失败；过期或未验证证据获得正式推荐资格才是失败。

- [ ] **步骤 4：失败分流**

- `insufficient_distinct_trade_days`：等待新的真实交易日；
- provider 失败但正确降级：记录，不立即改策略；
- artifact 缺字段：先写 acceptance 失败测试，再修 artifact；
- stale formal recommendation：冻结正式推荐，作为独立 P0 修复 PR；
- 超时或停滞：保存最后心跳与 provider health，再定位对应阶段。

**完成定义：** `distinct_trade_days >= 5`、`passed=true`，五日均无 artifact 失败，并形成一页汇总说明。该证据等级是 `MULTI_DAY_VERIFIED`，不是策略有效性证明。

## 5. F1-02：HumanGate 与 checkpoint 真实恢复验收

状态：`NOT_STARTED`。需要用户在终端选择和批准真实 Agnes Token。

**Files:**

- Inspect/modify if needed: `cli/analyze/run_impl.py`
- Inspect/modify if needed: `tradingagents/application/service.py`
- Inspect/modify if needed: `tradingagents/graph/trading_graph.py`
- Inspect/modify if needed: `tradingagents/graph/setup.py`
- Test: `tests/test_phase3.py`
- Test: `tests/test_run_resume.py`

- [ ] **步骤 1：先跑离线 HITL 契约**

```powershell
venv\Scripts\python.exe -m pytest tests\test_phase3.py tests\test_run_resume.py -q
```

- [ ] **步骤 2：确认 Agnes 配置但不输出密钥**

确认 `.env` 中 provider/model 为 Agnes，禁止执行 `Get-Content .env`。只允许通过程序输出 provider 和 model 名，不输出 key。

- [ ] **步骤 3：完成 comment → resume**

```powershell
venv\Scripts\python.exe -m tradingagents analyze --ticker 600519 --date 2026-08-20 --hitl
```

在 HumanGate 选择 `comment`，输入不含数字篡改的风险偏好说明。保存 run-id、暂停事件、comment、恢复事件、最终决策和报告路径。

- [ ] **步骤 4：完成中断恢复**

另起一次运行，在 HumanGate 前安全中断，记录 run-id，然后执行：

```powershell
$runId = Read-Host '输入刚才终端记录的 run-id'
venv\Scripts\python.exe -m tradingagents analyze --resume $runId
```

这里的 run-id 必须来自刚才真实运行，不能使用文档示例值。确认已完成节点没有重复计费。

- [ ] **步骤 5：完成 abort**

另起一次 `--hitl` 运行，在 HumanGate 选择 `abort`。确认生成 `abandoned.json`，最终状态不被伪装成正常完成。

- [ ] **步骤 6：只有真实失败时才改代码**

修改前分别对 `create_human_gate_node`、`AnalysisService.resume_run`、`TradingAgentsGraph.stream_analysis` 运行 impact。先把真实失败固化为离线回归测试，再做最小修复。

**完成定义：** comment/resume、故障恢复和 abort 均有脱敏 artifact；恢复不重复执行已完成节点；状态语义准确。

## 6. F2-01：可复现依赖、环境示例与 CI

状态：`NOT_STARTED`。

**Files:**

- Modify: `pyproject.toml`
- Regenerate: `uv.lock`
- Modify: `.env.example`
- Modify: `.github/workflows/ci.yml`
- Modify: `docs/demo-runbook.md`
- Test: `tests/test_smoke_imports.py`
- Test: `tests/test_agnes_provider.py`

- [ ] **步骤 1：采集当前可用版本**

```powershell
venv\Scripts\python.exe -m pip show akshare baostock tushare yfinance
uv lock --check
```

记录真实可用版本与缺失包，不猜版本号。

- [ ] **步骤 2：先写 extras smoke 测试**

测试标准安装必须可导入核心包；数据 extra 环境必须让 `check_libraries()` 对声明的库返回 true；Tushare 保持独立可选 extra，不因未安装阻断核心 CI。

- [ ] **步骤 3：定义 optional dependencies**

在 `pyproject.toml` 增加清晰分组：

```toml
[project.optional-dependencies]
data-cn = ["akshare", "baostock"]
tushare = ["tushare"]
dev = ["pytest", "build"]
```

实施时把步骤 1 验证过的兼容版本约束写入，而不是保留无约束示例；随后运行 `uv lock`。

- [ ] **步骤 4：补全环境示例**

`.env.example` 增加以下注释组合，不改变用户真实 `.env`：

```dotenv
# LLM_PROVIDER=agnes
# DEEP_THINK_LLM=agnes-2.5-flash
# QUICK_THINK_LLM=agnes-2.5-flash
# AGNES_API_KEY=
# TUSHARE_ENABLED=false
# TUSHARE_TOKEN=
```

- [ ] **步骤 5：分层 CI**

- Ubuntu Python 3.10/3.11：`uv sync --locked --extra dev` 后跑离线测试；
- Windows Python 3.10：核心 import、CLI help 和小型离线 smoke；
- provider live probe：单独 scheduled/manual workflow，缺少 secrets 时 skip，不阻塞 PR；
- wheel build：继续保留。

- [ ] **步骤 6：干净环境验证**

在临时虚拟环境分别验证核心安装和 `data-cn` extra。预期核心不要求 Tushare，完整数据 extra 能通过 capability import 检查。

**完成定义：** 本地与 CI 使用同一锁文件；Windows/Linux smoke 通过；文档能明确告诉用户安装哪个 extra；无密钥进入 Git。

## 7. F2-02：Provider capability manifest

状态：`NOT_STARTED`。

**Files:**

- Create: `tradingagents/dataflows/provider_capabilities.py`
- Modify: `tradingagents/screener/capability.py`
- Modify: `tradingagents/dataflows/interface.py`
- Create: `tests/test_provider_capabilities.py`
- Update: `docs/point-in-time-audit.md`

- [ ] **步骤 1：影响分析**

对 `check_libraries`、`run_live_probes`、`get_vendor` 和 `route_to_vendor` 运行 impact。`route_to_vendor` 是共享枢纽，预计风险较高；本包只读取 manifest，不改变返回值和降级顺序。

- [ ] **步骤 2：先定义契约测试**

每个启用 provider 必须声明：provider、category、method、dependency、auth mode、market、history support、PIT level、rate-limit note。未知 method 必须返回显式 `NOT_AUDITED`，不能默认为 SAFE。

- [ ] **步骤 3：实现不可变能力模型**

```python
@dataclass(frozen=True)
class ProviderCapability:
    provider: str
    category: str
    methods: tuple[str, ...]
    dependency: str | None
    auth_mode: str
    markets: tuple[str, ...]
    history_support: str
    pit_level: str
    supports_published_at: bool
    notes: str = ""
```

`pit_level` 只允许 `SAFE / CONDITIONAL / REALTIME_ONLY / NOT_AUDITED`。

- [ ] **步骤 4：接入 capability 输出**

`build_capability_summary` 把静态能力与真实 probe 分开：静态能力回答“理论支持什么”，probe 回答“此刻能否调用”。禁止用一次 probe 成功把 PIT 等级升级为 SAFE。

- [ ] **步骤 5：验证与文档**

```powershell
venv\Scripts\python.exe -m pytest tests\test_provider_capabilities.py tests\test_data_access_split.py tests\test_interface_routing.py -q
venv\Scripts\python.exe -m pytest tests\ -q
```

**完成定义：** 所有正式路由方法可查询能力；manifest 与 probe 不混淆；未知项失败关闭。

## 8. F2-03：Provenance sidecar 与 PIT 门禁

状态：`NOT_STARTED`。这是高风险数据主链修改，建议拆成两个 PR：记录 sidecar，再启用历史门禁。

**Files:**

- Create: `tradingagents/dataflows/provenance.py`
- Create: `tradingagents/dataflows/snapshot_store.py`
- Modify: `tradingagents/dataflows/interface.py`
- Modify: `tradingagents/application/service.py`
- Modify: `tradingagents/screener/report.py`
- Create: `tests/test_data_provenance.py`
- Extend: `tests/test_point_in_time.py`

- [ ] **步骤 1：定义 sidecar，不改变 provider 返回类型**

```python
@dataclass(frozen=True)
class ProvenanceRecord:
    provider: str
    method: str
    ticker: str | None
    as_of: str | None
    period_end: str | None
    published_at: str | None
    retrieved_at: str
    pit_status: str
    content_sha256: str
    source_id: str | None = None
```

使用 run-scoped/context-local recorder，避免并发运行互相污染。第一阶段只追加记录，不把所有字符串/DataFrame 接口一次性改成 wrapper。

- [ ] **步骤 2：先写记录测试**

覆盖成功、空数据、schema error、fallback、多次运行隔离和秘密脱敏。相同输入内容哈希必须稳定；错误文本不参与原始内容哈希。

- [ ] **步骤 3：在 `route_to_vendor` 记录 provenance**

在每次真实 provider 返回后记录 provider/method/as_of/retrieved_at/hash；无法获得 `published_at` 时必须为 null，并按 manifest 保留 `CONDITIONAL` 或 `REALTIME_ONLY`。

- [ ] **步骤 4：建立本地快照存储**

默认目录使用 `~/.tradingagents/snapshots/`，按 `provider/method/ticker/as_of/content_sha256` 存储。提供 `off / record / replay` 三种模式；默认 `off`，避免悄悄改变当前行为。

- [ ] **步骤 5：启用历史门禁**

只有调用方明确声明 historical evaluation 时才要求 PIT SAFE。若关键方法为 `REALTIME_ONLY` 或缺少公告时间，返回结构化 `INSUFFICIENT_PIT_EVIDENCE`，而不是退回最新快照。

- [ ] **步骤 6：artifact 接入**

Analyzer 与 Screener 报告新增 provenance sidecar 路径、关键源摘要和 PIT 失败原因。不要把完整原始供应商响应塞进主 JSON。

- [ ] **步骤 7：验证**

```powershell
venv\Scripts\python.exe -m pytest tests\test_data_provenance.py tests\test_point_in_time.py tests\test_interface_routing.py -q
venv\Scripts\python.exe -m pytest tests\ -q
```

**完成定义：** 任意关键证据可以追溯 provider、as-of、发布时间状态和内容哈希；历史模式遇到不安全数据会失败关闭。

## 9. F2-04：财务主源选型与 shadow 验证

状态：`NOT_STARTED`。需要用户决定是否购买或授权新数据源。

**Files:**

- Create: `docs/decisions/0001-financial-data-provider.md`
- Modify after decision: `tradingagents/dataflows/interface.py`
- Create after decision: `tradingagents/dataflows/financial_primary.py`
- Extend: `tests/test_official_sources.py`
- Create: `tests/fixtures/providers/financial_primary/`

- [ ] **步骤 1：只做选型，不先写适配器**

对候选源比较：A 股覆盖、三表字段、公告时间、历史修订、复权、限流、价格、权限、SDK 稳定性、许可条款和可缓存性。至少包含当前 Tushare 权限现状与一个独立财务 API。

- [ ] **步骤 2：写 ADR**

ADR 必须记录选择、拒绝方案、成本、不可逆约束、PIT 等级和退出策略。用户确认后状态才能从 Proposed 改为 Accepted。

- [ ] **步骤 3：fixture-first 适配器**

先保存脱敏响应 fixture，再实现统一三表输出。所有数值保留单位、币种、period_end、published_at、source_id 和修订版本。

- [ ] **步骤 4：shadow mode**

同一批 5 个 ticker 同时请求新旧源，比较字段覆盖、值差异、公告时间、延迟和失败率。shadow 结果不能影响正式推荐。

- [ ] **步骤 5：分阶段切换**

只有 shadow 达到事先写入 ADR 的通过条件，才把新源提升为主源；保留旧源作为降级。认证失败不得无限重试。

**完成定义：** 有 Accepted ADR、契约 fixture、5 ticker 对比报告和回滚开关；主源切换后 PIT 语义不下降。

## 10. F3-01：Golden cases v1

状态：`NOT_STARTED`，依赖 PIT sidecar。

**Files:**

- Create: `tradingagents/eval/data/golden_cases.v1.json`
- Create: `tradingagents/eval/golden.py`
- Modify: `tradingagents/eval/cases.py`
- Create: `tests/test_golden_cases.py`
- Update: `docs/point-in-time-audit.md`

- [ ] **步骤 1：冻结 schema**

```json
{
  "schema_version": 1,
  "dataset_version": "golden-v1",
  "cases": [
    {
      "id": "2024-01-02_600519_h20",
      "ticker": "600519",
      "as_of": "2024-01-02",
      "horizon_days": 20,
      "label_rule": "forward_close_return_v1",
      "label": "BUY",
      "horizon_return": 0.12,
      "evidence_snapshot_id": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
      "review_status": "human_verified"
    }
  ]
}
```

上例只定义字段，不是可直接采用的真实案例。真实值必须由冻结行情与人工复核生成，禁止复制示例数字。

- [ ] **步骤 2：建立校验器**

检查 ticker、日期、horizon、标签阈值、快照 ID、重复 ID、未来观察窗口完整性和人工复核状态。非法 case 阻断整个评测。

- [ ] **步骤 3：先制作 5 个案例**

覆盖 BUY、SELL、NEUTRAL、重大公告和数据缺失。每个案例保存构造脚本输出与人工复核记录。

- [ ] **步骤 4：扩展到 20 个案例**

按市场阶段、行业与市值分层，不从最终结果中只挑“系统容易做对”的案例。

**完成定义：** 20 个案例全部 human_verified、PIT 安全、可重复加载；数据集版本变更不可覆盖旧版。

## 11. F3-02：Agnes 正确性小样本评测

状态：`NOT_STARTED`。需要用户批准 Token 预算。

**Files:**

- Execute/modify if needed: `tradingagents/eval/__main__.py`
- Modify: `tradingagents/eval/runner.py`
- Modify: `tradingagents/eval/report.py`
- Test: `tests/test_eval.py`
- Artifact: `reports/eval/`

- [ ] **步骤 1：预算前置**

先用 1 个 case 估算 Token、耗时和费用；把单 case 预算乘以 5 后展示给用户，获得授权再继续。

- [ ] **步骤 2：运行 5-case pilot**

```powershell
venv\Scripts\python.exe -m tradingagents.eval --n 5 --provider agnes
```

如果 CLI 已改为读取环境，可省略 `--provider agnes`，但报告必须记录最终 provider/model。

- [ ] **步骤 3：验证报告真实性**

报告必须包含 dataset version、commit、provider/model、真实运行标记、样本量、混淆矩阵、方向准确率、拒绝率、证据覆盖、Token、耗时和失败列表。

- [ ] **步骤 4：失败案例复盘**

逐案区分：数据缺失、PIT 门禁、解析错误、模型判断错误、标签争议。不得把拒绝回答自动记为正确或错误，必须单列 coverage。

- [ ] **步骤 5：决定是否扩展**

只有 5-case pilot 没有时间穿越、报告语义错误或 Token 失控时，才扩到 20 cases。

**完成定义：** 至少 20 个冻结案例产生真实 Agnes 报告；结果无论好坏都保留；不将小样本数字包装成收益承诺。

## 12. F3-03：多窗口、成本与历史成分股回测

状态：`NOT_STARTED`。

**Files:**

- Modify: `tradingagents/backtest/engine.py`
- Modify: `tradingagents/backtest/data.py`
- Modify: `tradingagents/backtest/performance.py`
- Modify: `tradingagents/backtest/report.py`
- Modify: `tradingagents/backtest/__main__.py`
- Extend: `tests/test_backtest.py`

- [ ] **步骤 1：影响分析与现状冻结**

对 `BacktestEngine.run`、`build_pool`、`fetch_market_data`、`equity_curve_from_holdings` 运行 impact。保存当前 smoke 输出作为兼容基线。

- [ ] **步骤 2：交易规则测试先行**

新增测试覆盖佣金、印花税、滑点、停牌、涨跌停不可成交、成交量上限、退市缺价和 T+1。每条规则用小型手工 DataFrame 给出可计算真值。

- [ ] **步骤 3：历史股票池**

`build_pool` 接收 as-of 日期并优先使用历史成分快照；没有历史成分时报告 `survivorship_bias=true`，不得静默使用当前成分并声称无偏。

- [ ] **步骤 4：walk-forward**

明确 train、validation、test 三段。参数只在 validation 选择，最终 test 只运行一次。报告分别列出每段绩效。

- [ ] **步骤 5：成本矩阵**

固定策略下运行 0 / 10 / 20 bps，并报告收益、超额、Sharpe、最大回撤、换手率、拒单率和容量假设。

- [ ] **步骤 6：多市场阶段**

至少选择下跌、震荡、上涨三个不重叠窗口；窗口由日期规则预先确定，不根据结果好坏调整。

**完成定义：** 有历史成分状态、三阶段、留出测试集和成本矩阵；每个回测数字附限制条件。

## 13. F3-04：消融、敏感性与置信度校准

状态：`NOT_STARTED`。

**Files:**

- Modify: `tradingagents/ablation/configs.py`
- Modify: `tradingagents/ablation/runner.py`
- Modify: `tradingagents/ablation/report.py`
- Modify: `tradingagents/backtest/sensitivity.py`
- Create: `tradingagents/eval/calibration.py`
- Extend: `tests/test_ablation.py`
- Extend: `tests/test_sensitivity.py`
- Create: `tests/test_calibration.py`

- [ ] **步骤 1：冻结最小矩阵**

首批只比较 `single_market` 与 `multi_debate_1`，1 个 ticker、各 2 次，确认实验协议和成本字段正确后再运行四配置矩阵。

- [ ] **步骤 2：补全每次运行统计**

ablation outcome 增加 provider/model、tokens_in/out、llm_calls、tool_calls、elapsed、evidence coverage 和 failure status。

- [ ] **步骤 3：运行固定数据集**

所有配置使用同一 golden dataset version、同一 as-of 快照和相同模型参数。随机性参数必须记录。

- [ ] **步骤 4：敏感性**

每次只改变一个阈值，使用 validation 选参数；高敏感参数写入实验报告或 ADR。

- [ ] **步骤 5：校准**

按置信度区间统计命中率、覆盖率和拒绝率。样本不足 20 时只输出原始分箱，不拟合复杂校准器。

**完成定义：** 能回答多 Agent 是否改善质量、稳定性和成本；无法证明改善时也保留负结果。

## 14. F4-01：节点级 Token/时延优化

状态：`NOT_STARTED`，必须先有 F3-02 小样本基线。

**Files:**

- Inspect/modify: `tradingagents/application/service.py`
- Inspect/modify: `tradingagents/application/events.py`
- Inspect/modify: `tradingagents/graph/trading_graph.py`
- Inspect/modify: `tradingagents/graph/setup.py`
- Inspect/modify: `cli/stats_handler.py`
- Extend: `tests/test_analysis_service.py`
- Extend: `tests/test_graph_stream.py`

- [ ] **步骤 1：先测量，不先压缩**

记录每个节点输入/输出 Token、耗时、工具轮数、输出哈希、消息条数和压缩次数。建立 3 个固定 ticker 的基线。

- [ ] **步骤 2：定位前三大成本节点**

只优化累计 Token 占比最高的三个节点；不做全图重写。

- [ ] **步骤 3：按顺序尝试**

1. 去除重复 handoff / debug 快照；
2. 用结构化阶段摘要替代完整历史；
3. 只传 evidence reference，不复制大段工具文本；
4. 低新增信息时提前收敛；
5. 简单任务路由 quick model。

- [ ] **步骤 4：质量守卫**

每次优化都在同一 5-case 集合比较决策、证据覆盖、拒绝率和结构化解析成功率。成本下降但质量明显恶化时回滚该优化。

**完成定义：** 标准运行 Token 或时延至少下降 30%，且 golden pilot 质量指标没有超出预先设定的容忍区间。

## 15. F5-01：每日研究调度与差异报告

状态：`NOT_STARTED`。不包含自动下单。

**Files:**

- Create: `tradingagents/scheduler/daily_research.py`
- Create: `tradingagents/scheduler/manifest.py`
- Create: `tradingagents/scheduler/diff.py`
- Modify: `tradingagents/__main__.py`
- Create: `tests/test_daily_research.py`
- Create: `tests/test_research_diff.py`

- [ ] **步骤 1：定义可重入 manifest**

每个交易日记录 commit、config hash、universe、Screener run-id、Analyzer run-id、完成阶段和错误。相同日期/config 已完成时默认不重复收费；显式 `--force` 才重跑。

- [ ] **步骤 2：编排现有服务**

顺序固定为：交易日守卫 → Screener → 资格过滤 → 最多 N 个 Analyzer → 差异报告。不得复制 ScreenerEngine 或 AnalysisService 内部逻辑。

- [ ] **步骤 3：差异报告**

报告新增、移除、资格升降、证据覆盖变化、风险变化和供应商变化。没有变化时输出简短 no-change，不生成冗长 LLM 报告。

- [ ] **步骤 4：故障恢复**

单票 Analyzer 失败不抹掉 Screener 成功；再次运行从 manifest 未完成项继续。每日总 Token、时间和候选数有硬上限。

- [ ] **步骤 5：最后才接系统调度**

先手工运行 5 次无误，再提供 Windows Task Scheduler 示例。调度器只调用项目 CLI，不保存密钥副本。

**完成定义：** 日任务可重入、可恢复、有预算、无自动下单；差异报告可以解释候选变化。

## 16. F5-02：模拟组合与风险预算

状态：`NOT_STARTED`。

**Files:**

- Create: `tradingagents/portfolio/models.py`
- Create: `tradingagents/portfolio/risk_budget.py`
- Create: `tradingagents/portfolio/paper.py`
- Create: `tradingagents/portfolio/report.py`
- Create: `tests/test_portfolio_risk_budget.py`
- Create: `tests/test_paper_portfolio.py`

- [ ] **步骤 1：只接正式 eligible 候选**

research candidate 不进入模拟组合；每个持仓保存来源 run-id 和证据资格。

- [ ] **步骤 2：确定性风险规则**

先实现单票上限、行业上限、现金下限、换手上限、最大持仓数和相关性告警。规则由代码执行，不让 LLM 直接决定仓位。

- [ ] **步骤 3：paper ledger**

记录订单意图、成交假设、费用、拒单原因、持仓和净值。账本 append-only，修正使用反向记录，不覆盖历史。

- [ ] **步骤 4：回放验证**

使用 F3-03 的历史数据和成交规则回放，确认账本与回测净值一致。

**完成定义：** 模拟组合可审计、风险规则确定性、无券商连接、无真实下单能力。

## 17. F5-03：本地运营与证据面板

状态：`NOT_STARTED`。只有已有 artifact 足够稳定时才开始。

**Files:**

- Create: `tradingagents/observability/aggregate.py`
- Create: `tradingagents/observability/html_report.py`
- Modify: `tradingagents/ui/summary.py`
- Create: `tests/test_observability_aggregate.py`
- Create: `tests/test_html_report.py`

- [ ] **步骤 1：先定义只读聚合模型**

输入只读取现有 Analyzer、Screener、vendor health、eval 和 acceptance artifact；不直接调用 provider 或 LLM。

- [ ] **步骤 2：展示核心运营指标**

显示运行成功率、P50/P95 时延、Token、供应商失败率、证据覆盖、正式推荐数、拒绝率和 acceptance 状态。每个数字可链接到来源 artifact。

- [ ] **步骤 3：静态 HTML 优先**

先生成本地静态 HTML；只有确实需要交互筛选时才考虑服务化。输出转义所有外部文本，防止报告中的不可信内容形成 XSS。

**完成定义：** 面板完全只读、数字可追溯、无密钥、无外部文本注入。

## 18. 用户必须参与的决策

以下事项未来 Agent 不得擅自决定：

| 决策 | 需要用户提供什么 | 不提供时的默认行为 |
|---|---|---|
| Agnes 批量评测预算 | 最大 Token、费用或案例数 | 只跑离线测试，不调用 API |
| 新财务供应商 | 账号、权限、价格接受度和许可 | 保持现有降级，不启用新源 |
| Tushare | 是否提升积分并启用 | `TUSHARE_ENABLED=false` |
| HumanGate 真实验收 | 在终端选择 comment/abort | 只跑离线 HITL 测试 |
| Windows 定时任务 | 允许的时间、目录和账户 | 只提供手工 CLI |
| Paper trading | 是否接受模拟组合范围 | 不创建券商连接 |
| 实盘接口 | 单独的安全、合规和风控授权 | 永不实现自动下单 |

## 19. 通用 PR 模板

```markdown
## 修改目标

- 对应 Future Doing 工作包：WORK_PACKAGE_ID
- 解决的问题：
- 明确不包含：

## 主要修改

- 按实际提交填写文件、契约和行为变化；没有发生的修改不要列入。

## 验证结果

- 专项测试：
- 全量测试：
- compileall / diff-check：
- GitNexus 影响范围：
- 真实运行（如有）：provider、model、run-id、耗时、Token、artifact

## 证据等级

- CODE_READY / OFFLINE_VERIFIED / LIVE_SMOKE_VERIFIED / MULTI_DAY_VERIFIED / STATISTICALLY_EVALUATED

## 风险与回滚

- 风险：
- 回滚方式：
- 仍未完成：
```

## 20. 工作包完成后的文档更新

- 把本文件对应状态改为 `VERIFIED`，填写 commit、PR、测试与 artifact；
- 在 `Future.md` 只更新成熟度和优先级，不粘贴长实施日志；
- 在封箱总结后追加“恢复维护阶段”证据，不修改原封箱数字；
- 数据契约变化时更新 `docs/point-in-time-audit.md`；
- 公共架构变化时更新 `docs/architecture.md`；
- 重大、昂贵或难逆转的决策写入 `docs/decisions/`；
- README 只引用达到相应证据等级的数字。

## 21. 最终停止线

在以下条件全部满足前，项目仍定位为研究决策辅助系统：

- Screener 至少 20 个真实交易日稳定运行；
- 核心历史数据满足 PIT；
- golden cases 和留出回测形成统计报告；
- HumanGate、checkpoint 和故障恢复有真实证据；
- 成本、时延、供应商和推荐误放行有长期指标；
- 模拟组合风险规则稳定；
- 用户完成安全、合规和责任边界确认。

即使全部满足，也应先进入 paper trading；实盘自动下单必须作为全新项目阶段重新评审，而不是本计划的自然延伸。
