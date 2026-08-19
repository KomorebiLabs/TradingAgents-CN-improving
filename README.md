<p align="center">
  <img src="assets/TauricResearch.png" style="width: 60%; height: auto;">
</p>

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
git clone https://github.com/KomorebiLabs/TradingAgents-CN-improving.git
cd TradingAgents-CN-improving

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

### 运行测试（离线护栏）

```bash
venv/Scripts/python.exe -m pytest tests/ -q    # 预期：385 passed（全部离线，无网络无 LLM）
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
python -m tradingagents               # 推荐：统一入口（主菜单）
python -m cli                        # 通过主菜单进入（向后兼容）
python -m tradingagents screener     # 直接进入 Screener
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
python -m tradingagents analyze      # 直接进入 Analyzer
python -m tradingagents               # 通过主菜单进入
python -m cli                        # 通过主菜单进入（向后兼容）
```

**Python API 启动（无界面）：**
```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["deep_think_llm"] = "gpt-4o"
config["quick_think_llm"] = "gpt-4o-mini"
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
python -m tradingagents report reports/        # 直接指定目录
```

---

## LLM 支持总览

| 提供商 | 支持模型 | 配置方式 |
|--------|----------|----------|
| **OpenAI** | GPT-4o、GPT-4o-mini、GPT-4.1 | `OPENAI_API_KEY` |
| **Google** | Gemini 2.0 Flash、Gemini 1.5 Pro、Gemini 1.5 Flash（含 Thinking 模式） | `GOOGLE_API_KEY` |
| **Anthropic** | Claude 3.5 Sonnet、Claude 3.5 Haiku、Claude 3 Opus（含 Effort 控制） | `ANTHROPIC_API_KEY` |
| **DeepSeek** | DeepSeek V3（deepseek-chat）、DeepSeek R1（deepseek-reasoner） | `DEEPSEEK_API_KEY` |
| **Qwen（阿里云）** | Qwen Plus、Qwen Max、Qwen Long 等 | `DASHSCOPE_API_KEY` |
| **GLM（智谱）** | GLM-4、GLM-4-Plus、GLM-4-Flash 等 | `ZHIPU_API_KEY` |
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
TradingAgents-CN-improving/
├── cli/                          # 统一 CLI（Phase 5）
│   ├── __main__.py               # python -m cli 入口
│   ├── main_menu.py              # Bloomberg 风格主菜单
│   ├── prompts.py                # 统一问卷工具
│   ├── report_viewer.py          # 报告查看器
│   ├── announcements.py          # 公告组件
│   ├── analyze/                  # Analyzer 模块（app.py + run_impl.py）
│   └── screener/                 # Screener 模块（app.py + run_impl.py）
│
├── tradingagents/
│   ├── application/              # 应用层（AnalysisRequest/Result + 9 种执行事件 + AnalysisService）
│   ├── ports/                    # MarketDataPort 能力协议 + 进程级共享实例
│   ├── ui/                       # 终端 UI（live_dashboard / summary / theme）
│   ├── harness/                  # Phase 3 可观测性（skills/ + engine/cost_tracker）
│   ├── graph/                    # LangGraph 核心
│   │   ├── trading_graph.py      # TradingAgentsGraph（stream_analysis / propagate）
│   │   ├── setup.py              # 图装配（setup_graph 编排器 + 阶段构建方法）
│   │   └── reflection/           # 反思包（extraction / route_analytics / reflector / conclusion）
│   ├── agents/                   # 多智能体系统
│   │   ├── analysts/             # 分析师（market / social / news / fundamentals）
│   │   ├── researchers/          # 多空研究员
│   │   ├── trader/               # 交易员
│   │   ├── risk_mgmt/            # 风控辩论团队
│   │   ├── managers/             # Research / Portfolio Manager
│   │   └── utils/                # 状态助手 + 记忆（memory/）+ 工具装配（tools/）
│   ├── screener/                 # Stage 1 筛选器
│   │   ├── data_access.py        # 数据门面（546 行，拆自 1905 行）
│   │   ├── engine.py             # 筛选执行引擎 + DeepAnalyzer
│   │   ├── universe.py           # 股票池构建
│   │   ├── merger/               # 信号合并包（pipeline / aggregation / conflicts / filters / ...）
│   │   ├── strategies/           # 三大策略（technical / policy / smart_money）
│   │   └── vendors/              # 供应商适配（tencent / sina / ths / misc / backup）
│   ├── dataflows/                # 数据层
│   │   ├── akshare/              # akshare 领域包（stock / news / flow / macro / events / ...）
│   │   ├── interface.py          # 供应商路由（route_to_vendor）
│   │   └── errors.py             # 类型化供应商错误（VendorError 族）
│   └── llm_clients/              # LLM 客户端工厂（10+ 提供商）
│
├── tests/                        # 离线测试护栏（385 个用例，全离线）
├── main.py                       # Python API 入口示例
└── pyproject.toml                # 项目元数据 + 依赖声明
```

---

## 命令速查表

| 功能 | 推荐命令 | 说明 |
|------|----------|------|
| **统一入口（推荐）** | `python -m tradingagents` | 交互式主菜单，可进入 Screener / Analyzer / Report |
| **主菜单（兼容）** | `python -m cli` | 同上 |
| **直接进入 Screener** | `python -m tradingagents screener` | 直接进入筛选器 |
| **直接进入 Analyzer** | `python -m tradingagents analyze` | 直接进入分析器 |
| **查看报告** | `python -m tradingagents report reports/` | 打开报告查看器 |
| **版本信息** | `python -m tradingagents --version` | 显示版本 |
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

# 上游版权与致谢

TradingAgents 框架起源于 [Tauric Research](https://github.com/TauricResearch/TradingAgents) 的开源项目（arXiv:2412.20138）。本仓库 **TradingAgents-CN-improving** 在其基础上面向 A 股市场做了深度重构与扩展。

> 上游英文安装 / CLI / 包使用文档已被上文的中文本地化文档取代，不再保留；上游方的 Discord、微信群、Star History 等社区资源与本仓库无关。

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
