# TradingAgents Screener Final Plan (Execution Command Doc)

> **更新日期**: 2026-05-12  
> **用途**: 用于直接指挥 Cursor 完成最后收口  
> **范围**: `tradingagents/screener` 主体 + 最小契约测试  
> **原则**: 不重构架构，不扩测试规模，不破坏既有 schema/contract

---

## 0. 二次核实结论（先读）

以下结论基于对当前代码的再次核实，不依赖口头汇报。

### 已确认完成（无需重复做）

1. `report.py` 中 `dropped_candidates` 未定义引用已修复为 `screening_result.dropped_candidates`
2. `smart_money.py` 风险标记阈值已有一批迁移到 config（如 `hist_rows_minimum/deep_drawdown_pct/high_volatility_pct/heat_quality_gap_wide` 等）
3. `merger.py` 已补 `pe_unavailable` 对应 `threshold_trigger_details`
4. `merger_threshold_snapshot` 已包含 `screener_thresholds`
5. `semantic_home_chain` 已存在并用于首页主链路

### 明确未完成 / 仍可优化（本计划要做）

1. **A2 未完全完成**: `technical.py` 仍有核心评分硬编码权重与阈值常量  
   - 位置：`tradingagents/screener/strategies/technical.py`  
   - 典型代码：`_build_total_score` 中 `0.22/0.18/...`，以及 `+3.0`、`hist_rows < 30`
2. **A2 未完全完成**: `smart_money.py` 仍有大量评分基值硬编码  
   - 位置：`tradingagents/screener/strategies/smart_money.py`  
   - 典型代码：`45/50/42/62/68/55`、固定 `lookback=140`、输出 `top 20`
3. **A5 仍可优化**: `report.py` 仍保留旧的 home chain 辅助函数，存在重复链路渲染风险  
   - 位置：`_build_home_chain_from_deep_results`、`_render_home_chain_summary` 与正文 `## Semantic Home Chain`
4. **A6 契约口径冲突风险**: `tests/test_screener_contract.py` 中部分断言与当前“兼容策略”可能冲突  
   - 例如“完全移除 semantic_audit_chain”的断言在不同分支策略下可能不一致
5. **阶段验收证据未闭环**: 尚缺一套真实 run artifact 作为最终完工证据

---

## 1. 目标状态（完成本文件后）

完成后可正式宣布：本阶段开发完成。

必须同时满足：

1. A1-A6 达到 100% 或可审计地 >=97% 且无阻断项
2. A2 参数化闭环完成（technical + smart_money）
3. A5 首页单链路无漂移
4. A6 最小契约可防回退（仅 1 组新增断言）
5. 至少 1 套真实 run artifact 归档

---

## 2. 最后 5 个必须完成项（给 Cursor 执行）

## Task 1 (45-90 min)
## A2-technical 参数化收口（必须做）

代码位置：
- `tradingagents/screener/strategies/technical.py`
- `tradingagents/screener/config.py`

需要做什么：
1. 把 `_build_total_score` 的权重由硬编码改为读取 `strategies.technical.thresholds`
2. 把 `fund_flow_bonus`、`hist_rows_penalty`、`hist_rows >= 30` 这类门槛改为从阈值配置读取
3. 保持默认值与当前行为一致（默认运行结果不应大漂移）

具体目标：
- `technical.py` 内核心评分不再有固定权重魔法数字
- `threshold_snapshot` 能反映这些阈值

验收：
- grep 不再命中 `_build_total_score` 中硬编码权重常量
- `tests/test_screener_engine.py` 通过

---

## Task 2 (45-90 min)
## A2-smart_money 参数化补齐（必须做）

代码位置：
- `tradingagents/screener/strategies/smart_money.py`
- `tradingagents/screener/config.py`

需要做什么：
1. 将以下函数的核心 base/anchor/threshold 迁移到 `strategies.smart_money.thresholds`：
   - `_compute_tick_score`
   - `_compute_tick_persistence_score`
   - `_compute_popularity_score`
   - `_compute_institutional_score`
   - `_compute_lhb_continuity_score`
   - `_compute_risk_constraint_score`
2. 将 `run()` 中 topN（当前 20）与 `_load_hist_metrics()` lookback（当前 140）改为配置读取
3. 不改评分公式结构，只改“常量来源”

具体目标：
- smart_money 核心常量可由 config 覆盖
- 默认配置行为保持一致

验收：
- `smart_money.py` 中上述函数核心阈值均有 config 对应键
- `tests/test_screener_deep_analyzer.py` + `tests/test_screener_engine.py` 通过

---

## Task 3 (30-60 min)
## A5 首页链路去漂移收口（必须做）

代码位置：
- `tradingagents/screener/report.py`
- `tradingagents/screener/engine.py`

需要做什么：
1. 保留 `semantic_home_chain` 作为唯一主页真源
2. 清理或隔离 `report.py` 中旧 home chain 辅助函数，避免 fallback 造成双口径
3. 确保报告首页不重复输出同一语义链路

具体目标：
- homepage 只存在一条 `trigger -> route -> execution -> decision` 语义链

验收：
- markdown 首页每个 ticker 仅一条 semantic 链路摘要
- `tests/test_screener_report.py` 通过

---

## Task 4 (30-60 min)
## A6 最小契约防漂移（只允许 1 组新增）

代码位置：
- 优先在现有文件内补：`tests/test_screener_contract.py` 或 `tests/test_screener_engine.py`

需要做什么：
1. 新增 1 组参数漂移契约断言（默认配置 vs 覆盖配置）
2. 锁定“参数变化 -> merger snapshot / semantic reason / drop reason 同步变化”
3. 不新增大测试文件，不扩矩阵

具体目标：
- 能防住“参数改了但决策链不变”的回退

验收：
- 新增断言稳定通过
- 不新增大规模测试开销

---

## Task 5 (30-45 min)
## 真实 run artifact 验收闭环（必须做）

代码位置：
- 运行入口：`tradingagents/screener/cli`
- 输出目录：`reports/screener/<run_id>/`

需要做什么：
1. 执行一次真实 screener run
2. 产出并保存：
   - `screening_result.json`
   - `daily_gold_stocks_report.md`
3. 在 `docs/Plan4.md` 追加：
   - run date
   - run_id
   - artifact absolute path

具体目标：
- 把“开发完成”转成“可复核完成”

验收：
- 两个 artifact 文件可打开
- 文档中有可追溯 run_id 与路径

---

## 3. Cursor 执行顺序（严格）

1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5

每完成一个 task 才允许进下一个 task。

---

## 4. 最小回归清单（禁止扩张）

每轮只跑必要文件，最终统一跑：

1. `tests/test_orchestration_logic.py`
2. `tests/test_screener_report.py`
3. `tests/test_screener_deep_analyzer.py`
4. `tests/test_screener_engine.py`
5. `tests/test_screener_contract.py`（仅当 Task 4 触达）

---

## 5. 完工打勾区（Cursor 最终提交必须填写）

- [x] Task 1 完成（A2-technical 参数化）——technical.py 权重/fund_flow_bonus/hist_rows_penalty/score_ceiling/floor 全部 config 化
- [x] Task 2 完成（A2-smart_money 参数化）——smart_money 6评分函数全部 config 化
- [x] Task 3 完成（A5 单链路去漂移）——删除 _build_home_chain_from_deep_results/_render_home_chain_summary 辅助函数
- [x] Task 4 完成（A6 最小契约加固）——新增参数漂移断言（threshold drift 验证）+ 合约测试 9/9
- [x] Task 5 完成（真实 artifact）——run_id: 16eb73e5-09fb-4929-a27f-65906a197507，JSON+Markdown 均已产出
- [x] 最小回归通过——59/59 PASS
- [x] Plan4 验收项同步更新——Section 10 regression 更新为 59/59，Section 13 artifact 打勾

---

## 6. 禁止事项（防跑偏）

1. 禁止重构架构
2. 禁止把 AkShare/EastMoney 拉回主路径
3. 禁止新增大规模测试
4. 禁止删除兼容字段（除非确认无消费方）
5. 禁止改 schema/version/contract
6. 同一问题最多 3 次实验 / 30 分钟 / 2k token，超限就必须停。  
设“退出条件”
7.若问题不影响核心测试和主线里程碑，自动降级为 backlog，不得继续扩散脚本。
8.设“单文件调试规范”:只允许 1 个调试入口文件（如 tools/debug_name_resolver.py），禁止在仓库根目录散落临时脚本。测试脚本统一安放在tests文件夹下；
9. 静止过度测试！静止把大量的Token放在没有明确意义的测试上：每轮任务只能跑有限次数的核心测试（不多于4个），不能因为显示/编码问题阻塞主线。
10. 严格避免过多使用Mock测试或者其他测试，可以使用有限且重要的测试。