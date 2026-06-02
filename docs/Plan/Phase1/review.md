# TradingAgents 2.0 项目复盘文档

> **更新日期**: 2026-05-12
> **文档状态**: 收口阶段 - 以验收闭环为主，非功能开发阶段

---

## 一、项目阶段定位

### 当前阶段：收口 + 验收闭环

本项目已完成从零到有的核心功能建设，当前处于**收口阶段**，主要任务：

1. 验收证据补齐（真实 run artifact）
2. 文档口径对齐
3. 参数漂移防护
4. 最小回归测试稳定

---

## 二、全新增加的模块

### 1. **Screener 模块** (新增，约 20+ 文件)

实现主动选股引擎，是 2.0 区别于原版的核心新增：

| 文件 | 功能 |
|------|------|
| `screener/engine.py` | 选股引擎主入口，与 Trading Graph 已联动 |
| `screener/config.py` | 配置管理 |
| `screener/models.py` | 数据模型 (SignalCard, ScreeningResult) |
| `screener/merger.py` | 信号卡合并与冲突解决 |
| `screener/deep_analyzer.py` | Deep Analyzer 深度分析编排 |
| `screener/report.py` | 报告生成，含 semantic_home_chain |
| `screener/universe.py` | 股票池构建 |
| `screener/data_access.py` | 数据访问接口 |
| `screener/strategies/technical.py` | 技术面策略 |
| `screener/strategies/policy.py` | 政策面策略 |
| `screener/strategies/smart_money.py` | 聪明钱策略 |
| `screener/cli/` | 独立 CLI 入口 |

### 2. **DataFlows 模块** (新增)

- `dataflows/interface.py` - 统一数据接口
- `dataflows/akshare_interface.py` - AkShare 中国数据源（**补充/legacy**）
- `dataflows/config.py` - 数据流配置

### 3. **RAG 模块** (新增)

- `agents/utils/rag/` - 完整 RAG 实现
  - `cn_news_retriever.py` - 中国新闻检索
  - `retriever.py` / `reranker.py` / `vector_store.py`

### 4. **Harness 增强**

- `graph/conditional_logic.py` - 条件逻辑路由
- `graph/reflection.py` - Reflection 反思机制
- `graph/signal_processing.py` - 信号处理

---

## 三、数据源架构（关键纠正）

### ⚠️ 当前基线：Tencent-first

| 数据源 | 定位 |
|--------|------|
| **Tencent** | **主数据源（当前基线）** |
| AkShare | 补充 / legacy fallback |
| yfinance | 辅助参考 |

> **证据**: `config.py`、`data_access.py` 中腾讯接口作为首选，AkShare 为降级路径。

---

## 四、原模块的改造

### 1. **Tool System (L2)**

| 原版 | 2.0 改造 |
|------|----------|
| yfinance 为主 | **Tencent-first**，AkShare 为补充 |
| 单一数据源 | **vendor fallback 机制** |
| 无 instrument profile | **instrument profile 体系** |
| 无 style bucket | **style bucket 路由** |

### 2. **Execution Orchestration (L3)**

| 原版 | 2.0 改造 |
|------|----------|
| 固定线性流程 | **状态驱动轨道** |
| 固定跳转 | **条件边路由** |
| 无 handoff 压缩 | **Handoff Summary 节点** |
| 无风险辩论收口 | **Finalize Risk Debate 节点** |
| 无路由洞察 | **route_history / route_insight** |

### 3. **State & Memory (L4)**

| 原版 | 2.0 改造 |
|------|----------|
| 散乱聊天上下文 | **结构化状态块** |
| 字符串 memory | **结构化 memory schema** |
| 无 event_trail | **event_trail 追踪** |

---

## 五、核心新功能一览

| 功能 | 状态 | 说明 |
|------|------|------|
| **Screener 选股引擎** | ✅ 已实现 | 两阶段架构 |
| **三策略评分体系** | ✅ 已实现 | Technical / Policy / Smart Money |
| **semantic_home_chain** | ✅ 已实现 | trigger → route → execution → decision |
| **参数化配置** | ⚠️ 部分完成 | 大部分阈值已配置化，策略内部仍有少量常量 |
| **Deep Analyzer** | ✅ 已实现 | 多 Agent 深度论证 |
| **RAG 新闻检索** | ✅ 已实现 | 带重排的中国新闻检索 |
| **条件逻辑路由** | ✅ 已实现 | 基于状态的动态路由 |
| **CLI 独立入口** | ✅ 已实现 | screener 专用 CLI |

---

## 六、未完成尾项（收口阶段待办）

| 任务 | 优先级 | 状态 |
|------|--------|------|
| 真实 run artifact 验收闭环 | 高 | 进行中 |
| 技术文档与代码同步 | 中 | 待处理 |
| 环境依赖差异文档化 | 低 | 建议补充 |

---

## 七、风险提示

### ⚠️ 环境依赖差异

- 不同环境（Windows/Linux/Docker）的依赖版本差异可能影响测试复现口径
- AkShare 数据接口在部分环境可能不稳定
- 建议在 CI/CD 中锁定依赖版本

### ⚠️ 参数化收口

- Screener 核心阈值已大幅配置化
- 但 `technical.py`、`smart_money.py` 内部仍有少量硬编码常量
- 方向正确，尚未 100% 闭环

---

## 八、与原版核心区别

```
原版 TradingAgents:
  单票分析 → 多 Agent 辩论 → 决策

2.0 TradingAgents:
  全市场初筛 → 多策略评分 → 信号卡合并 → Deep Analyzer → Top 3 金股深度论证
       ↑                              ↑
   新增 Screener              增强的 Harness Orchestration
```

---

## 九、验收证据（Plan_final.md）

根据 `docs/Plan_final.md` Section 5 完工打勾区：

- [x] Task 1: A2-technical 参数化收口完成
- [x] Task 2: A2-smart_money 参数化补齐完成
- [x] Task 3: A5 首页链路去漂移收口完成
- [x] Task 4: A6 最小契约加固完成
- [x] Task 5: 真实 artifact 验收完成（run_id: 16eb73e5-09fb-4929-a27f-65906a197507）
- [x] 最小回归测试：59/59 PASS

---

## 十、结论

2.0 版本在原版基础上实现了：

1. **Screener 模块** - 主动选股引擎（原版没有）
2. **多策略评分体系** - Technical/Policy/Smart Money 三维评分
3. **Harness 架构** - 状态驱动执行编排（原版是线性流程）
4. **RAG 系统** - 中国新闻检索与重排
5. **Deep Analyzer** - 多 Agent 深度论证框架
6. **Tencent-first 数据源** - 中国A股数据主干的现代化架构

> **数据源澄清**: 原描述"AkShare 为主干"不准确，当前基线是 **Tencent-first**，AkShare 是补充/legacy。
