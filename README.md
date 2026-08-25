<p align="center">
  <img src="assets/TauricResearch.png" style="width: 60%; height: auto;">
</p>

---

# TradingAgents-CN — 面向 A 股的多智能体 LLM 交易框架

> **版本：** v0.2.3 · **定位：** 基于开源 [TradingAgents](https://github.com/TauricResearch/TradingAgents)（~99k★）的 A 股深度定制 + 面向二开的架构治理
> **测试护栏：** 682 个离线测试全绿（无网络、无 LLM）· **文档：** [架构](docs/architecture.md) · [面试导航](docs/interview-notes.md) · [封箱验收](docx/开发文件/封箱总结-项目完成情况与面试验收.md)

TradingAgents 是专为 **A 股市场**设计的 **多智能体 LLM 金融交易框架**：先用 Screener 从数千只股票中筛选候选，再用 LangGraph 编排的「分析师 → 多空辩论 → 交易员 → 风控辩论」多智能体流程对候选做深度分析，输出 BUY / HOLD / SELL 决策。

相比之下，这个仓库的重点不只是"几个 Agent 协作"，而是**把它做成了可观察、可测试、可演进、可二开的工程系统**——历史遗留的模块耦合、状态双写、多入口与供应商耦合，已被逐步收口为单向分层 + 契约化 + 测试护航的干净边界。

---

## 🚀 项目亮点（均为仓库内真实验证产物）

> 下面的数字来自 `pytest` 输出 / `reports/` 下真实回测与敏感性报告，可复现；**每个指标都标注适用边界**。

| 维度 | 亮点 | 边界 |
|---|---|---|
| **回测引擎** | 自研信号驱动回测，复用系统真实选股逻辑（TechnicalStrategy），CSI300 之 80 只池 · 月度再平衡 top5 → **总收益 82.86% / 夏普 2.17 / 超额 +56.57%**（12 个月） | 单段窗口、未计交易成本、仅技术因子可回溯；窗口参数可调整，交易成本显式化仍属下一阶段（见 `reports/backtest/`） |
| **参数敏感性** | 动量权重 −22% → 收益腰斩（30.9%），趋势对齐权重正向敏感——"感觉合理"的参数有了**实测依据** | 小池 mini 回测，见 `reports/sensitivity.md` |
| **未来函数审计** | 回测取数显式截止信号日（`end_date = trade_date`），杜绝 look-ahead 泄漏 | 已在技术因子上核实 |
| **测试护栏** | **682 个离线测试**：merger golden/parity、回测净值数学、供应商健康、接口路由、AST 依赖无环、图拓扑分解、证据门禁与真实运行回归 | 以"冻结行为"和工程契约为主；不等价于真实模型正确率 |
| **数据可靠性** | 逐供应商健康监控（失败率/耗时/最近错误）+ 反爬重试（连接类指数退避、**HTTP 429/403 绝不重试**）+ 熔断降级 + 假成功可见化 | 免费数据源本身有接口漂移风险，已加探测告警 |
| **工程重构** | 六大千行文件拆解（merger 1050 / reflection 1302 / memory 1124 / data_access 1905 / akshare_interface 1619 / agent_utils 944）→ 单向依赖分层 | 公开 API 零改动，等价性由 golden + parity 测试证明 |

## 🤖 AI Agent / LLM 工程视角

用 **LangGraph 状态编排**管理多阶段交接与条件路由；用 **canonical AgentState**（结构化块权威、平铺字段降级兼容镜像）消除"同一数据两套形状"的迁移陷阱；用 **Tool / Port / Dataflows 分层**隔离数据能力与具体供应商；用 **Application Events（9 种执行事件）+ Harness** 把图 chunk 转为稳定事件，统一承载状态、工具调用、Token、成本与错误；用 **contract / golden / parity / 依赖图测试**在不改动公开行为的前提下铲除历史入口分叉与 God Class。

**Agent 可靠性与评测：** 通过离线 Tool Contract 测试约束工具参数转发、时间边界与失败语义；通过 point-in-time 审计约束 Agent 数据 grounding；评测框架支持决策归一化、混淆矩阵、方向准确率与运行元数据，并显式区分 `framework_ready` 与 `real_model_run`——**不把未运行的真实 API / 模型评测写成已验证结果**。

> 证据边界声明：本项目明确区分**代码能力 / 离线验证 / 业务证据**——不把未执行的真实 API 端到端运行、消融实验或正确性评测写成已验证结果。详见 [架构与证据标签](docs/architecture.md)。

---

## 🧪 验证与治理成果

| 板块 | 成果 | 位置 |
|---|---|---|
| 回测闭环 | 信号驱动回测引擎 + 市场分析报告（绩效、资金曲线、csv） | `python -m tradingagents.backtest` / `reports/backtest/` |
| 参数敏感性 | 二参数十扰动 mini 回测表，量化权重敏感度 | `python -m tradingagents.backtest --sensitivity` / `reports/sensitivity.md` |
| 多智能体消融 | 分析师数 × 辩论深度的对照框架，量化决策一致性与成本 | `python -m tradingagents.ablation` |
| 正确性评测集 | 已知结局案例 → 混淆矩阵 + 方向准确率；决策归一化、评测元数据与 `real_model_run` 边界已建立；真实模型评测仍未形成统计结论 | `python -m tradingagents.eval` |
| 数据可靠性 | 供应商健康监控 + 反爬重试 + 熔断 + 假成功可见化 | `tradingagents/screener/vendors/_guard.py` 等 |
| Point-in-time 审计 | 技术指标路径已增加历史截止日防御，并完成工具族审计矩阵；**没有宣称所有供应商都通过历史披露时点验证** | [审计表](docs/point-in-time-audit.md) |
| 工具契约 | Tool wrapper → 路由 → provider 的参数转发、时间边界与失败语义有离线契约测试，避免日期参数丢失/错位 | `tests/test_tool_contracts.py` |
| LLM 成本估算 | LLM token 成本（$/MTok）+ 结构化决策提取（正则优先省调用）+ 可选缓存（命中/未命中可观测） | `tradingagents/llm_clients/cost.py`、`cache.py` |

---

## 📚 文档导航

| 文档 | 内容 |
|---|---|
| [架构说明](docs/architecture.md) | 分层图、数据流、证据标签体系（架构岗位深读） |
| [面试导航](docs/interview-notes.md) | 60 秒介绍 + 技术 FAQ + 诚实应答（AI 工程岗备考） |
| [演示手册](docs/demo-runbook.md) | Analyzer / Screener 最小复现路径与证据检查 |
| `docx/屎山清理/屎山报告-1..5` | 诊断与七轮+重构施工记录（历史依据） |
| `docx/开发文件/治理报告-6` | 残余不足与下一阶段治理方案 |
| `docx/开发文件/交接报告` | 给下一个 Agent/助手的工作交接（当前进度） |
| [路线规划](docx/开发文件/项目发展路线规划-简历价值导向.md) | 简历导向的发展路线（R1-R11 + 冲刺计划） |
| [README_TECH](README_TECH.md) | 深度技术手册（模块级实现细节） |

---

## 快速启动

### 环境准备

```bash
# 1. 克隆项目
git clone https://github.com/KomorebiLabs/TradingAgents-CN-improving.git
cd TradingAgents-CN-improving

# 2. 创建虚拟环境（Python 3.10+）并安装
conda create -n tradingagents python=3.13
conda activate tradingagents
pip install .

# 3. 安装 CLI 交互依赖
pip install "questionary>=2.1.0"

# 4. 配置 API Key（至少一个）
export AGNES_API_KEY=...      # Agnes AI（本项目真实验收使用 Agnes 2.5 Flash）
export OPENAI_API_KEY=...     # OpenAI（GPT 系列）
export GOOGLE_API_KEY=...     # Google（Gemini）
# ... 见下方"LLM 支持总览"
```

### 运行测试（离线护栏，无需任何 Key）

```bash
venv/Scripts/python.exe -m pytest tests/ -q    # 预期：682 passed（全离线）
```

### 跑一次回测（免费数据，无需 LLM Key）

```bash
python -m tradingagents.backtest --sensitivity   # 参数敏感性表 → reports/sensitivity.md
python -m tradingagents.backtest                 # 完整回测 → reports/backtest/<run_id>/
```

---

## 功能模块详解

### Stage 1 — Screener 筛选器

**定位：** A 股候选股票发现引擎，多策略协同筛选。

- **6 种模式**：`FULL` / `FOCUSED` / `CUSTOM` / `MVP` / `EXTENDED` / `EXPERIMENTAL`
- **5 级供应商降级**：腾讯直连 → AkShare腾讯 → AkShare新浪 → BaoStock → yfinance（历史 K 线），逐源失败自动降级 + 熔断
- **三大策略**：技术面（Technical）/ 主力资金（Smart Money）/ 政策概念（Policy），输出信号卡并经 **Merger** 合并与冲突解决
- **6 大筛选策略**（可叠加）：技术面 / 资金流 / 动量 / 突破 / 价值 / 政策

```bash
python -m tradingagents screener          # 直接进入 Screener
python -m tradingagents                   # 统一入口（主菜单）
```

### Stage 2 — Analyzer 多智能体深度分析

**定位：** 对单只股票进行多智能体协同深度分析，输出 BUY / HOLD / SELL 决策。

```
I.  分析师团队（Market / Social / News / Fundamentals）
        ↓ 4 份分析报告汇聚
II. 研究员团队（Bull ↔ Bear 多空辩论，Research Manager 裁判）
        ↓ 投资计划
III. 交易员 Trader → 具体交易计划
        ↓
IV.  风控团队（Aggressive ↔ Conservative ↔ Neutral 辩论）
        ↓ Portfolio Manager 裁判
V.   最终决策：BUY / HOLD / SELL
```

- **自适应辩论轮数**：按语义信号（政策地位 / 资金质量 / 冲突等级）自动增减轮数，简单标的省 token、高冲突标的加深
- **8 步交互问卷** + **实时 Live Dashboard**（Rich 4 面板）

```bash
python -m tradingagents analyze           # 直接进入 Analyzer
python -m tradingagents                   # 统一入口
```

**Python API（无界面）：**
```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["deep_think_llm"] = "gpt-4o"
config["quick_think_llm"] = "gpt-4o-mini"

ta = TradingAgentsGraph(selected_analyst_keys=["market", "news", "fundamentals"], config=config)
_, decision = ta.propagate("600519", "2026-05-20")
print(decision)
```

---

## LLM 支持总览

| 提供商 | 内置模型（保守真实 ID 子集） | 配置方式 |
|--------|------------------------------|----------|
| **OpenAI** | GPT-4o、GPT-4o-mini、GPT-4.1 | `OPENAI_API_KEY` |
| **Google** | Gemini 2.0 Flash、Gemini 1.5 Pro/Flash | `GOOGLE_API_KEY` |
| **Anthropic** | Claude 3.5 Sonnet/Haiku、Claude 3 Opus | `ANTHROPIC_API_KEY` |
| **DeepSeek** | deepseek-chat、deepseek-reasoner | `DEEPSEEK_API_KEY` |
| **Agnes AI** | agnes-2.5-flash（OpenAI-compatible） | `AGNES_API_KEY` |
| **Qwen（阿里云）** | qwen-plus、qwen-max、qwen-long | `DASHSCOPE_API_KEY` |
| **GLM（智谱）** | glm-4、glm-4-plus、glm-4-flash | `ZHIPU_API_KEY` |
| **xAI / OpenRouter / Azure / Ollama** | Grok、100+ 路由、企业模型、本地模型 | 各自 Key / 配置 |

> 系统通过 `deep_think_llm` / `quick_think_llm` 接受任意模型 ID；目录里的 ID 为保守真实子集，请以各提供商官方文档为准。

---

## 项目目录结构

```
TradingAgents-CN-improving/
├── cli/                          # 统一 CLI（主菜单 / analyze / screener / report）
├── tradingagents/
│   ├── application/              # 契约层：AnalysisRequest/Result + 9 种执行事件 + AnalysisService
│   ├── graph/                    # LangGraph 核心（trading_graph / setup / reflection 包）
│   ├── agents/                   # 分析师/研究员/交易员/风控/记忆(memory/)/工具装配(tools/)
│   ├── screener/                 # Stage 1（data_access 门面 / merger 包 / strategies / vendors）
│   ├── dataflows/                # 数据层（akshare 领域包 / interface 路由 / 类型化 errors）
│   ├── ports/                    # MarketDataPort 能力协议（进程级共享实例）
│   ├── backtest/                 # 自研信号回测引擎（engine/performance/sensitivity）
│   ├── ablation/                 # 多智能体消融框架（configs/runner/stability/report）
│   ├── eval/                     # 决策正确性评测集（cases/matrix/runner/report）
│   ├── harness/                  # 可观测性（skills / cost_tracker / usage）
│   ├── llm_clients/              # LLM 工厂（catalog 祛魅 / cost 估算 / cache）
│   └── ui/                       # 终端 UI（live_dashboard / summary / theme）
├── docs/                         # 架构说明 + 面试导航 + 演示手册（证据标签体系）
├── docx/                         # 治理报告系列（屎山清理 / 开发文件）
├── tests/                        # 682 个离线测试护栏
└── pyproject.toml                # 元数据 + 依赖
```

---

## 命令速查表

| 功能 | 命令 | 说明 |
|------|------|------|
| 统一入口（推荐） | `python -m tradingagents` | 主菜单（Screener / Analyzer / Report） |
| Screener | `python -m tradingagents screener` | 直接进筛选器 |
| Analyzer | `python -m tradingagents analyze` | 直接进分析器 |
| 报告查看 | `python -m tradingagents report reports/` | 打开报告查看器 |
| 回测 | `python -m tradingagents.backtest` | 信号驱动回测（免费数据） |
| 敏感性 | `python -m tradingagents.backtest --sensitivity` | 参数敏感性扫描 |
| 消融（需 LLM Key） | `python -m tradingagents.ablation` | 多智能体消融对比 |
| 评测（需 LLM Key） | `python -m tradingagents.eval` | 决策正确性评测集 |
| 测试 | `venv/Scripts/python.exe -m pytest tests/ -q` | 682 离线用例 |
| 版本 | `python -m tradingagents --version` | 显示版本 |

---

## 常见问题

**Q: 运行时报错 `questionary` 未找到？**
```bash
pip install "questionary>=2.1.0"
```

**Q: 国内模型（DeepSeek/Qwen/GLM）连接失败？**
检查网络代理，或配置 `HTTP_PROXY` / `HTTPS_PROXY`。

**Q: Screener 筛选结果为空？**
确认是交易日、扩大 `max_stocks`、改 `FULL` 模式。

**Q: Analyzer 报 `API 配额不足`？**
切换提供商、降低 `research_depth`、减少分析师数。

**Q: 回测的 82.86% 可靠吗？**
它是单段 12 个月、未计成本、仅技术因子的"方法论演示"，不是预测保证——引擎支持多窗口与成本参数，可自行复现与扩展验证。

---

# 上游版权与致谢

TradingAgents 框架起源于 [Tauric Research](https://github.com/TauricResearch/TradingAgents) 的开源项目（arXiv:2412.20138）。本仓库 **TradingAgents-CN-improving** 在其基础上面向 A 股市场做了深度重构与扩展。

> 上游英文安装 / CLI / 包使用文档已被上文中文本地化文档取代；上游方的 Discord、微信群、Star History 等社区资源与本仓库无关。

## Citation

请在你的工作中引用原框架：

```
@misc{xiao2025tradingagentsmultiagentsllmfinancial,
      title={TradingAgents: Multi-Agents LLM Financial Trading Framework},
      author={Yijia Xiao and Edward Sun and Di Luo and Wei Wang},
      year={2025},
      eprint={2412.20138},
      archivePrefix={arXiv},
      primaryClass={q-fin.TR},
      url={https://arxiv.org/abs/2412.20138},
}
```
