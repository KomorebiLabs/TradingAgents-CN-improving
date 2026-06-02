# Phase 2 开发计划文档

> **对应设计文档**: `docs/SCREENER_DESIGN.md`
> **创建日期**: 2026-05-18
> **最后更新**: 2026-05-18（补充新发现 bug，修正已有 bug 描述准确性）
> **用途**: Phase 2 开发执行依据

---

## Part 1: Bug 修复计划

> **状态标注说明**：
> - ✅ 已确认：代码审查中发现，代码逻辑确认存在问题
> - ⚠️ 需验证：基于代码审查的合理推断，建议实际运行确认
>
> **如何阅读**：每个 Task 的 step 均设计为可独立交付给 Coding Agent 执行。Task 之间如无特别说明均为并行关系。

---

### B-0: Bug 概述总表

> **状态标注说明**：
> - ✅ 已修复：代码已修改并通过验证
> - ⚠️ 已修复（环境限制）：代码已修改，因网络受限无法 live 验证，但逻辑正确

| 优先级 | Bug ID | 严重度 | 影响范围 | 修复状态 |
|--------|--------|--------|---------|---------|
| P0 | B-1 | Fatal | CLI 所有输出（评分/Signal badge） | ✅ 已修复 |
| P0 | B-2 | Fatal | JSON 序列化缺失 `data_source_verified` | ✅ 已修复 |
| P1 | B-3 | High | Universe 静默降级为 ETF 代码 | ✅ 已修复 |
| P1 | B-4 | High | ST 识别依赖 `company_name`（可能为 placeholder） | ✅ 已修复 |
| P2 | B-5 | Medium | `policy.py` 进度日志永远 100% | ✅ 已修复 |
| P2 | B-6 | Medium | `ThrottledRequester` 警告未暴露 | ✅ 已修复 |
| P2 | B-7 | Low | Merger evidence 顺序依赖（取第一个而非最高分） | ✅ 已修复 |
| P2 | B-8 | Low | Stage B 未应用 `stageb_max_input` 截断 | ✅ 已修复 |
| P1 | B-9 | High | `technical.py` 空数据兜底分数偏高（score 30+） | ✅ 已修复 |
| P1 | B-10 | High | `run_impl.py` 异常处理暴露 traceback | ✅ 已修复 |
| P2 | B-11 | Medium | `technical.py` 重复遍历所有股票（应复用 Stage A 数据） | ✅ 已修复（进程级缓存） |
| P2 | B-12 | Medium | `engine.py` 的 `llm_calls_total` 计数错误 | ✅ 已修复 |

---

### B-1: `overall_score` / `degraded` 属性不存在 [P0 - Fatal]

**状态**: ✅ 已确认

**影响文件**:
- `tradingagents/screener/cli/commands/run_impl.py:144-146`
- `tradingagents/screener/cli/formatters/terminal.py:57-59`

**问题描述**:

`SignalCard` 的正确字段名是 `screening_score`，不是 `overall_score`；没有顶级 `degraded` 属性（降级信息在 `SignalEvidence.degraded`）。

`run_impl.py:144-146`：
```python
# 当前错误代码（JSON 序列化部分）
"overall_score": c.overall_score,                    # ← 不存在，始终 None
"signal": _signal_from_score(c.overall_score),    # ← 传入 None → 返回 "HOLD"
"degraded": c.degraded,                           # ← 不存在
```

`terminal.py:57-59`：
```python
# 当前错误代码
score = getattr(card, "overall_score", None)  # ← 总是 None
score_str = f"{score:.1f}" if score is not None else "N/A"  # ← 始终显示 "N/A"
degraded = card.degraded  # ← AttributeError
```

**影响**：所有 BUY/HOLD/SELL badge 全部错误（因为 `None >= 75` → False，`None >= 60` → False → 返回 "SELL"）。

---

**Task B-1.1: 修复 `_serialize_for_output()` — `run_impl.py`**

文件：`tradingagents/screener/cli/commands/run_impl.py:140-151`

> **Step 顺序不可调换**，必须按序执行。

- [ ] **Step 1: 确认修复位置**

在 `_serialize_for_output()` 的候选字典中，将：

```python
"overall_score": c.overall_score,
"signal": _signal_from_score(c.overall_score),
"degraded": c.degraded,
```

修改为：

```python
"screening_score": c.screening_score,
"initial_confidence": c.initial_confidence,
"data_source_verified": c.data_source_verified,
"signal": _signal_from_score(c.screening_score),
"degraded": _is_degraded(c),
```

- [ ] **Step 2: 新增辅助函数 `_is_degraded()`**

在文件内（建议在 `_signal_from_score()` 附近）新增：

```python
def _is_degraded(card) -> bool:
    """Check if any SignalEvidence in the card is degraded."""
    if not card.signal_breakdown:
        return False
    return any(e.degraded for e in card.signal_breakdown)
```

- [ ] **Step 3: 验证**

运行：

```bash
python -m tradingagents.screener.cli run --tickers 600519 --no-deep --output json
```

检查 JSON 输出：`screening_score` 有数值（非 `null`），`signal` 正确（BUY/HOLD/SELL），`degraded` 为布尔值。

---

**Task B-1.2: 修复 `print_ranking_table()` — `terminal.py`**

文件：`tradingagents/screener/cli/formatters/terminal.py:54-74`

- [ ] **Step 1: 确认修复位置**

第 57-59 行：

```python
# 修复前
score = getattr(card, "overall_score", None)
score_str = f"{score:.1f}" if score is not None else "N/A"
degraded = card.degraded

# 修复后
score = getattr(card, "screening_score", None)
score_str = f"{score:.1f}" if score is not None else "N/A"
degraded = _is_degraded(card)
```

> 注意：修复后 `score` 有值，第 74 行 `format_signal_badge(score or 0, degraded)` 中的 `or 0` fallback 可移除（保持不变也无害）。

- [ ] **Step 2: 新增 `_is_degraded()` 函数**

在文件顶部（建议在 `format_signal_badge()` 之后）新增：

```python
def _is_degraded(card) -> bool:
    """Check if any SignalEvidence in the card is degraded."""
    if not hasattr(card, "signal_breakdown") or not card.signal_breakdown:
        return False
    return any(getattr(e, "degraded", False) for e in card.signal_breakdown)
```

> 注意：`terminal.py` 中的函数参数类型是 `Any`，需要用 `hasattr` 做安全检查（与 `run_impl.py` 不同）。

- [ ] **Step 3: 验证**

运行：

```bash
python -m tradingagents.screener.cli run --tickers 600519,000001 --no-deep
```

检查终端表格：Score 列有数值（不是 `N/A`），Signal 列正确显示 BUY/HOLD/SELL 而非全部 SELL。

---

### B-2: `data_source_verified` 未被序列化 [P0 - Fatal]

**状态**: ✅ 已确认（代码审查确认）

**影响文件**: `tradingagents/screener/cli/commands/run_impl.py:140-151`

**问题描述**: `_serialize_for_output()` 输出 JSON 时遗漏了 `data_source_verified` 字段，用户无法在 JSON 输出中判断数据质量。

**修复计划**（已包含在 B-1.1 Step 1 中，无需单独 Task）：

在 B-1.1 的 Step 1 修改中已一并加入：

```python
"data_source_verified": c.data_source_verified,
```

---

### B-3: Universe 成分股全部失败时静默降级为 ETF 代码 [P1 - High]

**状态**: ✅ 已确认（代码审查确认）

**影响文件**: `tradingagents/screener/universe.py:233-234`

**问题描述**:

```python
# 当前代码
if not constituents:
    constituents = index_codes  # ← 静默返回 "000300", "000905" 而非股票！
```

当所有成分股接口失败（如 AkShare 被封禁），`_fetch_constituents_for_indexes()` 返回空列表，`build_screening_universe()` 静默降级为直接使用指数代码本身——系统将筛选 ETF 而非股票。

**修复计划**：

**Task B-3.1: 显式错误处理 — `universe.py`**

文件：`tradingagents/screener/universe.py:233-234`

- [ ] **Step 1: 将静默降级改为显式抛出**

```python
# 修复前
if not constituents:
    constituents = index_codes

# 修复后
if not constituents:
    raise RuntimeError(
        f"[Screener] All index constituent APIs failed for indexes {index_codes}. "
        f"Cannot build universe from ETF codes. "
        f"Check AkShare connectivity or try CUSTOM mode with explicit tickers."
    )
```

- [ ] **Step 2: 写单元测试**

文件：`tests/test_screener_universe.py`（新建）

```python
def test_build_universe_fails_loudly_when_apis_all_fail(monkeypatch):
    """B-3: When all constituent APIs fail, universe.py must raise RuntimeError, not return ETF codes."""
    from tradingagents.screener import universe

    # Mock all constituent fetch attempts to return empty
    monkeypatch.setattr(
        "tradingagents.screener.universe._fetch_constituents_for_indexes",
        lambda *a, **kw: []
    )

    with pytest.raises(RuntimeError, match="All index constituent APIs failed"):
        universe.build_screening_universe(mode="MVP")
```

- [ ] **Step 3: 验证修复**

```bash
pytest tests/test_screener_universe.py::test_build_universe_fails_loudly_when_apis_all_fail -v
```

---

**Task B-3.2: 错误传播处理 — `engine.py`**

文件：`tradingagents/screener/engine.py:208`

- [ ] **Step 1: 在 `run()` 中捕获 RuntimeError，提供友好提示**

在 `build_screening_universe()` 调用处增加 try-except：

```python
try:
    universe = build_screening_universe(mode=mode, config=self.config)
except RuntimeError as e:
    raise RuntimeError(
        f"Universe construction failed: {e}\n"
        "Hint: Try --mode CUSTOM with --tickers <list> to skip index constituent fetching."
    )
```

---

### B-4: Merger 评分公式存在边界 Bug [P1 - High]

**状态**: ✅ 已确认（代码审查确认）

**影响文件**: `tradingagents/screener/merger.py:739-741`

**问题描述**:

```python
def _is_st_name(card: SignalCard) -> bool:
    name = (card.company_name or "").upper()
    return name.startswith("ST") or name.startswith("*ST") or " ST" in name or "*ST" in name
```

当前置 `name_resolver` 失败时，`company_name` 保留 placeholder（如 `"Proxy 000001"`），不含 ST 信息。若 ST 股票的 `company_name` 未被正确解析，ST 判断将失效。**真正的 ST 判断应额外检查 `sector_tags` 或 `concept_tags`。**

---

**Task B-4.1: 增强 ST 识别逻辑 — `merger.py`**

文件：`tradingagents/screener/merger.py:739-741`

- [ ] **Step 1: 将 `_is_st_name()` 改为多维判断**

```python
def _is_st_name(card: SignalCard) -> bool:
    """Detect ST/*ST status from multiple sources.

    Checks company_name (if real), sector_tags, and concept_tags.
    A card is flagged as ST if ANY source indicates ST status.
    """
    name = (card.company_name or "").upper()
    name_is_st = name.startswith("ST") or name.startswith("*ST") or " ST" in name

    # Also check sector_tags which are more reliable when name is a placeholder
    tag_is_st = any(
        tag.upper().startswith(("ST", "*ST")) or " ST" in tag.upper()
        for tag in (card.sector_tags or [])
    )

    return name_is_st or tag_is_st
```

- [ ] **Step 2: 写单元测试**

文件：`tests/test_screener_merger.py`

```python
def test_st_flagged_when_name_is_placeholder():
    """B-4: ST detection must work even when company_name is a placeholder."""
    from tradingagents.screener.merger import _is_st_name
    from tradingagents.screener.models import SignalCard

    card = SignalCard(
        ticker="000001.SZ",
        raw_code="000001",
        exchange="SZ",
        company_name="Proxy 000001",  # placeholder, no ST info
        trade_date="2026-01-01",
        sector_tags=["ST_candidate"],  # ← ST info here
        concept_tags=[],
        strategy_sources=["technical"],
        signal_breakdown=[],
        trigger_reason="test",
        screening_score=80.0,
        initial_confidence=80.0,
        data_source_verified=False,
    )
    assert _is_st_name(card) is True, "ST must be detected from sector_tags even when name is placeholder"
```

- [ ] **Step 3: 验证**

```bash
pytest tests/test_screener_merger.py -v -k "st"
```

---

### B-5: `policy.py` 第 300 行永远输出 100% 进度 [P2 - Medium]

**状态**: ✅ 已确认（代码审查确认）

**影响文件**: `tradingagents/screener/strategies/policy.py:299-301`

**问题描述**:

```python
if total > 0:
    pct = total * 100 // total  # ← 永远是 100！因为分子分母相同
    _logger.info(f"[Policy] Analysis: {total}/{total} (100%) ...")
```

进度计算 `total * 100 // total` 恒等于 100，且日志在循环外（循环结束后）执行，记录的是最终统计而非进度。

---

**Task B-5.1: 修复进度日志逻辑 — `policy.py`**

文件：`tradingagents/screener/strategies/policy.py`（主循环内）

- [ ] **Step 1: 删除无意义的进度行，将进度日志移入主循环**

在主循环内（建议在 `cards.append()` 之后）添加：

```python
# 每 10% 打印一次进度
if (idx + 1) % log_interval == 0 or (idx + 1) == total:
    pct = (idx + 1) * 100 // total
    _logger.info(f"[Policy] Analysis: {idx+1}/{total} ({pct}%) ...")
```

删除原来的无意义进度行（第 299-301 行）。

- [ ] **Step 2: 验证**

确认运行 Policy 策略时，进度日志按 10%/20%/.../100% 逐步输出。

---

### B-6: `ThrottledRequester` 中的 `_warnings` 未被使用 [P2 - Medium]

**状态**: ⚠️ 需验证（代码审查推断）

**影响文件**: `tradingagents/screener/throttling.py`

**问题描述**: `ThrottledRequester` 收集警告到 `_warnings` 列表，但这些警告未被暴露到 `data_access.py` 的 `get_interface_capability_summary()` 输出中。

---

**Task B-6.1: 确认并暴露警告 — `throttling.py`**

文件：`tradingagents/screener/throttling.py`

- [ ] **Step 1: 确认 `get_warnings()` 方法存在且未被调用**

读取 `throttling.py`，找到 `_warnings` 列表和 `get_warnings()` 方法。

- [ ] **Step 2: 在 `data_access.py` 的 `get_interface_capability_summary()` 中加入警告输出**

如果 `ThrottledRequester` 实例有 `get_warnings()` 方法，在 `capability_summary` 中加入：

```python
throttle_warnings = throttled_requester.get_warnings()  # 如果方法存在
if throttle_warnings:
    capability_summary["warnings"].extend(throttle_warnings)
```

- [ ] **Step 3: 验证**

运行 Screener，检查 JSON 输出中 `data_issues` 或 `warnings` 字段是否包含限速警告。

---

### B-7: Merger evidence 顺序依赖导致条件漏判 [P2 - Low]

**状态**: ⚠️ 需验证（代码审查推断，实际风险低）

**影响文件**: `tradingagents/screener/merger.py:38-42`

**问题描述**:

```python
def _find_signal_metrics(card: SignalCard, strategy: str | None = None) -> Dict[str, Any]:
    for evidence in card.signal_breakdown:
        if strategy is None or evidence.strategy == strategy:
            return evidence.raw_metrics or {}  # ← 返回第一个匹配的 evidence
    return {}
```

当同一策略产生多个 `SignalEvidence` 时（如 merger 后），只取第一个。合并后 `signal_breakdown` 顺序取决于 `strategy_sources` 的生成顺序，可能不稳定。

---

**Task B-7.1: 改为取评分最高的 evidence — `merger.py`**

文件：`tradingagents/screener/merger.py:38-42`

- [ ] **Step 1: 修改 `_find_signal_metrics()` 为取最高分**

```python
# 修复前：只取第一个
def _find_signal_metrics(card: SignalCard, strategy: str | None = None) -> Dict[str, Any]:
    for evidence in card.signal_breakdown:
        if strategy is None or evidence.strategy == strategy:
            return evidence.raw_metrics or {}
    return {}

# 修复后：取评分最高的那个
def _find_signal_metrics(card: SignalCard, strategy: str | None = None) -> Dict[str, Any]:
    best = {}
    best_score = float("-inf")
    for evidence in card.signal_breakdown:
        if strategy is None or evidence.strategy == strategy:
            if evidence.score > best_score:
                best_score = evidence.score
                best = evidence.raw_metrics or {}
    return best
```

- [ ] **Step 2: 验证**

```bash
pytest tests/test_screener_merger.py -v
```

---

### B-8: Stage B 未应用 `stageb_max_input` 截断 [P2 - Low]

**状态**: ⚠️ 需验证（代码审查推断）

**影响文件**: `tradingagents/screener/engine.py:225`

**问题描述**: `engine.py` 中 `stagea_pass_tickers` 直接传给三策略，没有在传入前应用 `stageb_max_input` 截断。

```python
# 当前代码
technical_outcome = technical_strategy.run(stagea_pass_tickers, trade_date)  # 可能超过 stageb_max_input
policy_outcome = policy_strategy.run(stagea_pass_tickers, trade_date)
smart_money_outcome = smart_money_strategy.run(stagea_pass_tickers, trade_date)
```

---

**Task B-8.1: 应用 Stage B 输入截断 — `engine.py`**

文件：`tradingagents/screener/engine.py:225`

- [ ] **Step 1: 在 `run()` 方法中，Stage A 完成后、Stage B 启动前增加截断逻辑**

```python
# 在 _logger.info(f"[Screener] Stage B starting: ...") 之前添加：
stageb_max = self.config.get("stageb_max_input", 1000)
if len(stagea_pass_tickers) > stageb_max:
    _logger.info(f"[Screener] Stage B limit applied: {len(stagea_pass_tickers)} -> {stageb_max}")
    stagea_pass_tickers = stagea_pass_tickers[:stageb_max]
```

- [ ] **Step 2: 验证**

运行 `python -m tradingagents.screener.cli run --stageb-max-input 50 --tickers ...`（传自定义 ticker 测试），确认日志中出现 `Stage B limit applied` 信息。

---

### B-9: Technical Strategy 空数据兜底分数偏高 [P1 - High]

**状态**: ⚠️ 需验证（代码审查推断，建议实际运行确认）

**影响文件**: `tradingagents/screener/strategies/technical.py:268-298`

**问题描述**:

```python
empty = {
    "hist_rows": 0,
    "trend_alignment_score": 30.0,   # ← 初始 30，不是 0
    "momentum_score": 30.0,          # ← 初始 30
    "drawdown_resilience_score": 35.0,
    "volatility_score": 40.0,
    "trend_consistency_score": 35.0,
    "structure_risk_score": 45.0,
    # ...
}
```

空数据的兜底分数为 30~45 分，**不是 0 分**。这意味着没有历史数据的股票仍可能通过 merger 的分数门槛，被错误选为候选。

**修复计划**：

**Task B-9.1: 评估并修复空数据兜底分数 — `technical.py`**

文件：`tradingagents/screener/strategies/technical.py:268-298`

- [ ] **Step 1: 评估空数据兜底分数对 Merger 的影响**

阅读 `merger.py` 中的 `_should_drop_card()` 和 `_merge_card_group()`，确认空数据 SignalCard 是否会被 merger 保留。如果会被保留（大多数情况下会的），则进行 Step 2。

- [ ] **Step 2: 修复空数据兜底分数**

```python
empty = {
    "hist_rows": 0,
    # 所有子分设为最低值，确保无数据时 merger 自然过滤
    "trend_alignment_score": 0.0,
    "momentum_score": 0.0,
    "drawdown_resilience_score": 0.0,
    "volatility_score": 0.0,
    "trend_consistency_score": 0.0,
    "structure_risk_score": 0.0,
    "volume_confirmation_score": 0.0,
    "breakout_quality_score": 0.0,
    "volume_price_divergence_score": 0.0,
    # ...
}
```

- [ ] **Step 3: 验证**

运行 `python -m tradingagents.screener.cli run --tickers 999999 --no-deep`（使用无效代码），确认该股票不出现在最终候选中。

---

### B-10: `run_impl.py` 异常处理暴露 traceback [P1 - High]

**状态**: ⚠️ 需验证（代码审查推断）

**影响文件**: `tradingagents/screener/cli/commands/run_impl.py:433-438`

**问题描述**:

```python
except Exception as e:
    console.print(f"[red]Unexpected error:[/red] {e}")
    if verbose:
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
    raise typer.Exit(code=1)
```

当非预期异常发生时，traceback 在 `verbose=True` 时输出到终端，可能暴露内部路径、变量名等信息。

---

**Task B-10.1: 修复异常处理安全性 — `run_impl.py`**

文件：`tradingagents/screener/cli/commands/run_impl.py:433-438`

- [ ] **Step 1: 删除 traceback 输出**

```python
except Exception as e:
    console.print(f"[red]Unexpected error:[/red] {e}")
    # 不输出 traceback，防止内部路径和变量名暴露
    raise typer.Exit(code=1)
```

---

### B-11: Technical Strategy 重复遍历所有股票 [P2 - Medium]

**状态**: ⚠️ 需验证（代码审查推断）

**影响文件**: `tradingagents/screener/strategies/technical.py:74-264` 和 `engine.py:139`

**问题描述**:

Stage A 已遍历所有股票获取历史数据（`engine.py:139`），但 `TechnicalStrategy.run()` 又独立遍历 `universe` 再次获取历史数据：

```python
# engine.py Stage A:
hist = data_access.fetch_hist(ticker, start_date, end_date, adjust="qfq")

# technical.py 中 _load_histories() 又做了一遍:
hist = self.data_access.fetch_hist(ticker, start_date, end_date, adjust="qfq")
```

这导致同一交易日同一只股票的历史数据被请求 **两次**，浪费时间和 API 配额。

---

**Task B-11.1: 复用 Stage A 历史数据 — `technical.py` + `engine.py`**

> 建议：优先尝试方案 B（进程级缓存），因为不改变接口签名，风险更小。

**方案 A：修改接口传递预加载数据**

文件：`tradingagents/screener/strategies/technical.py` + `engine.py`

- [ ] **Step 1A: 修改 `TechnicalStrategy.run()` 接口，接受预加载的 histories**

将 histories 作为可选参数传入：

```python
def run(self, universe: List[str], trade_date: str,
        preloaded_histories: Dict[str, Any] | None = None) -> StrategyOutcome:
    if preloaded_histories:
        histories = preloaded_histories
        vendors = {ticker: "stage_a_preloaded" for ticker in histories}
    else:
        histories, vendors = self._load_histories(...)
```

- [ ] **Step 2A: 修改 `engine.py` 传递 Stage A 数据**

在 `engine.py` 中，从 `_run_stage_a` 中提取 histories 并传递给策略：

```python
# engine.py - 需要从 _run_stage_a 提取 histories
# 建议：将 _run_stage_a 的返回值改为 (passed, drop_reasons, stage_a_data)
# 其中 stage_a_data 包含各股票的历史数据字典
```

**方案 B（推荐）：进程级缓存**

文件：`tradingagents/screener/data_access.py`

- [ ] **Step 1B: 在 `ScreenerDataAccess` 中增加进程级缓存**

在 `ScreenerDataAccess` 中增加一个 `_hist_cache: Dict[str, pd.DataFrame]` 字典。在 `fetch_hist()` 中先查缓存，miss 时请求并写入缓存。Stage A 获取的数据自动被缓存，Stage B 命中缓存后不再重复请求。

- [ ] **Step 2B: 验证**

运行 MVP 模式，监控 AkShare API 请求数是否减少约 50%（Stage A + Stage B 各减少一半）。

---

### B-12: `engine.py` 的 `llm_calls_total` 计数错误 [P2 - Medium]

**状态**: ⚠️ 需验证（代码审查推断）

**影响文件**: `tradingagents/screener/engine.py:275`

**问题描述**:

```python
llm_calls_total=1 if deep_results else 0,  # ← 始终为 0 或 1
```

`deep_results` 是 `List[DeepAnalysisResult]`，无论分析多少只股票（`max_stocks`），计数始终为 1（只要有结果）或 0（无结果）。正确值应为 `len(deep_results)`。

---

**Task B-12.1: 修复 llm_calls_total 计数 — `engine.py`**

文件：`tradingagents/screener/engine.py:275`

- [ ] **Step 1: 修复计数逻辑**

```python
# 修复前
llm_calls_total=1 if deep_results else 0,

# 修复后
llm_calls_total=len(deep_results) if deep_results else 0,
```

- [ ] **Step 2: 验证**

运行带 Deep Analyzer 的筛选（`--max-stocks 5`），检查 JSON 输出中 `metrics.llm_calls_total` 等于 5。

---

## Part 2: 模块功能说明与设计分析

> 以下内容同步写入 `Learning/About_Screener.md`

---

### P-1: Screener 整体架构是什么？

Screener 是 TradingAgents 的 **Stage 1（主动选股引擎）**，位于 Deep Analyzer（Stage 2）之前。它的职责是：**从全市场/降维股票池中，通过三策略评分 + Merger 融合，快速发现最值得深度分析的 Top 3-5 只股票**，作为 `TradingAgentsGraph` 的候选输入。

**数据流向**：

```
交易日 + 运行模式
    │
    ├─► Universe 构建（指数成分股 或 自定义列表）
    │
    ├─► Stage A 预筛（快速过滤无效股票）
    │       │
    │       ├─ 无历史数据 → 剔除
    │       ├─ 历史行数不足 → 剔除
    │       └─ 低流动性/极端涨跌 → 剔除
    │
    ├─► Stage B 三策略评分
    │       │
    │       ├─ Strategy A（技术）: 历史K线趋势 + 资金流
    │       ├─ Strategy B（政策）: 概念板块热度 + 新闻事件
    │       └─ Strategy C（Smart Money）: 资金质量 + 龙虎榜 + 人气
    │
    ├─► Merger 合并与过滤
    │       │
    │       ├─ 去重（以 ticker 为主键）
    │       ├─ 共振加分（多策略命中 +5 分/策略）
    │       ├─ 语义优先级（policy_strength + capital_tag）
    │       ├─ 冲突解析（跨策略冲突检测与 resolution）
    │       ├─ 熔断过滤（ST / 跌停 / 低流动性 / PE 极端值）
    │       └─ 分散化（同板块最多 2 只）
    │
    └─► Deep Analyzer（Stage 2）
            │
            ├─ 构造 graph_config + screener_context
            └─ 调用 TradingAgentsGraph.propagate()
```

---

### P-2: 各模块的功能详解

#### 2.1 `config.py` — 全局配置中心

**作用**：定义所有可配置项，是 Screener 的"单一配置真相来源"。

**核心内容**：

| 配置块 | 内容 |
|--------|------|
| `SCREENER_UNIVERSE` | 6种运行模式的股票池定义（股票代码列表、输入上限等） |
| `SCREENER_CONFIG` | 运行时规则、策略权重、Vendor 优先级、防封禁参数、冲突解析规则、合并评分参数 |
| `SCREENER_THRESHOLDS` | 硬过滤阈值（换手率、市值、涨跌幅、PE 边界） |
| `DeepAnalyzerConfig` | Deep Analyzer 并发配置 |
| `build_graph_config()` | 为 Deep Analyzer 构造 `TradingAgentsGraph` 兼容的 config dict |

**设计意图**：所有阈值都从配置文件读取，不允许在策略代码中出现魔法数字。修改评分行为只需改配置文件，无需改代码。

---

#### 2.2 `models.py` — 数据契约（Pydantic 模型）

**作用**：定义 Screener 所有核心数据结构，通过 Pydantic V2 做运行时强校验。

| 模型 | 作用 |
|------|------|
| `DataFreshness` | 记录每个数据源的"新鲜度"（fresh/stale/missing/estimated） |
| `SignalEvidence` | 单策略单股票的评分证据（分数、原因、原始指标、降级原因） |
| `SignalCard` | 完整的股票信号卡（包含所有策略证据 + 最终评分 + 风险标记） |
| `ScreeningResult` | 整轮筛选结果（所有候选、被剔除候选、策略状态、指标） |
| `DeepAnalysisResult` | Deep Analyzer 单只分析结果 |
| `ScreenerMetrics` | 运行指标（请求数、失败数、降级策略、阈值快照） |

**设计意图**：
- 每个 `SignalCard` 必须可追溯：哪几个策略命中？分数是多少？为什么被降级？
- 通过 `evidence_snapshot` 保留完整的中间计算过程，供审计和复盘使用。

---

#### 2.3 `runtime_guard.py` — 运行守卫

**作用**：在 Screener 运行前检查"是否允许运行"。

**`TimeValidator` 规则**：
- 交易日规则：周末默认拒绝（可通过 `--allow-weekend` 覆盖）
- 盘中规则：`09:30-15:00` 盘中时段 MVP/EXTENDED 模式拒绝运行
- 数据日期规则：数据超过 2 天发出警告

**设计意图**：确保 Screener 在数据质量最好的时间窗口（收盘后 `16:30` 至次日 `09:00`）运行。

---

#### 2.4 `throttling.py` — 防封禁请求器

**作用**：对所有 AkShare API 请求施加限速，防止 IP 被封禁。

**策略**：
- 基础间隔：每请求间隔 0.5 秒
- Burst 暂停：连续超过 10 次请求后强制暂停 2 秒
- 失败惩罚：请求失败后额外等待 1.5 秒
- 软 RPM 限制：30 次/分钟，超过后记录警告但不阻塞

---

#### 2.5 `universe.py` — 股票池构建

**作用**：根据运行模式，构建要筛选的股票代码列表。

**6 种模式**：

| 模式 | 含义 | 股票池 |
|------|------|--------|
| MVP | 沪深300 + 中证500 | ~800只 |
| EXTENDED | + 创业板 + 科创50 | ~1500只 |
| EXPERIMENTAL | + 中证1000 | ~2500只 |
| FULL | 近全市场 | ~4000只 |
| FOCUSED | 指定板块/主题/指数 | 动态 |
| CUSTOM | 用户自定义列表 | 用户指定 |

**关键设计**：
- 真实成分股通过 AkShare 的 `index_stock_cons_weight_csindex` 获取（不是直接用指数代码）
- 支持缓存（同一天不重复抓取成分股）
- **Bug B-3 修复后**：所有 API 失败时不再静默降级为指数代码，而是显式抛出错误

---

#### 2.6 `data_access.py` — 多源数据访问层

**作用**：封装 Sina、Tencent、THS、Baidu、Baostock、yfinance 等多个数据源，提供统一 API，并自动探测可用性、选择主备源。

**数据源优先级**（按数据类型）：

| 数据类型 | 主源 | 备源1 | 备源2 | 最终兜底 |
|---------|------|--------|--------|---------|
| 历史K线 | Tencent | Sina | Baostock | yfinance |
| 实时行情 | Tencent | Sina | — | — |
| 概念板块 | THS | Sina | — | — |
| 资金流向 | THS | AkShare EM | — | — |
| 指数数据 | Sina | Tencent | — | — |
| 分笔成交 | Tencent | Sina | — | — |
| 估值/人气 | Baidu | — | — | — |

**设计意图**：
- A0 Probe 系统：每次运行前探测各接口可用性
- 主备链自动切换：一个源失败自动尝试下一个
- 请求伪装：对 Sina/THS 等"反爬"源施加浏览器头伪装

---

#### 2.7 `strategies/technical.py` — Strategy A：技术与资金共振

**作用**：基于历史K线趋势 + 资金流向，给每只股票打技术分。

**核心评分维度（9个子分）**：

| 子分 | 权重 | 含义 |
|------|------|------|
| trend_alignment | 0.22 | 价格与均线系统对齐程度（MA20/MA60） |
| momentum | 0.18 | 20日和60日动量 |
| drawdown_resilience | 0.14 | 回撤控制能力 |
| volatility | 0.10 | 波动率健康度 |
| trend_consistency | 0.12 | 趋势一致性（正收益天数比例） |
| structure_risk | 0.11 | 结构风险（延伸幅度、均线支撑） |
| volume_confirmation | 0.07 | 量价配合确认度 |
| breakout_quality | 0.04 | 突破质量 |
| divergence | 0.02 | 量价背离检测 |

**关键设计**：使用 Tencent 历史K线作为主数据源，lookback=100天。资金流验证通过时额外 +3 分奖励。

---

#### 2.8 `strategies/policy.py` — Strategy B：政策与事件驱动

**作用**：通过概念板块热度 + 政策新闻事件，找到当前最热概念中的强势股票。

**核心流程**：
1. 获取概念板块列表（THS 优先）
2. 匹配政策新闻中的关键词
3. 提取命中概念下的成分股
4. 对成分股按涨跌幅/成交额/换手率打分

**评分维度**：
- 概念热度（新闻命中频次）
- 成分股相对强度
- 板块领导地位（成分股内排名）
- 多概念重叠（同一股票命中多概念 + 加分）
- 新闻源权重（官方政策 > 主流财经 > 二手转载）

**关键词 Fallback**：当 LLM 抽取失败时，使用内置的 `POLICY_KEYWORDS` 字典做关键词匹配兜底。

---

#### 2.9 `strategies/smart_money.py` — Strategy C：Smart Money

**作用**：寻找"资金质量高"的标的——机构参与度高、连续性强、资金与价格质量匹配。

**核心评分维度（10个子分 + capital_quality_tag）**：

| 维度 | 权重 | 含义 |
|------|------|------|
| momentum | 0.24 | 历史动量（来自 Technical 的 hist_metrics） |
| tick | 0.11 | 分笔大单净买入方向 |
| tick_persistence | 0.10 | 分笔大单连续性 |
| popularity | 0.12 | 百度人气投票 |
| institutional | 0.11 | 龙虎榜机构席位信号 |
| continuity | 0.10 | 龙虎榜连续上榜强度 |
| multi_day | 0.10 | 多日持续性 |
| valuation | 0.10 | 估值（PE/PB 合理区间） |
| risk_constraint | 0.07 | 风险约束（波动率/回撤控制） |
| joint_quality | 0.10 | 综合资金质量 |

**`capital_quality_tag`**：每个 SignalCard 被打上 `high / persistent / mixed / speculative` 四级标签，speculative 标签的股票在 Merger 中会被额外扣分。

**MVP 设计意图**：只要 Tencent 历史K线可用，Smart Money 就能运行；龙虎榜/机构席位/人气投票等数据是增强项，不是硬性要求。

---

#### 2.10 `merger.py` — 合并器（核心决策引擎）

**作用**：将三策略输出融合为最终 Top 候选，是 Screener 的"大脑"。

**融合流程**：

```
所有 SignalCard（每个策略给每只股票一个）
    │
    ├─ 按 ticker 去重，合并多策略 evidence
    │       合并分数 = sum(各策略分 * 权重) + 共振加分(+5/命中策略数-1)
    │
    ├─ 语义优先级计算
    │       policy_strength（0-3）+ capital_tag 加减分
    │       - 技术结构惩罚（structure_risk 低分时扣分）
    │       - 跨策略冲突检测（aligned / moderate / high / severe）
    │       - 冲突解析规则（8条规则，决定 bias 方向）
    │
    ├─ 熔断过滤
    │       ST / 跌停 / 低流动性 / PE极端 / speculative资本 + 低分 → 直接剔除
    │
    ├─ 分散化
    │       同板块最多 2 只（板块优先级：行业 > 概念 > unknown）
    │
    └─ 输出 Top N
```

**设计意图**：Merger 不只是"加权平均分数"，而是一个基于语义标签的决策引擎：
- `policy_top_stock`（概念板块龙头）天然优先
- `capital_quality_high`（高质量持续资金）天然优先
- 但两者冲突时（如强概念股 + 高技术风险），由冲突规则决定

---

#### 2.11 `deep_analyzer.py` — Deep Analyzer（Stage 2 桥接）

**作用**：将 Screener 输出的 `SignalCard` 逐只送入 `TradingAgentsGraph`，获得完整的 AI Agent 深度研判结果。

**工作流程**：
1. 为每只候选构造 `graph_config`（包含 `company_of_interest` + `screener_context`）
2. `screener_context` 注入：`trigger_reason` / `strategy_sources` / `screening_score` / `risk_flags` / `sector_tags` / `concept_tags` / `semantic_prompt_slots`
3. 调用 `TradingAgentsGraph(debug=False, config=graph_config).propagate(ticker, trade_date)`
4. 解析 `final_state`，提取路由决策 + 分析结论

**兼容性约束**：不修改 `TradingAgentsGraph.propagate()` 的函数签名，只通过 config 字典注入上下文。

---

#### 2.12 `report.py` — 报告生成器

**作用**：将 `ScreeningResult` 输出为可读的 JSON 和 Markdown 报告。

**输出文件**：
- `screening_result.json`：完整结构化数据（含所有 evidence_snapshot）
- `daily_gold_stocks_report.md`：人类可读的 Markdown 摘要

**Markdown 报告包含**：
- Funnel Summary（Stage A/B 通过率）
- Strategy Status（各策略是否 degraded）
- Capability Summary（各数据源探测结果）
- Candidates（每只候选的完整评分卡）
- Dropped Candidates（被剔除原因 + 语义决策摘要）
- Deep Analysis（路由决策 + 分析结论）

---

#### 2.13 `engine.py` — Screener 引擎（主编排器）

**作用**：串联所有模块的执行顺序，协调数据流。

**执行顺序**：
```
Runtime Guard 验证
    → Universe 构建
    → Stage A 预筛（数据完整性/流动性/极端价格）
    → Stage B 三策略评分
    → Merger 合并与过滤
    → Name Resolver 补充公司名
    → Deep Analyzer（可选）
    → 数据一致性检查
    → 报告输出
```

---

#### 2.14 `name_resolver.py` — 公司名解析

**作用**：将股票代码转换为公司中文名（解决 Sina API 中文乱码问题）。

**策略**：
- 主源：`akshare.stock_info_a_code_name()`（全市场A股名称，一次获取）
- 备源：中证指数成分股权重数据中的名称
- 缓存：每日缓存到 `.tradingagents/cache/screener/names_YYYYMMDD.json`

---

#### 2.15 `cli/` — 命令行界面

**作用**：为 Screener 提供交互式/命令行两种使用方式。

| 文件 | 职责 |
|------|------|
| `app.py` | Typer CLI 根入口（无参数启动交互式向导） |
| `commands/run_impl.py` | `screener run` 子命令实现 |
| `formatters/terminal.py` | Rich 终端表格/面板格式化 |
| `interactive.py` | 交互式向导（Komo mascot + 步骤引导） |

**支持的所有运行模式**：
```bash
# MVP 模式（默认）
python -m tradingagents.screener.cli run --date 2026-05-08

# 全市场
python -m tradingagents.screener.cli run --mode FULL

# 聚焦板块
python -m tradingagents.screener.cli run --mode FOCUSED --focus-type sector --focus-value semiconductor

# 自定义列表
python -m tradingagents.screener.cli run --mode CUSTOM --tickers 600519,000001

# 跳过 Deep Analyzer（快速测试）
python -m tradingagents.screener.cli run --no-deep

# 仅输出 JSON
python -m tradingagents.screener.cli run --output json
```

---

### P-3: 评分公式设计分析

#### 3.1 三策略评分公式对比

| 维度 | 设计文档 (SCREENER_DESIGN.md §10) | 实际实现 | 偏离程度 |
|------|-----------------------------------|---------|--------|
| Strategy A 权重数 | 4个子分（fund_flow/momentum/macd/liquidity） | 9个子分 | **重大偏离** |
| Strategy A 数据要求 | MA20/MA60 + MACD（DIF/DEA） | MA20/MA60 + 趋势一致性 + 结构风险等 | 删除了 MACD（正确），增加更多维度 |
| Strategy B 权重数 | 4个子分（concept_heat/stock_strength/source_quality/liquidity） | 10个子分 | **较大偏离** |
| Strategy B 核心逻辑 | 概念热度 + 成分股排名 | 保留，扩展了板块领导力/竞争度/多概念重叠 | 基本保留 |
| Strategy C 公式 | 4个子分（institutional/northbound/earnings/liquidity） | 10个子分 + capital_quality_tag | **最大偏离** |

#### 3.2 Merger 融合规则分析

**设计文档描述**：
- 去重 + 共振加分（+5/命中策略数-1）+ 熔断过滤 + 分散化

**实际实现额外包含**：
1. **Semantic Priority（语义优先级）**：policy_strength（0-3）+ capital_tag（+4/-4）综合评分，影响排序优先级
2. **Conflict Resolution（冲突解析）**：8条规则处理三策略之间的语义冲突（强概念股 + 高技术风险时谁胜出）
3. **Cross-Strategy Conflict Detection**：检测策略间的分数spread（aligned/moderate/high/severe 四级）
4. **阈值全部参数化**：所有硬过滤边界均从 `SCREENER_THRESHOLDS` / `SCREENER_CONFIG` 读取

**设计意图澄清**：Merger 的扩展不是"过度设计"，而是工程实践中发现"简单加权平均"无法处理策略间冲突时的决策问题。扩展的语义层是必要的业务逻辑。

---

### P-4: 配置体系规模分析

**设计文档预期**：简单的 `SCREENER_UNIVERSE` + `SCREENER_THRESHOLDS` 常量定义

**实际实现**：高度参数化系统（6种模式 × 多级配置块 × 100+ 个阈值参数）

**评估**：
- ✅ **优点**：评分逻辑完全可调，无需改代码；适合 A/B 测试不同权重配置
- ⚠️ **缺点**：配置复杂度高，新用户上手门槛增加；需要配套配置文档
- 📌 **建议**：在 `Learning/About_Screener.md` 中增加配置项索引，并提供"推荐配置"注释

---

### P-5: 其他可优化项

#### P-5.1: 配置缓存 TTL 不一致

- `config.py` 中 `cache.ttl_hours = 12`（未被使用）
- `data_access.py` 中 probe 缓存 TTL = 60 分钟（通过 `a0_probe.cache_ttl_minutes`）
- **建议**：统一为 `cache.ttl_minutes` 或移除 `cache.ttl_hours`

#### P-5.2: Stage A 预筛未在设计文档中说明

- `engine.py` 的 `_run_stage_a()` 是性能优化，增加 Stage A/B 两级过滤
- **建议**：补充设计文档 §10A（新增章节）或在 `SCREENER_DESIGN.md` 中更新实施计划

#### P-5.3: `cache_key` 来源不一致

- `universe.py` 中 `cache_key` 构造在多处出现（`_fetch_constituents_for_indexes` 的 `cache_file` 命名与 `build_screening_universe` 的 `cache_key` 可能不一致）
- **建议**：统一缓存键生成逻辑

#### P-5.4: `strategies/__init__.py` 未导出 `StrategyOutcome`

- `strategies/__init__.py` 只导出三个策略类
- `StrategyOutcome` dataclass 定义在各策略文件内部，外部导入困难
- **建议**：在 `strategies/__init__.py` 中添加 `StrategyOutcome` 导出

---

### P-5 代码优化项状态

> Phase 3 已完成以下优化：

| 项目 | 状态 | 修改文件 |
|------|------|---------|
| P-5.1 配置缓存TTL统一 | ✅ 已完成 | `config.py`: `ttl_hours: 12` → `cache_ttl_minutes: 720` |
| P-5.2 Stage A 文档化 | 🔲 待完成 | 需更新 `SCREENER_DESIGN.md` |
| P-5.3 cache_key 生成逻辑统一 | ✅ 已完成 | `universe.py`: 统一为 `"{profile.lower()}_constituents"` |
| P-5.4 `StrategyOutcome` 导出 | ✅ 已完成 | `strategies/__init__.py` 新增导出 |

---

## Part 3: Phase 2 Bug 修复总结

> **所有 12 个 Bug 已全部修复完成 (2026-05-18)**

### 立即执行（P0-P1，必须修复）— ✅ 全部完成

| 优先级 | Bug ID | 任务 | 状态 |
|--------|--------|------|------|
| P0 | B-1 + B-2 | 修复 `overall_score` / `degraded` / `data_source_verified` 序列化错误 | ✅ 已修复 |
| P1 | B-3 | 修复 Universe 静默降级为 ETF 代码的问题 | ✅ 已修复 |

### 下一迭代（P1-P2，建议修复）— ✅ 全部完成

| 优先级 | Bug ID | 任务 | 状态 |
|--------|--------|------|------|
| P1 | B-4 | 增强 ST 识别逻辑（支持 placeholder name 场景） | ✅ 已修复 |
| P2 | B-5 | 修复 `policy.py` 进度显示 100% 的逻辑错误 | ✅ 已修复 |
| P1 | B-9 | 修复 `technical.py` 空数据兜底分数偏高 | ✅ 已修复 |
| P1 | B-10 | 修复 `run_impl.py` 异常处理暴露 traceback | ✅ 已修复 |

### 规划迭代（P2，视情况决定）— ✅ 全部完成

| 优先级 | Bug ID | 任务 | 状态 |
|--------|--------|------|------|
| P2 | B-6 | `ThrottledRequester` 警告收集机制完善 | ✅ 已修复 |
| P2 | B-7 | Merger 多 evidence 稳定性改进 | ✅ 已修复 |
| P2 | B-8 | Stage B 截断逻辑 | ✅ 已修复 |
| P2 | B-11 | Technical Strategy 重复遍历优化 | ✅ 已修复（进程级缓存） |
| P2 | B-12 | `llm_calls_total` 计数修复 | ✅ 已修复 |

### 文档同步（Phase 3）— 部分完成

- ✅ 更新 `EXECUTION_GUIDE.md` 执行记录
- ✅ 更新 `Plan.md` Bug 状态表
- ✅ 更新 `Plan.md` Part 3 总结
- ✅ P-5.1 ~ P-5.4 代码优化
- 🔲 更新 `SCREENER_DESIGN.md` §10 评分公式章节（Phase 3 待完成）
- 🔲 补充 Stage A 两级过滤的设计文档说明（Phase 3 待完成）

---

## Part 4: 任务拆分清单（Coding Agent 执行用）

以下为每个 Task 的可独立执行步骤，适合交给 Coding Agent 并行处理。

> **并行策略**：B-1.1 与 B-1.2 可并行；B-3.1 与 B-3.2 可并行；其余 Task 建议顺序执行。

### 批次 1（可并行，P0，~30min）

| Task | 文件 | 操作 |
|------|------|------|
| B-1.1 | `cli/commands/run_impl.py` | 将 `overall_score` 改为 `screening_score`，加 `_is_degraded()` 函数 |
| B-1.2 | `cli/formatters/terminal.py` | 将 `overall_score` 改为 `screening_score`，加 `_is_degraded()` 函数 |

### 批次 2（可并行，P1，~45min）

| Task | 文件 | 操作 |
|------|------|------|
| B-3.1 | `universe.py` | 将 `constituents = index_codes` 改为 `raise RuntimeError(...)` |
| B-3.2 | `engine.py` | 在 `build_screening_universe()` 外包裹 try-except |
| B-4.1 | `merger.py` | 增强 `_is_st_name()` 检查 `sector_tags` |

### 批次 3（独立，P2-P1，~60min）

| Task | 文件 | 操作 |
|------|------|------|
| B-5.1 | `strategies/policy.py` | 修复进度日志逻辑 |
| B-9.1 | `strategies/technical.py` | 评估并修复空数据兜底分数 |
| B-10.1 | `cli/commands/run_impl.py` | 删除 traceback 输出 |

### 批次 4（独立，P2，~2h）

| Task | 文件 | 操作 |
|------|------|------|
| B-6.1 | `throttling.py` + `data_access.py` | 确认并暴露警告 |
| B-7.1 | `merger.py` | 修改 `_find_signal_metrics()` 取最高分 |
| B-8.1 | `engine.py` | 添加 Stage B 截断逻辑 |
| B-11.1 | `data_access.py` | 增加进程级历史数据缓存 |
| B-12.1 | `engine.py` | 修复 `llm_calls_total` 计数 |

### 测试文件创建（建议在批次 1-3 完成后执行）

| 测试文件 | 测试目标 |
|---------|---------|
| `tests/test_screener_universe.py` | B-3.1: Universe API 全失败时显式错误 |
| `tests/test_screener_merger.py` | B-4.1: Placeholder name 场景下 ST 识别 |
