<p align="center">
  <img src="assets/TauricResearch.png" style="width: 60%; height: auto;">
</p>

<div align="center" style="line-height: 1;">
  <a href="https://arxiv.org/abs/2412.20138" target="_blank"><img alt="arXiv" src="https://img.shields.io/badge/arXiv-2412.20138-B31B1B?logo=arxiv"/></a>
  <a href="https://discord.com/invite/hk9PGKShPK" target="_blank"><img alt="Discord" src="https://img.shields.io/badge/Discord-TradingResearch-7289da?logo=discord&logoColor=white&color=7289da"/></a>
  <a href="./assets/wechat.png" target="_blank"><img alt="WeChat" src="https://img.shields.io/badge/WeChat-TauricResearch-brightgreen?logo=wechat&logoColor=white"/></a>
  <a href="https://x.com/TauricResearch" target="_blank"><img alt="X Follow" src="https://img.shields.io/badge/X-TauricResearch-white?logo=x&logoColor=white"/></a>
  <br>
  <a href="https://github.com/TauricResearch/" target="_blank"><img alt="Community" src="https://img.shields.io/badge/Join_GitHub_Community-TauricResearch-14C290?logo=discourse"/></a>
</div>

<div align="center">
  <!-- Keep these links. Translations will automatically update with the README. -->
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=de">Deutsch</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=es">Español</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=fr">français</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ja">日本語</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ko">한국어</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=pt">Português</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ru">Русский</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=zh">中文</a>
</div>

---

# 项目总览（中文）

> **版本：** v0.2.3 · **开发阶段：** Phase 5 · **最后更新：** 2026-05

TradingAgents 是由 [Tauric Research](https://github.com/TauricResearch) 开发的 **多智能体 LLM 金融交易框架**，专为 A 股市场设计。整个项目分为多个 Phase 迭代开发，当前处于 **Phase 5（统一 CLI 框架 + 可观测性终端）** 阶段。

---

## 开发阶段一览

| Phase | 名称 | 状态 | 说明 |
|-------|------|------|------|
| **Phase 1** | Screener 筛选器 | ✅ 已完成 | 多策略选股引擎（技术面/资金流/动量/突破/价值/政策） |
| **Phase 2** | Bug 修复 + CLI 美化 | ✅ 已完成 | 12 个 Bug 全部修复，Bloomberg Terminal 风格 Typer CLI |
| **Phase 3** | Harness 可观测性 + Skills | ✅ 已实现 | 25+ 内置 Skill，决策类型路由，成本追踪，Token 统计 |
| **Phase 4** | Memory 记忆系统 | 🔨 规划中 | 股票分析结论缓存（TTL 7 天） |
| **Phase 5** | 统一 CLI + Live Dashboard | ✅ 已完成 | 单一入口 + 主菜单循环 + 4 面板实时仪表盘 |

---

## 快速启动

### 环境准备

```bash
# 1. 克隆项目
git clone https://github.com/TauricResearch/TradingAgents.git
cd TradingAgents

# 2. 创建虚拟环境（Python 3.10+）
conda create -n tradingagents python=3.13
conda activate tradingagents

# 3. 安装依赖
pip install .
# 或使用 uv
uv pip install .

# 4. 安装 CLI 交互依赖（交互问卷功能）
pip install "questionary>=2.1.0"

# 5. 配置 API Key（至少配置一个）
export OPENAI_API_KEY=sk-...       # OpenAI（GPT 系列）
export GOOGLE_API_KEY=...          # Google（Gemini 系列）
export ANTHROPIC_API_KEY=...      # Anthropic（Claude 系列）
export DEEPSEEK_API_KEY=...       # DeepSeek
export DASHSCOPE_API_KEY=...      # Qwen（阿里云）
export ZHIPU_API_KEY=...           # GLM（智谱）
export XAI_API_KEY=...            # xAI（Grok 系列）
export OPENROUTER_API_KEY=...     # OpenRouter（一站式模型路由）
```

> 也可直接复制环境变量模板：
> ```bash
> cp .env.example .env
> # 然后编辑 .env 文件填入你的 API Keys
> ```

### Docker 启动

```bash
cp .env.example .env  # 填入 API Keys
docker compose run --rm tradingagents

# 使用本地模型（Ollama）
docker compose --profile ollama run --rm tradingagents-ollama
```

---

## 功能模块详解

### Stage 1 — Screener 筛选器

**定位：** A 股候选股票发现引擎，通过多策略协同筛选缩小候选范围。

**支持 6 种筛选模式：**

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `FULL` | 扫描沪深全市场（CSI 指数成分） | 全面扫描 |
| `FOCUSED` | 聚焦特定板块/主题/指数 | 行业机会 |
| `CUSTOM` | 自定义股票列表输入 | 已知标的 |
| `MVP` | 最小可行产品模式 | 快速验证 |
| `EXTENDED` | 扩展参数集 | 深度分析 |
| `EXPERIMENTAL` | 实验性策略 | 测试新方法 |

**6 大筛选策略（可叠加）：**

| 策略 | 核心指标 |
|------|----------|
| **技术面（Technical）** | MACD、RSI、KDJ、布林带、均线系统 |
| **资金流（Smart Money）** | 主力资金净流入、大单净流入、龙虎榜数据 |
| **动量（Momentum）** | 近期涨幅、成交量放大、趋势强度 |
| **突破（Breakout）** | 价格突破关键阻力位、成交量确认 |
| **价值（Value）** | PE、PB、PS、EV/EBITDA 等估值指标 |
| **政策（Policy）** | 政策利好/利空事件、概念板块轮动 |

**Deep Analyzer（深度分析）：** 候选股票通过 Deep Analyzer 做 LLM 驱动的深度分析，评估公司质量、行业地位、风险因素，最终输出候选股票排名列表（含评分、信号：BUY/HOLD/SELL、核心原因）。

**交互启动：**
```bash
python -m cli                        # 推荐：通过主菜单进入
python -m tradingagents               # 同上（统一入口）
python -m tradingagents screener     # 直接进入 Screener（向后兼容）
```

---

### Stage 2 — Analyzer 多智能体深度分析

**定位：** 对单只股票进行多智能体协同深度分析，输出包含决策、置信度、完整报告的最终交易建议。

**多智能体协作流程：**

```
I.   分析师团队（Analyst Team）
     ├─ Market Analyst（市场分析师）     — 宏观经济 + 行业趋势 + 价格动量
     ├─ News Analyst（新闻分析师）      — 全球新闻 + 政策解读 + 事件影响
     ├─ Social Analyst（社交分析师）    — 社交媒体情绪 + 舆情评分 + 群体行为
     └─ Fundamentals Analyst（基本面分析师）— 财务数据 + 估值分析 + 成长质量

     ↓（4 位分析师报告汇聚）

II.  研究员团队（Researcher Team）
     ├─ Bull Researcher（多头研究员）  — 挖掘看多逻辑
     └─ Bear Researcher（空头研究员）  — 挖掘看空逻辑

     ↓（多空辩论，Research Manager 裁判）

III. 交易员（Trader）
     └─ 综合研报 → 生成投资计划（入场/出场/仓位/风险预算）

     ↓（投资计划提交）

IV.  风控团队（Risk Management）
     ├─ Aggressive Analyst（激进型）    — 高风险高收益视角
     ├─ Conservative Analyst（保守型）  — 低风险稳健视角
     └─ Neutral Analyst（中性型）      — 平衡视角

     ↓（风控辩论，Portfolio Manager 裁判）

V.   投资组合经理（Portfolio Manager）
     └─ 最终决策：BUY / HOLD / SELL（含置信度百分比）
```

**8 步交互问卷（分析前配置）：**

| 步骤 | 内容 | 选项示例 |
|------|------|----------|
| Step 1 | 股票代码 | SPY、600519、NVDA、7203.T 等 |
| Step 2 | 分析日期 | YYYY-MM-DD（默认当天） |
| Step 3 | 输出语言 | 中文、English、日语、韩语等 12 种 |
| Step 4 | 分析团队 | Market / Social / News / Fundamentals（多选） |
| Step 5 | 研究深度 | Shallow（1轮）/ Medium（3轮）/ Deep（5轮） |
| Step 6 | LLM 提供商 | OpenAI / Google / DeepSeek / Qwen / Claude 等 10 种 |
| Step 7 | Thinking 模型 | quick 模型 + deep 模型（根据提供商提供选项） |
| Step 8 | 推理配置 | Google Thinking 模式 / OpenAI 推理深度 / Claude Effort Level |

**实时 Live Dashboard：** 分析过程中自动弹出 4 面板终端，实时展示：

```
┌─ PROGRESS ───────────┬─ AGENT STATUS ────────────┐
│ Stage 1  [■■■■] ✓    │ Market Analyst  ✓        │
│ Stage A  [●○○○] RUN  │ Social Analyst  ●         │
│ Stage B  [○○○○] WAIT │ News Analyst    ○        │
│ Stage C  [○○○○] WAIT │ Fundamentals   ○         │
├───────────────────────┴───────────────────────────┤
│ [EVENT TRAIL]                                   │
│ [14:30:01] Market Analyst: research started     │
│ [14:32:15] News Analyst: completed              │
│ [14:35:42] Debate in progress...                │
├─────────────────────────────────────────────────┤
│ LLM: 12  Tools: 45  ↑128K  ↓34K  ⏱ 05:23     │
└─────────────────────────────────────────────────┘
```

**交互启动：**
```bash
python -m cli                        # 推荐：通过主菜单进入
python -m tradingagents               # 同上（统一入口）
python -m tradingagents analyze      # 直接进入 Analyzer（向后兼容）
```

**Python API 启动（无界面）：**
```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["deep_think_llm"] = "gpt-5.4"
config["quick_think_llm"] = "gpt-5.4-mini"
config["max_debate_rounds"] = 3

ta = TradingAgentsGraph(
    selected_analyst_keys=["market", "news", "fundamentals"],
    config=config,
    debug=True
)
_, decision = ta.propagate("600519", "2026-05-20")
print(decision)  # 输出：BUY / HOLD / SELL + 置信度
```

---

### Stage 3 — HTML 报告查看器

生成的分析报告和筛选结果以 Markdown 格式保存在本地目录，CLI 提供交互式查看入口：

```bash
python -m cli                                  # 选 3 查看报告
python -m tradingagents report reports/        # 直接指定目录
```

---

## LLM 支持总览

| 提供商 | 支持模型 | 配置方式 |
|--------|----------|----------|
| **OpenAI** | GPT-5.5、GPT-5.5 Pro、GPT-5.4、GPT-5.4 Mini、GPT-4.1、GPT-4o | `OPENAI_API_KEY` |
| **Google** | Gemini 3.5 Flash、Gemini 3.1 Pro、Gemini 2.5 Pro（含 Thinking 模式） | `GOOGLE_API_KEY` |
| **Anthropic** | Claude Opus 4.8、Claude Sonnet 4.6、Claude Haiku 4.5、Claude Fable 5（含 Effort 控制） | `ANTHROPIC_API_KEY` |
| **DeepSeek** | DeepSeek V4 Flash、V4 Pro、V3 | `DEEPSEEK_API_KEY` |
| **Qwen（阿里云）** | Qwen3 Max/Plus/Flash、Qwen3-8B 等 | `DASHSCOPE_API_KEY` |
| **GLM（智谱）** | GLM-5、GLM-5.1、GLM-4.7 等 | `ZHIPU_API_KEY` |
| **xAI** | Grok 系列 | `XAI_API_KEY` |
| **OpenRouter** | 100+ 模型一站式路由 | `OPENROUTER_API_KEY` |
| **Azure OpenAI** | 企业版 GPT-4 等 | `.env.enterprise` 配置 |
| **Ollama** | 本地模型（Llama/Qwen 等） | `llm_provider: "ollama"` + 本地服务 |

---

## Phase 3 — Harness 可观测性 + Skills 系统

TradingAgents 内置 **Harness 可观测性框架**，提供 LLM 调用全链路追踪：

- **Skill 注册表**：25+ 内置 Skill（市场分析/舆情/政策/估值/风控等），按决策类型自动路由注入
- **成本追踪（CostTracker）**：实时统计 LLM Token 消耗（输入/输出/成本估算）
- **使用监控（API Usage）**：各 Agent 的 API 调用次数、延迟、错误率
- **决策链路追踪**：每个决策节点的 Skill 调用记录可审计

---

## 项目目录结构

```
TradingAgents/
├── cli/                          # 统一 CLI 入口（Phase 5 新增）
│   ├── __main__.py               # python -m cli 入口
│   ├── main_menu.py              # Bloomberg 风格主菜单
│   ├── prompts.py                 # 统一问卷工具（Rich 替代 questionary）
│   ├── analyze/                  # Analyzer 模块
│   │   ├── app.py                # 8 步问卷 + 汇总页
│   │   └── run_impl.py           # 核心执行引擎 + Live Dashboard
│   └── screener/                 # Screener 模块
│       ├── app.py                # 6 步问卷 + 执行
│       └── run_impl.py           # 筛选器执行引擎
│
├── tradingagents/
│   ├── ui/                       # Phase 5 UI 层
│   │   ├── theme.py              # Bloomberg Terminal 配色主题
│   │   ├── live_dashboard.py     # 4 面板实时仪表盘（3s 刷新）
│   │   ├── summary.py            # 分析/筛选结果汇总页
│   │   └── terminal_mascot.py    # 品牌吉祥物 Komo（小灰猫）
│   ├── harness/                  # Phase 3 可观测性框架
│   │   ├── skills/               # Skills 系统
│   │   │   ├── registry.py      # Skill 注册表
│   │   │   ├── mapping.py       # 决策类型路由
│   │   │   └── bundled/         # 25+ 内置 Skill（.md）
│   │   └── engine/               # 可观测性引擎
│   │       └── cost_tracker.py   # Token 成本追踪
│   ├── screener/                 # Phase 1 筛选器
│   │   ├── strategies/           # 6 大筛选策略
│   │   │   ├── technical.py     # 技术面策略
│   │   │   ├── smart_money.py   # 主力资金策略
│   │   │   └── policy.py        # 政策策略
│   │   ├── cli/                 # Screener Typer CLI
│   │   └── engine.py            # 筛选器执行引擎
│   ├── graph/                   # LangGraph 核心
│   │   └── trading_graph.py     # TradingAgentsGraph 多智能体图
│   ├── agents/                  # 多智能体系统
│   │   ├── analysts/            # 4 类分析师
│   │   ├── researchers/          # 多空研究员
│   │   ├── trader/              # 交易员
│   │   └── risk_mgmt/           # 风控辩论团队
│   ├── commands/                # 向后兼容命令（Analyze）
│   └── llm_clients/            # LLM 客户端工厂
│
├── docs/                        # 开发文档
│   └── Plan/Phase3/             # Phase 1-5 详细计划
│       ├── Plan5CLI.md          # Phase 5 CLI 详细设计
│       └── ...
│
├── assets/                     # 图片资源（Logo/架构图）
├── main.py                     # Python API 入口
└── pyproject.toml              # 项目元数据 + 依赖声明
```

---

## 命令速查表

| 功能 | 推荐命令 | 说明 |
|------|----------|------|
| **主菜单（推荐）** | `python -m cli` | 交互式主菜单，可进入 Screener / Analyzer / Report |
| **统一入口** | `python -m tradingagents` | 同上，通过 Typer 转发 |
| **直接进入 Screener** | `python -m tradingagents screener` | 向后兼容，直接进入筛选器 |
| **直接进入 Analyzer** | `python -m tradingagents analyze` | 向后兼容，直接进入分析器 |
| **查看报告** | `python -m tradingagents report reports/` | 打开 HTML 报告 |
| **版本信息** | `python -m tradingagents --version` | 显示版本 |
| **系统信息** | `python -m tradingagents --info` | 显示模块状态 |
| **Python API** | `python main.py` | 编程方式调用（见上方示例） |

---

## 常见问题

**Q: 运行时报错 `questionary` 未找到？**
```bash
pip install "questionary>=2.1.0"
```

**Q: 使用国内模型（DeepSeek/Qwen/GLM）连接失败？**
检查网络代理设置，或配置 `HTTP_PROXY` / `HTTPS_PROXY` 环境变量。

**Q: Screener 筛选结果为空？**
- 确认日期为交易日（非周末/节假日）
- 尝试扩大 `max_stocks` 参数
- 切换 `FULL` 模式扫描全市场

**Q: Analyzer 分析报错 `API 配额不足`？**
- 切换到其他 LLM 提供商
- 降低 `research_depth`（从 Deep 改为 Medium）
- 减少选中的分析师数量

---

## 参与贡献

我们欢迎社区贡献！无论是修复 Bug、改进文档还是提出新功能，都欢迎参与：
- 🌐 [Tauric Research](https://tauric.ai/)
- 💬 [Discord 社区](https://discord.com/invite/hk9PGKShPK)

---

# TradingAgents: Multi-Agents LLM Financial Trading Framework

## News
- [2026-03] **TradingAgents v0.2.3** released with multi-language support, GPT-5.4 family models, unified model catalog, backtesting date fidelity, and proxy support.
- [2026-03] **TradingAgents v0.2.2** released with GPT-5.4/Gemini 3.1/Claude 4.6 model coverage, five-tier rating scale, OpenAI Responses API, Anthropic effort control, and cross-platform stability.
- [2026-02] **TradingAgents v0.2.0** released with multi-provider LLM support (GPT-5.x, Gemini 3.x, Claude 4.x, Grok 4.x) and improved system architecture.
- [2026-01] **Trading-R1** [Technical Report](https://arxiv.org/abs/2509.11420) released, with [Terminal](https://github.com/TauricResearch/Trading-R1) expected to land soon.

<div align="center">
<a href="https://www.star-history.com/#TauricResearch/TradingAgents&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date" />
   <img alt="TradingAgents Star History" src="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date" style="width: 80%; height: auto;" />
 </picture>
</a>
</div>

> 🎉 **TradingAgents** officially released! We have received numerous inquiries about the work, and we would like to express our thanks for the enthusiasm in our community.
>
> So we decided to fully open-source the framework. Looking forward to building impactful projects with you!

<div align="center">

🚀 [TradingAgents](#tradingagents-framework) | ⚡ [Installation & CLI](#installation-and-cli) | 🎬 [Demo](https://www.youtube.com/watch?v=90gr5lwjIho) | 📦 [Package Usage](#tradingagents-package) | 🤝 [Contributing](#contributing) | 📄 [Citation](#citation)

</div>

## TradingAgents Framework

TradingAgents is a multi-agent trading framework that mirrors the dynamics of real-world trading firms. By deploying specialized LLM-powered agents: from fundamental analysts, sentiment experts, and technical analysts, to trader, risk management team, the platform collaboratively evaluates market conditions and informs trading decisions. Moreover, these agents engage in dynamic discussions to pinpoint the optimal strategy.

<p align="center">
  <img src="assets/schema.png" style="width: 100%; height: auto;">
</p>

> TradingAgents framework is designed for research purposes. Trading performance may vary based on many factors, including the chosen backbone language models, model temperature, trading periods, the quality of data, and other non-deterministic factors. [It is not intended as financial, investment, or trading advice.](https://tauric.ai/disclaimer/)

Our framework decomposes complex trading tasks into specialized roles. This ensures the system achieves a robust, scalable approach to market analysis and decision-making.

### Analyst Team
- Fundamentals Analyst: Evaluates company financials and performance metrics, identifying intrinsic values and potential red flags.
- Sentiment Analyst: Analyzes social media and public sentiment using sentiment scoring algorithms to gauge short-term market mood.
- News Analyst: Monitors global news and macroeconomic indicators, interpreting the impact of events on market conditions.
- Technical Analyst: Utilizes technical indicators (like MACD and RSI) to detect trading patterns and forecast price movements.

<p align="center">
  <img src="assets/analyst.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

### Researcher Team
- Comprises both bullish and bearish researchers who critically assess the insights provided by the Analyst Team. Through structured debates, they balance potential gains against inherent risks.

<p align="center">
  <img src="assets/researcher.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### Trader Agent
- Composes reports from the analysts and researchers to make informed trading decisions. It determines the timing and magnitude of trades based on comprehensive market insights.

<p align="center">
  <img src="assets/trader.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### Risk Management and Portfolio Manager
- Continuously evaluates portfolio risk by assessing market volatility, liquidity, and other risk factors. The risk management team evaluates and adjusts trading strategies, providing assessment reports to the Portfolio Manager for final decision.
- The Portfolio Manager approves/rejects the transaction proposal. If approved, the order will be sent to the simulated exchange and executed.

<p align="center">
  <img src="assets/risk.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

## Installation and CLI

### Installation

Clone TradingAgents:
```bash
git clone https://github.com/TauricResearch/TradingAgents.git
cd TradingAgents
```

Create a virtual environment in any of your favorite environment managers:
```bash
conda create -n tradingagents python=3.13
conda activate tradingagents
```

Install the package and its dependencies:
```bash
pip install .
```

### Docker

Alternatively, run with Docker:
```bash
cp .env.example .env  # add your API keys
docker compose run --rm tradingagents
```

For local models with Ollama:
```bash
docker compose --profile ollama run --rm tradingagents-ollama
```

### Required APIs

TradingAgents supports multiple LLM providers. Set the API key for your chosen provider:

```bash
export OPENAI_API_KEY=...          # OpenAI (GPT)
export GOOGLE_API_KEY=...          # Google (Gemini)
export ANTHROPIC_API_KEY=...       # Anthropic (Claude)
export XAI_API_KEY=...             # xAI (Grok)
export DEEPSEEK_API_KEY=...        # DeepSeek
export DASHSCOPE_API_KEY=...       # Qwen (Alibaba DashScope)
export ZHIPU_API_KEY=...           # GLM (Zhipu)
export OPENROUTER_API_KEY=...      # OpenRouter
export ALPHA_VANTAGE_API_KEY=...   # Alpha Vantage
```

For enterprise providers (e.g. Azure OpenAI, AWS Bedrock), copy `.env.enterprise.example` to `.env.enterprise` and fill in your credentials.

For local models, configure Ollama with `llm_provider: "ollama"` in your config.

Alternatively, copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

### CLI Usage

Launch the interactive CLI:
```bash
tradingagents          # installed command
python -m cli.main     # alternative: run directly from source
```
You will see a screen where you can select your desired tickers, analysis date, LLM provider, research depth, and more.

<p align="center">
  <img src="assets/cli/cli_init.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

An interface will appear showing results as they load, letting you track the agent's progress as it runs.

<p align="center">
  <img src="assets/cli/cli_news.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

<p align="center">
  <img src="assets/cli/cli_transaction.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

## TradingAgents Package

### Implementation Details

We built TradingAgents with LangGraph to ensure flexibility and modularity. The framework supports multiple LLM providers: OpenAI, Google, Anthropic, xAI, OpenRouter, and Ollama.

### Python Usage

To use TradingAgents inside your code, you can import the `tradingagents` module and initialize a `TradingAgentsGraph()` object. The `.propagate()` function will return a decision. You can run `main.py`, here's also a quick example:

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())

# forward propagate
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

You can also adjust the default configuration to set your own choice of LLMs, debate rounds, etc.

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"        # openai, google, anthropic, xai, openrouter, ollama
config["deep_think_llm"] = "gpt-5.4"       # Model for complex reasoning
config["quick_think_llm"] = "gpt-5.4-mini" # Model for quick tasks
config["max_debate_rounds"] = 2

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

See `tradingagents/default_config.py` for all configuration options.

## Contributing

We welcome contributions from the community! Whether it's fixing a bug, improving documentation, or suggesting a new feature, your input helps make this project better. If you are interested in this line of research, please consider joining our open-source financial AI research community [Tauric Research](https://tauric.ai/).

## Citation

Please reference our work if you find *TradingAgents* provides you with some help :)

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
