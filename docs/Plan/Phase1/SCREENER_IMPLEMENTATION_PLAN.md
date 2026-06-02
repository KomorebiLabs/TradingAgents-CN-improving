# Stage 1: The Screener — 实施计划文档 (V1.0)

> **对应设计文档**: [SCREENER_DESIGN.md](./SCREENER_DESIGN.md)
> **文档版本**: V1.0
> **创建日期**: 2026-05-07
> **用途**: 作为 Screener 最新一轮开发的执行计划与验收依据

---

## 1. 文档目的

本文档是 `SCREENER_DESIGN.md` 的实施拆解版，目标不是重复设计，而是把设计变成可以逐步编码、逐步验证、逐步收敛的开发路线图。

本文档回答四个问题：

1. 先做什么
2. 每一步改哪些文件
3. 每一步产出什么
4. 每一步如何验收

---

## 2. 实施总原则

### 2.1 开发原则

1. 先验证数据源假设，再写主流程。
2. 先搭数据契约，再写策略逻辑。
3. 先做单策略闭环，再做策略融合。
4. 先保证可降级，再追求更强信号。
5. 先保证与现有 Harness 兼容，再考虑更深耦合。

### 2.2 明确不做

本轮实施不做以下内容：

- 不改 `TradingAgentsGraph.propagate()` 的函数签名
- 不做抓数并发
- 不做盘中高频更新
- 不做完整回测系统
- 不把质押硬过滤作为 Screener 第一阶段强约束

---

## 3. 依赖关系与推荐顺序

### 3.1 推荐顺序

```text
A0 数据源验证
   ↓
A1 Screener 骨架与数据模型
   ↓
A2 三策略单独实现
   ↓
A3 合并器、过滤器、评分器
   ↓
A4 Deep Analyzer 桥接 TradingAgentsGraph
   ↓
A5 报告输出与指标记录
   ↓
A6 测试、修复、收尾
```

### 3.2 依赖说明

- `A0` 决定 `A2` 的抓数方式是否需要调整
- `A1` 决定 `A2/A3/A4` 的输入输出格式
- `A3` 决定最终候选排序逻辑
- `A4` 决定 Screener 与现有 Harness 的连接方式
- `A5/A6` 负责把实现变成可交付结果

---

## 4. 模块级开发拆分

### 4.1 新增目录

建议新增：

```text
tradingagents/screener/
  __init__.py
  config.py
  models.py
  engine.py
  merger.py
  report.py
  runtime_guard.py
  throttling.py
  universe.py
  data_access.py
  deep_analyzer.py
  strategies/
    __init__.py
    technical.py
    policy.py
    smart_money.py
```

### 4.2 文件职责

`config.py`
- Screener 默认配置
- 运行模式配置
- 股票池配置
- 分数阈值配置

`models.py`
- `DataFreshness`
- `SignalEvidence`
- `SignalCard`
- `ScreeningResult`
- `DeepAnalysisResult`
- `ScreenerMetrics`

`runtime_guard.py`
- 交易时间校验
- 交易日校验
- 数据一致性检查

`throttling.py`
- 顺序请求器
- 请求节流
- 请求统计

`universe.py`
- 股票池构建
- 成分股缓存
- 扩展池配置

`data_access.py`
- Screener 专用数据访问
- AkShare / fallback 适配

`strategies/technical.py`
- 策略 A：技术与资金共振

`strategies/policy.py`
- 策略 B：政策与事件驱动

`strategies/smart_money.py`
- 策略 C：Smart Money

`merger.py`
- 去重
- 共振加分
- 分数融合
- 熔断过滤

`deep_analyzer.py`
- `SignalCard -> TradingAgentsGraph` 的桥接器

`report.py`
- Markdown 报告
- JSON 报告
- 结果摘要

`engine.py`
- Screener 主入口
- 调度三策略
- 调度合并器
- 调度 Deep Analyzer

---

## 5. 阶段 A0：数据源验证

### 5.1 目标

先确认文档里的关键免费数据假设是否成立，避免把错误前提写进主流程。

### 5.2 必查项

1. `stock_individual_fund_flow()` 是否存在稳定可用的全量模式
2. `stock_board_concept_spot_em()` 是否可稳定返回有效概念列表
3. `stock_board_concept_cons_em()` 对概念名是否严格敏感
4. 龙虎榜、北向、业绩预告是否能在目标时间窗稳定获取
5. `stock_zh_a_hist_em()` 100 天顺序抓取的实际耗时

### 5.3 实施产出

- `docs/SCREENER_DATA_ASSUMPTION_NOTES.md`（可选）
- 关键接口验证日志
- 是否需要调整策略 A/B/C 的结论

### 5.4 验收标准

- 给出每个接口的“可用 / 不稳定 / 不可用”结论
- 给出是否需要改造数据流的结论

---

## 6. 阶段 A1：骨架与数据模型

### 6.1 目标

建立 Screener 的基础结构，先统一输出格式，再写策略。

### 6.2 任务拆分

#### 6.2.1 创建配置模块

文件：

- `tradingagents/screener/config.py`

内容：

- `SCREENER_CONFIG`
- `SCREENER_UNIVERSE`
- `SCREENER_THRESHOLDS`
- `DeepAnalyzerConfig`

#### 6.2.2 创建数据模型

文件：

- `tradingagents/screener/models.py`

内容：

- `DataFreshness`
- `SignalEvidence`
- `SignalCard`
- `ScreeningResult`
- `DeepAnalysisResult`
- `ScreenerMetrics`

#### 6.2.3 创建运行守卫

文件：

- `tradingagents/screener/runtime_guard.py`

内容：

- `TimeValidator`
- `validate_screener_run()`
- `check_data_consistency()`

#### 6.2.4 创建节流器

文件：

- `tradingagents/screener/throttling.py`

内容：

- `AntiBanConfig`
- `ThrottledRequester`

#### 6.2.5 创建股票池

文件：

- `tradingagents/screener/universe.py`

内容：

- `build_screening_universe()`
- `load_universe_cache()`
- `save_universe_cache()`

### 6.3 验收标准

- 所有模型能正常序列化
- 配置能被 engine 读取
- 时间守卫能独立运行
- 节流器能独立计数和降速

---

## 7. 阶段 A2：三策略单独实现

### 7.1 目标

让每个策略先形成独立闭环，不依赖合并器。

### 7.2 Strategy A：技术与资金共振

文件：

- `tradingagents/screener/strategies/technical.py`

功能：

- 成分股截面筛选
- 资金流粗筛
- 100 天历史数据抓取
- MACD / 均线 / 动量确认
- 输出 `SignalCard` 候选

实现要点：

- 仅使用顺序请求
- 仅对 Top 100 抓历史数据
- 所有异常都写入 `SignalEvidence.degraded`

验收标准：

- 能输出含分数的候选
- 能在资金流或历史数据缺失时降级运行

### 7.3 Strategy B：政策与事件驱动

文件：

- `tradingagents/screener/strategies/policy.py`

功能：

- 拉取新闻摘要
- 获取有效概念列表
- LLM 概念提取
- 概念合法性校验
- 概念到成分股映射

实现要点：

- 概念只能从有效概念列表里选
- LLM 失败后必须有关键词 fallback
- 概念列表不可用时允许策略降级退出

验收标准：

- 能产出合法概念映射结果
- LLM 失败时不会中断整轮 Screener

### 7.4 Strategy C：Smart Money

文件：

- `tradingagents/screener/strategies/smart_money.py`

功能：

- 龙虎榜/机构席位汇总
- 北向资金摘要
- 业绩预告/高增长信号
- 生成资金质量评分

实现要点：

- 不把单一事件作为硬条件
- 不把缺失字段直接视为失败
- 更偏重“资金质量”而非“题材热度”

验收标准：

- 能输出机构/资金相关的 `SignalCard`
- 数据缺失时仍能给出降级输出

---

## 8. 阶段 A3：合并器、过滤器、评分器

### 8.1 目标

把三个策略的输出收敛成最终的 Top 候选。

### 8.2 任务拆分

#### 8.2.1 合并去重

文件：

- `tradingagents/screener/merger.py`

功能：

- 以 `ticker` 为主键去重
- 合并多策略 evidence
- 记录命中策略数

#### 8.2.2 共振加分

功能：

- 多策略命中时增加 `resonance_bonus`
- 分数封顶 100

#### 8.2.3 安全熔断

功能：

- ST / *ST 剔除
- 跌停 / 近跌停剔除
- 低流动性剔除
- PE 条件过滤仅在字段可用时启用

#### 8.2.4 分散化控制

功能：

- 同板块最多 2 只
- 板块优先级：行业 > 概念 > unknown

### 8.3 验收标准

- 同一只股票多策略命中能正确融合
- 黑名单过滤生效
- 分散化约束生效
- 输出最终 `SignalCard[]`

---

## 9. 阶段 A4：Deep Analyzer 桥接

### 9.1 目标

把 Screener 的最终候选安全、稳定地送入现有 `TradingAgentsGraph`。

### 9.2 任务拆分

#### 9.2.1 建立桥接器

文件：

- `tradingagents/screener/deep_analyzer.py`

功能：

- 接收 `SignalCard`
- 生成 `graph_config`
- 注入 `screener_context`
- 调用 `TradingAgentsGraph`

#### 9.2.2 维持兼容性

规则：

- 不修改 `TradingAgentsGraph.propagate()` 签名
- 不把 `SignalCard` 直接传入 graph
- 只通过 config 和输入 ticker 传递必要上下文

#### 9.2.3 顺序执行

规则：

- 默认 Top 3
- 每只之间冷却 2 秒
- 单只失败不影响后续候选

### 9.3 验收标准

- 能对 Top 3 逐只完成深度分析
- graph 配置能正确注入 Screener 上下文
- 单只失败可记录，不会中断整轮

---

## 10. 阶段 A5：报告输出与指标记录

### 10.1 目标

把 Screener 的输出变成可读、可追踪、可复盘的报告。

### 10.2 任务拆分

#### 10.2.1 JSON 输出

文件：

- `tradingagents/screener/report.py`

产物：

- `screening_result.json`

#### 10.2.2 Markdown 输出

产物：

- `daily_gold_stocks_report.md`

#### 10.2.3 指标记录

产物字段：

- 请求总数
- 失败请求数
- 降级策略数
- 最终候选数
- 深度分析成功数
- 总耗时

### 10.3 报告最小字段

每只候选必须包含：

- ticker
- company_name
- strategy_sources
- trigger_reason
- screening_score
- initial_confidence
- risk_flags
- deep analysis status

### 10.4 验收标准

- JSON 可正常解析
- Markdown 可正常阅读
- 指标完整可追踪

---

## 11. 阶段 A6：测试与修复

### 11.1 单元测试

建议新增：

- `tests/test_screener_models.py`
- `tests/test_screener_runtime_guard.py`
- `tests/test_screener_throttling.py`
- `tests/test_screener_universe.py`
- `tests/test_screener_strategy_technical.py`
- `tests/test_screener_strategy_policy.py`
- `tests/test_screener_strategy_smart_money.py`
- `tests/test_screener_merger.py`
- `tests/test_screener_deep_analyzer.py`

### 11.2 集成测试

建议覆盖：

- `A0 -> A1`
- `A2 -> A3`
- `A3 -> A4`
- `A4 -> A5`

### 11.3 伪数据测试

必须覆盖：

- 三策略共振
- 单策略命中
- 概念列表为空
- 历史数据缺失
- Deep Analyzer 单票失败

### 11.4 验收标准

- 单元测试通过
- 集成测试通过
- 不破坏现有 CN 工具测试
- 不破坏现有 `TradingAgentsGraph` 路径

---

## 12. 文件级开发顺序建议

### 12.1 第一批

1. `tradingagents/screener/config.py`
2. `tradingagents/screener/models.py`
3. `tradingagents/screener/runtime_guard.py`
4. `tradingagents/screener/throttling.py`
5. `tradingagents/screener/universe.py`

### 12.2 第二批

1. `tradingagents/screener/data_access.py`
2. `tradingagents/screener/strategies/technical.py`
3. `tradingagents/screener/strategies/policy.py`
4. `tradingagents/screener/strategies/smart_money.py`

### 12.3 第三批

1. `tradingagents/screener/merger.py`
2. `tradingagents/screener/deep_analyzer.py`
3. `tradingagents/screener/report.py`
4. `tradingagents/screener/engine.py`

### 12.4 第四批

1. `tests/test_screener_*.py`
2. 文档与参数收尾

---

## 13. 风险点与对应动作

### 13.1 风险点

1. 免费数据源不稳定
2. 概念列表与 LLM 语义偏差
3. 100 天历史数据抓取时间过长
4. Deep Analyzer 与现有 graph 兼容性不足
5. 分数融合规则过于主观

### 13.2 对应动作

1. 所有策略允许 degraded
2. 概念必须先验合法校验
3. Top 100 限定 + 顺序请求 + 缓存
4. 仅通过 config 桥接，不改 graph 签名
5. 每个分数必须拆成子分数

---

## 14. 最终交付物清单

完成本轮实施后，应至少交付以下内容：

- 可运行的 Screener 主流程
- 三个策略的单独实现
- 合并器与评分器
- Deep Analyzer 桥接器
- JSON / Markdown 报告
- 完整测试集
- 可复盘的运行指标

---

## 15. 当前执行口径

后续如果开始编码，默认遵循以下口径：

- 先写 `models.py` 和 `config.py`
- 再写三策略
- 再写合并器
- 再写桥接器
- 最后补测试和报告

如果实现过程中发现 `SCREENER_DESIGN.md` 的假设与真实数据行为不一致，优先修正文档，再修代码。
