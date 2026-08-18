# TradingAgents 技术报告

> **版本：** v0.2.3 · **Phase：** Phase 5 · **更新日期：** 2026-05
> **项目地址：** https://github.com/TauricResearch/TradingAgents

本文档是 TradingAgents 的深度技术参考手册，面向开发者、贡献者和高级用户。它详细说明了每个模块的技术实现、算法原理、数据来源和架构设计。基础入门请参阅 `README.md`。

---

## 目录

1. [整体架构](#1-整体架构)
2. [Stage 1 — Screener 筛选器](#2-stage-1--screener-筛选器)
   - [2.1 数据访问层（ScreenerDataAccess）](#21-数据访问层screenerdataaccess)
   - [2.2 股票池构建（Universe）](#22-股票池构建universe)
   - [2.3 Stage A 预筛选](#23-stage-a-预筛选)
   - [2.4 三大策略引擎](#24-三大策略引擎)
   - [2.5 信号合并与冲突解决（Merger）](#25-信号合并与冲突解决merger)
   - [2.6 Deep Analyzer 深度分析](#26-deep-analyzer-深度分析)
   - [2.7 报告生成（Report）](#27-报告生成report)
3. [Stage 2 — Analyzer 多智能体深度分析](#3-stage-2--analyzer-多智能体深度分析)
   - [3.1 LangGraph 架构](#31-langgraph-架构)
   - [3.2 分析师团队（Analyst Team）](#32-分析师团队analyst-team)
   - [3.3 研究员团队（Researcher Team）](#33-研究员团队researcher-team)
   - [3.4 交易员（Trader）](#34-交易员trader)
   - [3.5 风控团队（Risk Management）](#35-风控团队risk-management)
   - [3.6 辩论机制详解](#36-辩论机制详解)
   - [3.7 记忆系统（Memory）](#37-记忆系统memory)
4. [CLI 交互界面](#4-cli-交互界面)
   - [4.1 统一主菜单](#41-统一主菜单)
   - [4.2 Live Dashboard 实时仪表盘](#42-live-dashboard-实时仪表盘)
   - [4.3 分析报告汇总页](#43-分析报告汇总页)
5. [LLM 多提供商支持](#5-llm-多提供商支持)
   - [5.1 LLM 客户端工厂](#51-llm-客户端工厂)
   - [5.2 支持的提供商与模型](#52-支持的提供商与模型)
   - [5.3 双模型架构（Deep + Quick）](#53-双模型架构deep--quick)
6. [工具系统与数据流](#6-工具系统与数据流)
   - [6.1 数据流接口路由](#61-数据流接口路由)
   - [6.2 核心工具清单](#62-核心工具清单)
7. [技术栈总览](#7-技术栈总览)
8. [开发阶段路线图](#8-开发阶段路线图)

---

## 1. 整体架构

TradingAgents 是一个专为 A 股市场设计的多智能体 LLM 金融交易框架，分为两个核心分析阶段：

```
┌─────────────────────────────────────────────────────────────┐
│                    统一入口：python -m cli                   │
│                 Bloomberg Terminal 风格交互界面               │
└──────────────────────────┬──────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌─────────────┐  ┌──────────────┐  ┌─────────────┐
    │   Stage 1   │  │   Stage 2   │  │   Report    │
    │  Screener   │  │  Analyzer   │  │  Viewer     │
    │  筛选器     │  │  多智能体   │  │  报告查看   │
    └──────┬──────┘  └──────┬──────┘  └─────────────┘
           │                 │
           ▼                 ▼
    从 4000+ 股票中    对单只股票进行
    筛选出 Top 3-5      多智能体深度分析
    候选股票            输出 BUY/HOLD/SELL
```

### 整体数据流

```
原始股票池（Universe）
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  Stage A — 预筛选（4 重过滤器）                            │
│  历史数据可用性 → 数据完整性 → 流动性 → 涨跌停检测         │
└──────────────────────────┬──────────────────────────────────┘
                           │ ~4000+ → ~500-2000
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Stage B — 三大策略并行打分                                │
│  TechnicalStrategy  │ PolicyStrategy  │ SmartMoneyStrategy  │
│  (技术指标)          │ (概念板块)       │ (资金流向)         │
└──────────────────────────┬──────────────────────────────────┘
                           │ SignalCard 列表
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Merger — 信号合并与冲突解决                               │
│  10 重硬过滤器 + 6 规则冲突解决 + 分散化限制              │
└──────────────────────────┬──────────────────────────────────┘
                           │ Top 3-5 候选
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Deep Analyzer — LLM 深度分析                              │
│  对每只候选股进行语义级质量评估                           │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  报告生成（JSON + Markdown）                               │
│  screening_result.json + daily_gold_stocks_report.md       │
└─────────────────────────────────────────────────────────────┘
```

### Stage 2 多智能体数据流

```
股票代码 + 日期
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  分析师团队（4 位并行）                                    │
│  Market Analyst → Social Analyst → News Analyst            │
│  → Fundamentals Analyst                                    │
│  每个分析师可调用专属工具集                              │
└──────────────────────────┬──────────────────────────────────┘
                           │ 4 份分析报告
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  研究员团队（多空辩论）                                    │
│  Bull Researcher ↔ Bear Researcher                          │
│  Research Manager 裁判 → investment_plan                   │
└──────────────────────────┬──────────────────────────────────┘
                           │ 投资计划
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  交易员（Trader）                                          │
│  将研报转化为具体交易计划                                   │
└──────────────────────────┬──────────────────────────────────┘
                           │ 交易计划
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  风控团队（3 方辩论）                                      │
│  Aggressive ↔ Conservative ↔ Neutral                       │
│  Portfolio Manager 裁判 → final_trade_decision             │
└──────────────────────────┬──────────────────────────────────┘
                           │ 最终决策 BUY / HOLD / SELL
                           ▼
报告输出（Markdown 分节存储）
```

---

## 2. Stage 1 — Screener 筛选器

Screener 是 A 股候选股票的发现引擎，核心文件位于 `tradingagents/screener/`。

### 2.1 数据访问层（ScreenerDataAccess）

**文件：** `tradingagents/screener/data_access.py`

ScreenerDataAccess 是整个筛选器的数据底座，采用 **5 级供应商链式降级** 架构，每个数据类型的请求都按优先级依次尝试各供应商，任一成功即返回，全部失败才报错。

#### 2.1.1 供应商链路总览

| 数据类型 | 第1优先级 | 第2优先级 | 第3优先级 | 第4优先级 | 第5优先级 |
|----------|-----------|-----------|-----------|-----------|-----------|
| **历史K线** | 腾讯直连 HTTP | AkShare 腾讯 | AkShare 新浪 | AkShare  BaoStock | yfinance |
| **实时行情** | 腾讯直连 HTTP | AkShare 腾讯 | AkShare 新浪 | — | — |
| **概念板块列表** | THS 同花顺 | — | — | — | — |
| **概念成分股** | THS HTML 爬虫 | THS API | 东方财富 | — | — |
| **资金流向** | THS 同花顺 | 东方财富 | — | — | — |
| **指数成分股** | AkShare CSIndex | — | — | — | — |
| **龙虎榜** | 东方财富 | — | — | — | — |

#### 2.1.2 腾讯直连 HTTP API

Screener 直接构造 HTTP 请求访问腾讯金融接口，无需经过 AkShare 中间层，延迟最低：

```
# 历史K线
GET https://web.ifzq.gtimg.cn/appstock/app/fqkline/get
  ?param=sh600519,day,,,320,qfq

# 实时行情
GET https://qt.gtimg.cn/q=sh600519
```

#### 2.1.3 THS HTML 爬虫

同花顺（THS）概念板块成分股通过解析 HTML 页面获取，URL 模板：

```
GET http://q.10jqka.com.cn/gn/detail/code/{board_code}/
```

`data_access._parse_ths_board_table()` 解析 HTML 中的股票列表，返回 `股票代码` + `股票名称` + `现价` + `涨跌幅` + `成交量` + `成交额` + `换手率`。

#### 2.1.4 请求限速（Anti-Ban）

`ThrottledRequester` 类实现进程级请求限速：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `base_interval` | 0.5s | 相邻请求最小间隔 |
| `burst_threshold` | 10 次 | 连续请求超此数触发暂停 |
| `burst_pause` | 2.0s | 触发 burst 后暂停时长 |
| `failure_penalty` | 1.5s | 请求失败后的额外等待 |
| `soft_rpm_limit` | 30 req/min | 软上限，超出仅警告 |

#### 2.1.5 缓存机制

- **历史数据缓存**：`self._hist_cache`（进程级 dict），Key = `(ticker, freq, start, end)`，避免 Stage A 和 Stage B 对同一股票重复请求历史数据
- **探测结果缓存**：JSON 文件缓存（TTL 60 分钟），Path = `.tradingagents/cache/screener/a0_probe_summary_v2.json`

#### 2.1.6 探测系统（Probe）

`ScreenerDataAccess._run_live_probes()` 在每次 run 时对 7 个数据模块发起真实探测请求，验证各 API 可用性，结果持久化到缓存供后续决策参考。

### 2.2 股票池构建（Universe）

**文件：** `tradingagents/screener/universe.py`

#### 2.2.1 6 种 Universe 模式

| 模式 | 描述 | 指数成分 |
|------|------|----------|
| `MVP` | 最小可行产品 | 沪深300 + 中证500 |
| `FULL` | 全市场扫描 | 沪深300 + 中证500 + 创业板指 + 科创50 + 中证1000 |
| `EXTENDED` | 扩展参数集 | 同 FULL |
| `EXPERIMENTAL` | 实验性策略 | 同 FULL |
| `FOCUSED` | 聚焦特定板块/主题/指数 | 用户指定 |
| `CUSTOM` | 自定义股票列表 | 用户提供 |

指数成分通过 AkShare CSIndex API 批量获取：

```python
ak.index_stock_cons_weight_csindex(symbol="000300")  # 沪深300
ak.index_stock_cons_weight_csindex(symbol="000905")  # 中证500
ak.index_stock_cons_weight_csindex(symbol="399006")  # 创业板指
ak.index_stock_cons_weight_csindex(symbol="000688")  # 科创50
ak.index_stock_cons_weight_csindex(symbol="000852")  # 中证1000
```

#### 2.2.2 FOCUSED 模式别名映射

支持中英文别名自动映射到同花顺概念板块：

```python
"半导体"/"chip"/"集成电路"  → 半导体板块
"人工智能"/"AI"/"算力"    → 人工智能板块
"新能源"/"光伏"/"储能"      → 新能源板块
"医疗"/"医药"/"biotech"    → 医疗器械/医药制造
"云计算"/"cloud"           → 云计算板块
"5g"/"物联网"              → 5G/物联网板块
```

### 2.3 Stage A 预筛选

**文件：** `tradingagents/screener/engine.py` — `ScreenerEngine._run_stage_a()`

Stage A 以快速失败策略在 500ms 内过滤无效股票，每只股票只做 4 项检查：

| 检查项 | 逻辑 | 阈值 |
|--------|------|------|
| **历史数据可用性** | 请求 100 天历史数据，任一为 `None` 即丢弃 | — |
| **数据行数下限** | 历史数据行数 < `thresholds.hist_rows_minimum` 丢弃 | 默认 30 行 |
| **流动性检查** | 计算 5 日平均换手率 < `low_turnover_rate` 丢弃 | 默认 2.0% |
| **涨跌停检测** | 最近 3 天任一 `pct_change` >= 9.9% 或 <= -9.9% 丢弃 | ±9.9% |

典型漏斗效果：沪深全市场 4000+ 股票 → Stage A 后约 500-2000 只。

### 2.4 三大策略引擎

所有策略共享统一的输出结构：`StrategyOutcome(cards, status, warnings)`，每张信号卡（SignalCard）包含打分（20-100 分）、证据快照（SignalEvidence）、风险标记（risk_flags）和标签（concept_tags）。

#### 2.4.1 TechnicalStrategy — 技术面策略

**文件：** `tradingagents/screener/strategies/technical.py`

**数据来源：**

- 主数据：历史 K 线（OHLCV，100 天 + 30 天 padding，前复权）
- 降级链路：腾讯 → AkShare 腾讯 → AkShare 新浪 → BaoStock → yfinance

**历史指标计算（`_compute_hist_metrics`）：**

| 指标 | 计算方法 |
|------|----------|
| MA20 / MA60 | 最近 20/60 行的收盘价均值 |
| `return_20d_pct` | `(close / close[-21] - 1) * 100` |
| `return_60d_pct` | `(close / close[-61] - 1) * 100` |
| `max_drawdown_pct` | `abs(min(drawdown_series))`，drawdown = `(close/cummax - 1) * 100` |
| `annualized_volatility_pct` | `returns.std() * sqrt(252) * 100` |
| `positive_days_ratio_pct` | `(returns > 0).mean() * 100` |
| `ma_spread_pct` | `(MA20 / MA60 - 1) * 100` |
| `volume_spike_ratio` | 最新成交量 / 20 日均量 |
| `trend_failure_streak` | 最近 12 行连续下跌的次数 |
| `support_loss_count` | 最近 20 行收盘价低于 MA20 的行数 |

**子评分公式：**

```
trend_alignment_score = base 40
  + 25 if close_above_ma20
  + 20 if close_above_ma60
  + 15 if ma20 >= ma60 > 0
  → clamp [0, 100]

momentum_score = min(100, max(20, 50 + return_20d * 1.2 + return_60d * 0.5))

drawdown_resilience_score = min(100, max(20, 100 - max_drawdown_pct * 2.2))

volatility_score = min(100, max(20, 100 - annualized_volatility_pct * 1.1))

trend_consistency_score = min(100, max(20,
  38 + positive_days_ratio * 45 + max(0, ma_spread_pct) * 1.1 - max_drawdown_pct * 0.6))

volume_confirmation_score = base 42
  + 30 if volume_spike_ratio >= 1.6 AND return_20d > 0
  + 18 if volume_spike_ratio >= 1.15 AND return_20d > 0
  - 10 if volume_spike_ratio <= 0.75 AND return_20d > 8
  + 8 if close_above_ma20 AND close_above_ma60

breakout_quality_score = base 38
  + 16 if close_above_ma20 AND close_above_ma60 AND return_20d > 0
  + min(18, ma_spread_pct * 2.2) if ma_spread_pct > 0
  + min(14, (recent_extension_pct - 2) * 2) if recent_extension_pct > 2
  + min(10, (volume_spike_ratio - 1) * 12) if volume_spike_ratio > 1

structure_risk_score = base 68
  - min(16, (recent_extension_pct - 4) * 1.8) if recent_extension_pct > 4
  - 10 if not close_above_ma20
  - 8 if not close_above_ma60
  - 12 if ma20 < ma60
  - 8 if trend_failure_streak >= 3
  - 7 if support_loss_count >= 8
  - 8 if max_drawdown_pct >= 18
  - 8 if annualized_volatility_pct >= 45
  - 8 if volume_spike_ratio >= 1.8 AND recent_extension_pct >= 8
  - 6 if return_20d > 10 AND volume_spike_ratio < 0.8
```

**技术面总分公式（`_build_total_score`）：**

```
base = (
  0.22 * trend_alignment_score
  + 0.18 * momentum_score
  + 0.14 * drawdown_resilience_score
  + 0.10 * volatility_score
  + 0.12 * trend_consistency_score
  + 0.11 * structure_risk_score
  + 0.07 * volume_confirmation_score
  + 0.04 * breakout_quality_score
  + 0.02 * volume_price_divergence_score
)
if fund_flow_verified: base += fund_flow_bonus  # 默认 3.0
if hist_rows < hist_rows_minimum: base -= hist_rows_penalty  # 默认 10.0
→ clamp [score_floor=20, score_ceiling=95]
```

**风险标记（Risk Flags）：**

| 标记 | 条件 |
|------|------|
| `trend_structure_extended` | `structure_risk_score <= 45` |
| `trend_consistency_weak` | `trend_consistency_score <= 48` |
| `volume_exhaustion_risk` | `volume_spike_ratio >= 1.8 AND recent_extension_pct >= 8` |
| `price_volume_divergence` | `volume_price_divergence_score <= 42` |
| `signal_consistency_low` | `signal_consistency_index <= 45` |

**趋势分类（trend_grade）：**

| 分类 | 条件 |
|------|------|
| `trend_confirmed` | `structure_risk_score >= 72 AND trend_alignment_score >= 70` |
| `recovery` | `structure_risk_score <= 42 OR trend_failure_streak >= 3` |
| `transition` | 其他情况 |

#### 2.4.2 SmartMoneyStrategy — 主力资金策略

**文件：** `tradingagents/screener/strategies/smart_money.py`

**数据来源：**

| 数据类型 | 来源 | 接口 |
|----------|------|------|
| 历史数据（动量） | 腾讯链路 / yfinance | `fetch_hist()` |
| 分时成交明细 | `fetch_tick_data(prefixed_symbol)` | `sh/sz/bj` 前缀格式 |
| 人气投票 | 百度 | `fetch_vote_baidu(symbol)` |
| 估值数据 | 百度 | `fetch_valuation_baidu()` |
| 龙虎榜当日明细 | 东方财富 | `fetch_lhb_sina(trade_date)` |
| 龙虎榜5日统计 | 东方财富 | `fetch_lhb_stats_sina("5")` |
| 龙虎榜机构席位 | 东方财富 | `fetch_lhb_institutional_stats_sina("5")` |

**子评分公式：**

```
tick_score = tick_no_type_base  # 默认 50.0
  + imbalance * 50.0            # (buy_weight - sell_weight) / total_volume
  + large_trade_bonus           # +2.0 per buy trade >= 100 volume, -2.0 per sell
  → clamp [20, 100]

tick_persistence_score = tick_persistence_base  # 默认 45.0
  + longest_consecutive_streak * 4.0
  → clamp [20, 100]

popularity_score = 40.0 + max(vote_cells) * 0.6
  → clamp [20, 100]; 默认 45.0（无数据时）

valuation_score = valuation_neutral  # 55.0
  + 20 if 0 < PE < 35
  - 15 if PE > 80 or PE < 0
  + 10 if 0 < PB < 5
  - 10 if PB > 10
  → clamp [20, 100]; 返回 None（未找到时用于中性化处理）

institutional_score = institutional_base  # 45.0
  + 23.0 if 在龙虎榜中
  + 16.0 if 成交额 > 5e8
  + 8.0  if 成交额 > 1e8
  → clamp [20, 100]; 默认 48.0（不在龙虎榜时）

lhb_continuity_score = lhbc_base  # 42.0
  + min(20, count * 4.0)  # count = 上榜次数
  + 10.0 if net > 0
  + min(15, buy_times * 3.0)
  + 8.0 if institutional_net > 0
  → clamp [20, 100]

quality_stability_index = (
  0.36 * multi_day
  + 0.32 * risk_constraint
  + 0.22 * continuity
  + 0.10 * max(20, 100 - max(0, heat_quality_gap))
)
→ clamp [20, 100]
```

**资金质量分类（capital_quality_tag）：**

| 分类 | 条件 |
|------|------|
| `capital_quality_high` | `tick>=68 AND multi_day>=68 AND continuity>=65 AND risk>=62 AND institutional>=68 AND heat_gap<=18` |
| `capital_quality_speculative` | `risk<=45 OR (tick>=72 AND continuity<=50) OR heat_gap>=22` |
| `capital_quality_persistent` | `continuity>=58 AND multi_day>=58` |
| `capital_quality_mixed` | 其他情况 |

**主力资金总分公式：**

```
score = min(100,
  0.24 * momentum
  + 0.11 * tick
  + 0.10 * tick_persistence
  + 0.12 * popularity
  + 0.11 * institutional
  + 0.10 * continuity
  + 0.10 * multi_day
  + 0.10 * valuation  # 如果返回 None，则用中性值 55.0 替代
  + 0.07 * risk_constraint
  + 0.10 * joint_quality
)
score += capital_quality_weight  # high=+5.0, persistent=+2.5, speculative=罚分, mixed=0
→ clamp [20, 100]
```

#### 2.4.3 PolicyStrategy — 政策策略

**文件：** `tradingagents/screener/strategies/policy.py`

**数据来源：**

| 数据类型 | 来源 | 接口 |
|----------|------|------|
| 概念板块列表 | THS 同花顺 | `fetch_concept_boards()` |
| 概念成分股 | THS | `fetch_concept_constituents(concept_name)` |
| 政策新闻 | 百度 | `fetch_policy_news_baidu(trade_date, look_back_days=7, limit=24)` |
| 指数成分股 | CSIndex API | `fetch_index_constituents(code)` |

**Phase 4 核心改进 — 概念地位评估（concept_weight）：**

传统 board_rank（今日涨跌排名）存在日间噪声和数据盲区问题。Phase 4 将其替换为**静态概念地位评估**，基于指数成分层级判断：

```
_index_tier_score(raw_code) =
  +28  if 沪深300成员 (HS300, 000300)
  +18  if 中证500成员 (CSI500, 000905) 或 创业板指成员 (CY50, 399006)
  +0   if 不在任何主要指数中

concept_membership_score(member_metrics) =
  +12  if 在THS板块成分列表中 (is_member=True)
  +0   if 不在列表中
```

**概念地位标签（concept_weight_bucket）：**

| 条件 | 标签 |
|------|------|
| 沪深300成员 + THS成员 | `concept_weight_core`（板块核心资产） |
| 中证500/创业板50成员 + THS成员 | `concept_weight_quality`（优质标的） |
| 只在THS列表中（非指数成分） | `concept_weight_secondary`（概念成员） |
| 不在任何列表中 | `concept_weight_unconfirmed`（未确认） |

**top_selection_score（概念选择分）：**

```
top_selection_score = 55.0
  + index_tier_score          # 0/18/28
  + concept_membership_score  # 0/12
  + min(10, concept_breadth * 0.12)
→ clamp [20, 100]
```

**Policy 总分公式：**

```
score = min(100,
  0.22 * concept_heat
  + 0.22 * stock_strength
  + 0.18 * relative_rank
  + 0.16 * board_leadership
  + 0.10 * cross_hit              # 85 if in universe hit, 40 otherwise
  + 0.05 * concept_competition
  + 0.05 * primary_concept
  + 0.04 * source_quality         # 75 with news, 45 without
  + 0.03 * concept_breadth
  + 0.02 * liquidity              # 68 - rank_index * 2, min 40
)
→ clamp [0, 100]
```

### 2.5 信号合并与冲突解决（Merger）

**文件：** `tradingagents/screener/merger/`（2026-08 从单文件 `merger.py` 拆出的包：`pipeline` / `aggregation` / `conflicts` / `filters` / `semantic` / `explanations`）

Merger 是整个筛选流程中最复杂的逻辑模块，负责将三策略的 SignalCard 合并、排序并过滤。

#### 2.5.1 合并算法

同一只股票可能同时被多个策略评分，合并公式为：

```
screening_score = min(100, max(0,
  weighted_avg
  + resonance_bonus                   # (source_count - 1) * 5
  + semantic_bonus                    # semantic_priority * 1.5 + alignment_bonus * 0.75
))
```

#### 2.5.2 冲突检测与分层

| 层级 | 条件 | 偏差 |
|------|------|------|
| `aligned` | 分差 <= 6 | +1 |
| `moderate` | 分差 7-12 | 0 |
| `high` | 分差 13-20 | -1 |
| `severe` | 分差 > 20 | -2 |

#### 2.5.3 冲突解决规则

| 规则 | 条件 | 行为 |
|------|------|------|
| `technical_veto_overrides_semantic` | `policy_strength>=2` + `speculative` + `tech_severity>=4` | -4 |
| `semantic_consensus_priority` | `policy_strength>=2` + `high/persistent capital` + `tech_severity<=1` | +3 |
| `weak_policy_discount` | `policy_strength=0` + `tech_severity>=3` | -3 |
| `speculative_flow_discount` | `speculative capital` + `tech_severity>=3` | -2 |

#### 2.5.4 10 重硬过滤器（Hard Filters）

| # | 过滤器 | 条件 |
|---|--------|------|
| 1 | ST/\*ST 过滤 | 公司名或 sector_tags 含 ST/\*ST |
| 2 | 接近跌停 | `change_pct <= -9.9%` |
| 3 | 流动性不足 | 换手率 < 2.0% |
| 4 | 流通市值过低 | 流通市值 < 30 亿 |
| 5 | 负 PE | `pe_ttm < 0` |
| 6 | 极端 PE | `pe_ttm > 150` |
| 7 | 投机资金流 + 弱信号 | `speculative` + 非 top/core + score < 78 |
| 8 | 热度-质量断层 | `heat_quality_gap >= 28` + `speculative/mixed` |
| 9 | 技术结构风险 + 低信号 | `structure_risk <= 35` + `consistency <= 45` + score < 78 |
| 10 | 冲突否决 | `policy+speculative+tech>=4` + score < 82 |

#### 2.5.5 分散化限制

| 限制项 | 值 |
|--------|-----|
| 同概念/行业最多候选 | 2 只 |
| MVP 最大输出 | 3 只 |
| EXTENDED/EXPERIMENTAL/FULL 最大输出 | 5 只 |

### 2.6 Deep Analyzer 深度分析

**文件：** `tradingagents/screener/engine.py` — `DeepAnalyzer`

在 Merger 输出候选股票后，Deep Analyzer 对每只股票进行 LLM 驱动的语义级质量评估。配置项：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_stocks` | 3 | 最大深度分析股票数 |
| `delay_between_stocks` | 2.0s | 两次分析间延迟（防 API 超限） |
| `retry_on_failure` | True | 失败自动重试 |

Deep Analyzer 调用 `TradingAgentsGraph` 的单股票分析模式（可复用 Stage 2 的多智能体分析引擎），输出包含最终决策、Token 消耗和执行时间。

### 2.7 报告生成（Report）

**文件：** `tradingagents/screener/report.py`

#### 2.7.1 输出文件

| 文件名 | 格式 | 路径 |
|--------|------|------|
| `screening_result.json` | JSON | `{results_dir}/screener/{run_id}/` |
| `daily_gold_stocks_report.md` | Markdown | `{results_dir}/screener/{run_id}/` |

#### 2.7.2 JSON 报告内容

完整 Pydantic 模型序列化，包含：
- 运行元数据（run_id、模式、日期、耗时）
- 股票池规模与构建方式
- 各策略运行状态（ready/degraded）
- 能力探测结果（7 模块 × 各供应商状态）
- 候选股列表（含评分、置信度、风险标记、策略来源）
- 被过滤股票列表（含过滤原因）
- Deep Analysis 结果

---

## 3. Stage 2 — Analyzer 多智能体深度分析

Stage 2 对单只股票进行完整的多智能体协同分析，核心文件位于 `tradingagents/graph/` 和 `tradingagents/agents/`。

### 3.1 LangGraph 架构

**文件：** `tradingagents/graph/trading_graph.py`

系统基于 **LangGraph** 构建有向状态图，使用 `AgentState`（TypedDict）作为全局状态容器，在节点间流转。关键特性：

- **状态聚合模式**：使用 `Annotated[..., operator.add]` 实现消息追加（辩论历史），使用覆写实现单值字段更新
- **条件路由**：`ConditionalLogic` 根据当前状态决定下一个执行节点
- **流式执行**：`graph.stream()` 支持实时输出每个节点的中间结果（用于 Live Dashboard）

### 3.2 分析师团队（Analyst Team）

4 位分析师顺序执行，每位可按需调用工具：

| 分析师 | 职责 | 主要工具 |
|--------|------|----------|
| `Market Analyst` | 技术分析（K线、均线、动量） | `get_stock_data`, `get_indicators` |
| `Social Analyst` | 社交媒体情绪（Twitter/Reddit） | `get_news` |
| `News Analyst` | 全球财经新闻 | `get_global_news` |
| `Fundamentals Analyst` | 财务报表与估值 | `get_fundamentals`, `get_balance_sheet` |

分析师执行模式：`Analyst → Tools（按需） → Msg Clear → Next Analyst`

### 3.3 研究员团队（Researcher Team）

| 角色 | 文件 | 职责 |
|------|------|------|
| `Bull Researcher` | `agents/researchers/bull_researcher.py` | 挖掘看多逻辑，强调增长机会 |
| `Bear Researcher` | `agents/researchers/bear_researcher.py` | 挖掘看空逻辑，强调风险因素 |
| `Research Manager` | `agents/managers/research_manager.py` | 裁判多空辩论，产出 `investment_plan` |

### 3.4 交易员（Trader）

**文件：** `tradingagents/agents/trader/trader.py`

将研究员团队的投资计划转化为具体交易计划，包含：入场价格区间、目标持仓比例、风险预算、止损建议。

### 3.5 风控团队（Risk Management）

| 角色 | 文件 | 视角 |
|------|------|------|
| `Aggressive Analyst` | `agents/risk_mgmt/aggressive_debater.py` | 高风险高收益 |
| `Conservative Analyst` | `agents/risk_mgmt/conservative_debator.py` | 低风险稳健 |
| `Neutral Analyst` | `agents/risk_mgmt/neutral_debater.py` | 平衡视角 |
| `Portfolio Manager` | `agents/managers/portfolio_manager.py` | 最终裁判，产出 `final_trade_decision` |

### 3.6 辩论机制详解

#### 3.6.1 多空辩论（Investment Debate）

- **状态结构**：`InvestDebateState`，包含 `bull_history`、`bear_history`、`history`（均为追加模式）
- **循环次数**：`max_debate_rounds`（默认 1，可通过 CLI 配置为 1/3/5）
- **路由逻辑**：`ConditionalLogic.should_continue_debate()`
  - `count >= 2 * max_debate_rounds` → 退出辩论，提交 Research Manager
  - 否则按 `latest_speaker` 决定下一位发言人

#### 3.6.2 风控辩论（Risk Debate）

- **状态结构**：`RiskDebateState`，包含三方的 `aggressive_history`、`conservative_history`、`neutral_history`
- **循环模式**：Aggressive → Conservative → Neutral → 重复
- **退出条件**：每个分析师至少发言一次 + `count >= 3 * max_risk_discuss_rounds`

#### 3.6.3 自适应辩论轮数

系统根据路由决策动态调整辩论深度：

| 信号类型 | 条件 | 轮数调整 |
|----------|------|----------|
| `policy_top_stock` + 高质量 + 一致冲突 | — | +1 轮 |
| `capital_quality_speculative` | — | -1 轮（缩短） |
| `conflict_tier: high/severe` | — | 强化辩论 |

### 3.7 记忆系统（Memory）

**文件：** `tradingagents/agents/utils/memory/`（2026-08 从单文件 `memory.py` 拆出的包：`store` / `retrieval` / `analytics` / `basic`）

Phase 3 引入了 5 个独立记忆实例，为不同角色保留跨会话上下文：

| 记忆实例 | 持有者 | 用途 |
|----------|--------|------|
| `bull_memory` | Bull Researcher | 历史看多经验 |
| `bear_memory` | Bear Researcher | 历史看空经验 |
| `trader_memory` | Trader | 历史交易决策 |
| `invest_judge_memory` | Research Manager | 历史裁判判断 |
| `portfolio_manager_memory` | Portfolio Manager | 历史最终决策 |
| `route_memory` | 路由系统 | 结构化路由模式存储 |

记忆检索：基于语义相似度搜索（`memory.get_memories(situation, n_matches)`）。

---

## 4. CLI 交互界面

### 4.1 统一主菜单

**文件：** `cli/main_menu.py`

- **UI 框架**：Rich (`Console`, `Panel`, `Table`, `Prompt`)
- **交互逻辑**：`while True` 循环，通过 `Prompt.ask()` 接受输入
- **入口路由**：
  - `python -m cli`
  - `python -m tradingagents`
  - `python -m tradingagents analyze/screener/report`

#### Analyzer 8 步问卷

| 步骤 | 内容 | 选项数 |
|------|------|--------|
| 1 | 股票代码 | 自由输入（支持 600519/sh600519/SPY 等格式） |
| 2 | 分析日期 | `YYYY-MM-DD`，未来日期禁止 |
| 3 | 输出语言 | 12 种语言（含自定义） |
| 4 | 分析师团队 | Market / Social / News / Fundamentals（多选） |
| 5 | 研究深度 | Shallow（1轮）/ Medium（3轮）/ Deep（5轮） |
| 6 | LLM 提供商 | OpenAI / Google / DeepSeek / Qwen / Claude 等 10 种 |
| 7 | Thinking 模型 | quick 模型 + deep 模型 |
| 8 | 推理配置 | Google/OpenAI/Anthropic 特有推理参数 |

#### Screener 6 步问卷

| 步骤 | 内容 |
|------|------|
| 1 | 模式选择：FULL / FOCUSED / CUSTOM / MVP / EXTENDED / EXPERIMENTAL |
| 2 | 交易日期 |
| 3 | 范围定义（FOCUSED/CUSTOM 特有） |
| 4 | 输出选项（最大候选数、Deep Analyzer 开关、周末开关） |
| 5 | 汇总确认（含风险提示） |
| 6 | 执行 |

### 4.2 Live Dashboard 实时仪表盘

**文件：** `tradingagents/ui/live_dashboard.py`

Bloomberg Terminal 风格的 4 面板实时仪表盘，底层使用 Rich `Live` 组件：

```
┌──────────────────────────┬──────────────────────┐
│     PROGRESS             │   AGENT STATUS       │
│   Stage 1 ●○○○ RUNNING  │   ✓ Market Analyst    │
│   Stage A ○○○○ WAIT     │   ● Social Analyst    │
│   Stage B ○○○○ WAIT     │   ○ News Analyst      │
│   Stage C ○○○○ WAIT     │   ○ Fundamentals      │
├──────────────────────────┴──────────────────────┤
│            EVENT TRAIL                          │
│  [14:30:01] Market Analyst: research started  │
│  [14:32:15] News Analyst: completed           │
│  [14:35:42] Debate in progress...             │
├────────────────────────────────────────────────┤
│              METRICS                           │
│  LLM: 42  Tools: 128  ↑2.1M  ↓340K  ⏱ 05:23 │
└────────────────────────────────────────────────┘
```

**刷新策略**：双重触发 — 每个 graph chunk 到达时立即刷新（chunk-triggered），同时以 3 秒为周期定时刷新（timer fallback）。线程安全通过 `threading.RLock` 保证。

**面板状态图标**：`✓`（完成，绿）、`●`（运行中，青）、`✗`（错误，红）、`○`（等待，黄）。

### 4.3 分析报告汇总页

**文件：** `tradingagents/ui/summary.py`

- **技术报告页**：显示 ticker、决策（颜色编码 BUY=HOLD=SELL）、置信度进度条（█/░ Unicode 块）、耗时、LLM/工具调用次数、Token 总计
- **Screener 汇总页**：候选股排名表（rank、ticker、name、score、key reasons）
- **Markdown 渲染**：使用 Rich `Markdown()` 直接渲染分析报告中各节（市场分析、舆情分析、新闻研判、最终决策等）

---

## 5. LLM 多提供商支持

### 5.1 LLM 客户端工厂

**文件：** `tradingagents/llm_clients/factory.py`

工厂模式支持 10+ LLM 提供商，通过 `create_llm_client(provider, model, **kwargs)` 创建客户端实例。支持的协议：

| 协议类型 | 提供商 |
|----------|--------|
| OpenAI 兼容 | OpenAI、XAI、DeepSeek、Qwen、GLM、Ollama、OpenRouter |
| Anthropic 专用 | Anthropic（Claude 系列） |
| Google 专用 | Google（Gemini 系列） |
| Azure 专用 | Azure OpenAI |

### 5.2 支持的提供商与模型

| 提供商 | API Key 环境变量 | 特色功能 |
|--------|------------------|----------|
| **OpenAI** | `OPENAI_API_KEY` | `reasoning_effort` 参数（medium/high/low） |
| **Google** | `GOOGLE_API_KEY` | `thinking_level` 参数（high/minimal） |
| **Anthropic** | `ANTHROPIC_API_KEY` | `effort` 参数（high/medium/low） |
| **DeepSeek** | `DEEPSEEK_API_KEY` | V3/Chat 系列 |
| **Qwen（阿里云）** | `DASHSCOPE_API_KEY` | 通义千问系列 |
| **GLM（智谱）** | `ZHIPU_API_KEY` | GLM 系列 |
| **xAI** | `XAI_API_KEY` | Grok 系列 |
| **OpenRouter** | `OPENROUTER_API_KEY` | 100+ 模型一站式路由 |
| **Azure OpenAI** | `.env.enterprise` | 企业版 GPT-4 等 |
| **Ollama** | `llm_provider: "ollama"` | 本地模型（Llama/Qwen 等） |

### 5.3 双模型架构（Deep + Quick）

TradingAgentsGraph 在初始化时配置两个 LLM：

| 模型角色 | 用途 | 模型示例 |
|----------|------|----------|
| `deep_think_llm` | 复杂推理节点（Research Manager、Portfolio Manager） | GPT-5.4、GPT-5.5、Gemini 3.1 Pro |
| `quick_think_llm` | 快速分析节点（Analysts、Researchers、Trader） | GPT-5.4-mini、Gemini 3.5 Flash |

---

## 6. 工具系统与数据流

### 6.1 数据流接口路由

**文件：** `tradingagents/dataflows/interface.py`

接口层通过 `route_to_vendor()` 根据工具类别和配置路由到对应的数据供应商：

```
TOOLS_CATEGORIES = {
    "core_stock_apis":      ["get_stock_data"],
    "technical_indicators": ["get_indicators"],
    "fundamental_data":     ["get_fundamentals", "get_balance_sheet",
                              "get_cashflow", "get_income_statement"],
    "news_data":            ["get_news", "get_global_news",
                              "get_insider_transactions"],
    "cn_macro_data":        ["get_cn_macro_data", "get_cn_rate_outlook",
                              "get_cn_trade_data"],
    "cn_event_data":        ["get_cn_earnings_calendar", "get_cn_ipo_data",
                              "get_cn_limit_up_stocks"],
}
```

### 6.2 核心工具清单

所有工具使用 `@tool` 装饰器（LangChain）定义，通过 `route_to_vendor()` 路由：

#### 股票数据工具（`core_stock_tools.py`）

```python
@tool
def get_stock_data(symbol, start_date, end_date) -> str
    # 通过配置供应商获取 OHLCV 数据
```

#### 技术指标工具（`technical_indicators_tools.py`）

```python
@tool
def get_indicators(symbol, indicator, curr_date, look_back_days=30) -> str
    # 支持：rsi, macd, macds, macdh, boll, boll_ub, boll_lb,
    #       atr, close_50_sma, close_200_sma, close_10_ema, vwma, mfi
```

#### 基本面数据工具（`fundamental_data_tools.py`）

```python
@tool
def get_fundamentals(ticker, curr_date) -> str
    # 公司概览：估值、股本结构、公司信息

@tool
def get_balance_sheet(ticker, freq="quarterly", curr_date=None) -> str
    # 资产负债表：资产、负债、权益

@tool
def get_cashflow(ticker, freq="quarterly", curr_date=None) -> str
    # 现金流量表：经营、投资、融资现金流

@tool
def get_income_statement(ticker, freq="quarterly", curr_date=None) -> str
    # 利润表：营收、毛利、营业利润、净利润
```

#### 新闻数据工具（`news_data_tools.py`）

```python
@tool
def get_news(ticker, start_date, end_date) -> str       # 股票新闻（RAG 增强）
@tool
def get_global_news(curr_date, look_back_days=7, limit=5) -> str  # 全球宏观事件
@tool
def get_insider_transactions(ticker) -> str              # 内部交易（美股）/ 资金流（A股）
@tool
def get_cn_policy_news(curr_date, look_back_days=7, limit=6) -> str  # A股政策新闻
@tool
def get_cn_market_flow(ticker) -> str                    # A股主力资金流
```

#### A股宏观数据工具（`cn_macro_tools.py`）

```python
@tool
def get_cn_macro_data(indicators, period="quarterly", limit=8) -> str
    # GDP, CPI, PPI, M2, 贷款、工业生产

@tool
def get_cn_rate_outlook(focus="all") -> str
    # LPR, SHIBOR, 汇率

@tool
def get_cn_trade_data(months=12, focus="all") -> str
    # 进口/出口/贸易差额
```

#### A股事件数据工具（`cn_event_tools.py`）

```python
@tool
def get_cn_earnings_calendar(look_forward_days=30, market="all") -> str
    # A股业绩预告/公告日历

@tool
def get_cn_ipo_data(status="upcoming", limit=20) -> str
    # IPO 数据

@tool
def get_cn_limit_up_stocks(trade_date, limit=30) -> str
    # 涨停股统计

@tool
def get_cn_stock_pledge(ticker, look_back_days=30) -> str
    # 股权质押数据

@tool
def get_cn_m_a_news(ticker, look_back_days=90, limit=10) -> str
    # 并购重组新闻
```

#### A股板块新闻工具（`cn_sector_news_tools.py`）

```python
@tool
def get_cn_tech_sector_news(ticker, curr_date, look_back_days=7) -> str
@tool
def get_cn_new_energy_news(ticker, curr_date, look_back_days=7) -> str
@tool
def get_cn_pharma_news(ticker, curr_date, look_back_days=7) -> str
@tool
def get_cn_real_estate_news(curr_date, look_back_days=7) -> str
@tool
def get_cn_fintech_news(ticker, curr_date, look_back_days=7) -> str
```

---

## 7. 技术栈总览

### 核心依赖

| 类别 | 库 | 用途 |
|------|-----|------|
| **多智能体编排** | `langgraph>=0.4.8` | 有向状态图、多智能体协作 |
| **LLM 集成** | `langchain-core>=0.3.81` | 工具绑定、Prompt 管理 |
| **LLM 专用** | `langchain-anthropic`, `langchain-google-genai`, `langchain-openai` | 各提供商适配 |
| **A 股数据** | `akshare` | 概念板块、资金流、龙虎榜、指数成分 |
| **全球数据** | `yfinance>=0.2.63` | 美股/港股历史数据 |
| **技术指标** | `stockstats>=0.6.5` | RSI、MACD、布林带等 |
| **回测引擎** | `backtrader>=1.9.78.123` | 交易策略回测 |
| **数据处理** | `pandas>=2.3.0` | DataFrame 操作 |
| **终端 UI** | `rich>=14.0.0` | Bloomberg 风格交互界面 |
| **HTTP 请求** | `requests>=2.32.4` | 腾讯直连 API |
| **环境变量** | `python-dotenv` | API Key 配置 |
| **RAG 检索** | `rank-bm25>=0.2.2` | 关键词 + 语义混合检索 |
| **可选缓存** | `redis>=6.2.0` | 分布式 Token 缓存 |

### HTTP 伪装

ScreenerDataAccess 对所有 HTTP 请求注入浏览器标准 Header（User-Agent、Accept、Referer 等），模拟浏览器访问，降低被反爬机制拦截的风险。

---

## 8. 开发阶段路线图

> **重要说明：** 原始 TradingAgents（上游 TauricResearch/TradingAgents）的 Analyzer 采用简单的线性多智能体流程——4位分析师顺序执行 → 多空辩论 → 风控辩论 → 决策。各阶段之间的信息传递是简单的文本拼接，缺乏上下文压缩、语义路由和可观测性。本项目在初始提交（Phase 1）中即对 Analyzer 架构做了根本性重构，并新增了 Screener 选股引擎、Harness 可观测性、A 股专属数据接口等模块，后续 commits 在此基础上持续迭代。

### 8.1 Phase 1 vs 上游原始版本的对比

#### 原始 Analyzer 架构的缺陷

| 缺陷 | 原始实现 | 问题表现 |
|------|----------|----------|
| **辩论机械** | Bull/Bear 轮流发言，count-based 退出 | 缺乏真实推理，Agent 只是轮流输出文本 |
| **无上下文压缩** | 各阶段全量文本直接传递 | 上下文快速膨胀，token 消耗极高 |
| **无路由决策** | 所有标的走相同流程 | 简单标的和复杂标的没有区分 |
| **无记忆系统** | 仅有一个 `TradingMemoryLog` | 无法积累跨会话经验 |
| **无工具抽象** | 工具直接硬编码在 Agent 内 | 无法根据标的类型动态选择工具 |
| **无 A 股数据** | 依赖 yfinance（美股为主） | 无法获取 A 股概念板块，资金流、龙虎榜等数据 |

#### Phase 1 的核心重构（对比上游）

| 维度 | 上游原始版本 | Phase 1 重构版本 | 改进效果 |
|------|------------|----------------|----------|
| **辩论机制** | 49 行 `Reflector`，仅 1 个方法，输出 2-4 句纯文本 | 1117 行 `Reflector`，15+ 方法，支持逐 Agent 反思 + 路由洞察 + 混合总结 | 辩论质量质的提升 |
| **图结构** | 136 行 `setup.py`，14 个节点，线性流程 | 753 行 `setup.py`，25+ 节点，4 个路由拦截器 + 4 个压缩总结节点 | 智能路由 + 上下文压缩 |
| **上下文压缩** | 无 | 每个阶段边界有 LLM 压缩（Token 阈值 18K） | Token 消耗大幅降低 |
| **状态管理** | `AgentState` 平铺字段 | 引入 `structured` 嵌套块（decision_blocks/debate_blocks/analyst_reports） | 状态清晰、可追溯 |
| **记忆系统** | 1 个 `TradingMemoryLog`（JSON 简单存储） | 6 个 `FinancialSituationMemory`（各角色独立）+ 1 个 `StructuredMemory`（路由模式） | 跨会话智能积累 |
| **工具系统** | 硬编码工具绑定 | `get_tools_for_analyst()` + `instrument_profile` 抽象，按标的类型动态选择工具 | 灵活性大幅提升 |
| **A 股数据** | 无 | `dataflows/akshare_interface.py` + `cn_*_tools.py` | A 股市场全面支持 |
| **图行数** | `reflection.py` 49 行，`setup.py` 136 行 | `reflection.py` 1117 行，`setup.py` 753 行 | 增 1685 行核心逻辑 |

#### Phase 1 新增的 4 类智能节点

```
阶段边界拦截器（Orchestration Router）：
  分析师团队 → "Route Research Phase" → 多空研究员
  多空辩论 → "Route Trader Phase" → 交易员
  交易计划 → "Route Risk Phase" → 风控分析师
  风控辩论 → "Route Portfolio Phase" → 投资组合经理

阶段压缩总结器（Phase Handoff）：
  "Summarize Analyst Phase"   → 聚4位分析师报告为1份压缩备忘录
  "Summarize Research Phase"  → 聚多空辩论结论为1份备忘录
  "Summarize Trader Phase"    → 聚交易计划为1份备忘录
  "Summarize Risk Phase"      → 聚风控辩论为1份备忘录
```

### 8.2 全阶段路线图

| Phase | 名称 | 状态 | 核心交付 |
|-------|------|------|----------|
| **Phase 1** | A股 Analyzer 重构 + Screener 选股引擎 | ✅ 完成 | LangGraph 架构重构（路由/压缩/记忆）、6 大选股策略、A 股数据接口 |
| **Phase 2** | Bug 修复 + CLI 美化 | ✅ 完成 | 12 个 Bug 修复，Bloomberg Terminal 风格 Typer CLI |
| **Phase 3** | Harness 可观测性 + Skills | ✅ 完成 | 25+ 内置 Skill，决策类型路由，成本追踪，Token 统计，记忆系统 |
| **Phase 4** | 概念地位评分重构 | ✅ 完成 | board_rank → concept_weight，基于指数成分股替代日间涨跌排名 |
| **Phase 5** | 统一 CLI + Live Dashboard | ✅ 完成 | 单一入口 + 主菜单循环 + 4 面板实时仪表盘 |
| **Phase 6** | HTML 报告导出 | 🔨 规划中 | 将 Markdown 报告渲染为交互式 HTML |
| **Phase 7** | 回测集成 | 🔨 规划中 | 与 Backtrader 集成，验证历史信号效果 |

### 8.3 初始提交包含的子系统（上古 vs 新增）

上游原始版本仅有 64 个 Python 文件，本项目初始提交包含 130 个 Python 文件。新增子系统如下：

| 子系统 | 文件数 | 核心功能 |
|--------|--------|----------|
| **Screener 选股引擎** | 25+ | 6 大策略、信号合并、冲突解决、Deep Analyzer |
| **Harness 可观测性** | 20+ | Skill 注入、成本追踪、Token 计数、上下文注入 |
| **A 股数据接口** | 15+ | AkShare A 股数据、政策宏观事件、龙虎榜，资金流 |
| **RAG 检索系统** | 8+ | 向量存储、检索器、重排模型、CN 新闻增强 |
| **UI 终端界面** | 6+ | Bloomberg 风格 Live Dashboard、主题配色，品牌吉祥物 |
| **CLI 命令系统** | 15+ | 统一入口、8 步问卷、报告查看器 |
| **A 股专属工具** | 6+ | 宏观数据、板块新闻、事件日历、限售股等 |

---

## 附录：2026-08 代码质量整理（大文件存量拆分）

B 组六大千行文件全部拆分完成，公开 API / 调用路径零改动（均以门面 + 重导出承接，`*_legacy.py` 保留待删）：

| 文件（原行数） | 拆分后组织 | 新增测试护栏 |
|---|---|---|
| `screener/data_access.py`（1905） | 门面 546 行 + `vendors/` + `capability.py` + `response_parsers.py` + `ticker_formats.py` + `vendor_http.py` | +43 |
| `dataflows/akshare_interface.py`（1619） | 门面 41 行 + `dataflows/akshare/` 领域包 | +9 |
| `graph/reflection.py`（1302） | `graph/reflection/` 包（extraction / route_analytics / reflector / conclusion） | +9 |
| `agents/utils/memory.py`（1124） | `agents/utils/memory/` 包（store / retrieval / analytics / basic） | +18 |
| `screener/merger.py`（1050） | `screener/merger/` 包（pipeline / aggregation / conflicts / filters / semantic / explanations） | +25 |
| `agents/utils/agent_utils.py`（944） | 门面 37 行 + `agents/utils/tools/` | +9 |
| `graph/setup.py`（829） | `setup_graph()` 拆为 8 个阶段构建方法（471 → 38 行编排器） | +4 |

另有 `ports/market_data.py`（MarketDataPort）消灭数据层反向依赖与依赖环、`dataflows/errors.py` 类型化供应商错误、`application/` 契约层（AnalysisRequest/Result + 执行事件协议）。当前离线测试护栏 **385 个用例**，全部无网络、无 LLM。

---

*本文档由 TradingAgents Team 维护，最后更新于 2026-08。*
