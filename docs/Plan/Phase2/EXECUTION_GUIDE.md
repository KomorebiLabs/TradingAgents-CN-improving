# Phase 2 执行指南

> **总览**: Screener Bug 修复共 12 个，分 4 个阶段执行
> **前置依赖**: 无（各阶段独立，可按序执行）
> **完整文档**: `docs/Plan/Phase2/Plan.md`

---

## 阶段总览

| 阶段 | 包含 Bug | 优先级 | 涉及文件 | 预计工作量 |
|------|---------|--------|---------|-----------|
| **Phase 2.1** | B-1, B-2 | P0 Fatal | `cli/run_impl.py`, `cli/formatters/terminal.py` | ~30min |
| **Phase 2.2** | B-3, B-4 | P1 High | `universe.py`, `engine.py`, `merger.py` | ~60min |
| **Phase 2.3** | B-5, B-9, B-10, B-12 | P1-P2 | `policy.py`, `technical.py`, `run_impl.py`, `engine.py` | ~60min |
| **Phase 2.4** | B-6, B-7, B-8, B-11 | P2 | `throttling.py`, `data_access.py`, `merger.py`, `engine.py` | ~2h |

---

## Phase 2.1: CLI 输出修复

**优先级**: P0 Fatal  
**前置**: 无  
**目标**: 修复 CLI 所有输出的评分和 Signal badge 显示

### 任务清单

#### Task 2.1-A: 修复 `run_impl.py` 的 JSON 序列化

文件：`tradingagents/screener/cli/commands/run_impl.py`

在 `_serialize_for_output()` 函数中，将候选字典的以下内容：

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

然后在文件内（建议在 `_signal_from_score()` 附近）新增：

```python
def _is_degraded(card) -> bool:
    """Check if any SignalEvidence in the card is degraded."""
    if not card.signal_breakdown:
        return False
    return any(e.degraded for e in card.signal_breakdown)
```

#### Task 2.1-B: 修复 `terminal.py` 的表格输出

文件：`tradingagents/screener/cli/formatters/terminal.py`

在 `print_ranking_table()` 函数中，第 57-59 行：

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

然后在文件顶部（建议在 `format_signal_badge()` 之后）新增：

```python
def _is_degraded(card) -> bool:
    """Check if any SignalEvidence in the card is degraded."""
    if not hasattr(card, "signal_breakdown") or not card.signal_breakdown:
        return False
    return any(getattr(e, "degraded", False) for e in card.signal_breakdown)
```

### 验证命令

```bash
# 验证 JSON 输出
python -m tradingagents.screener.cli run --tickers 600519 --no-deep --output json

# 验证终端表格
python -m tradingagents.screener.cli run --tickers 600519,000001 --no-deep
```

**验收标准**: Score 列有数值（非 N/A），Signal 列正确显示 BUY/HOLD/SELL 而非全部 SELL。

---

## Phase 2.2: Universe + ST 检测修复

**优先级**: P1 High  
**前置**: Phase 2.1 完成  
**目标**: 修复 Universe 静默降级 ETF 和 ST 漏检问题

### 任务清单

#### Task 2.2-A: Universe 成分股全失败时显式抛出错误

文件：`tradingagents/screener/universe.py`

在 `build_screening_universe()` 函数中，找到第 233-234 行：

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

#### Task 2.2-B: engine.py 捕获 Universe 构建错误

文件：`tradingagents/screener/engine.py`

在 `run()` 方法中，找到 `build_screening_universe()` 调用处（约第 208 行），增加 try-except：

```python
try:
    universe = build_screening_universe(mode=mode, config=self.config)
except RuntimeError as e:
    raise RuntimeError(
        f"Universe construction failed: {e}\n"
        "Hint: Try --mode CUSTOM with --tickers <list> to skip index constituent fetching."
    )
```

#### Task 2.2-C: 增强 Merger 的 ST 识别逻辑

文件：`tradingagents/screener/merger.py`

找到 `_is_st_name()` 函数（约第 739-741 行），修改为：

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

### 验证命令

```bash
# B-3: 写单元测试
pytest tests/test_screener_universe.py -v

# B-4: 写单元测试
pytest tests/test_screener_merger.py -v -k "st"
```

**验收标准**: Universe API 全失败时抛出明确错误消息；ST 股票即使 name 为 placeholder 也能被识别。

---

## Phase 2.3: 逻辑错误修复

**优先级**: P1-P2  
**前置**: Phase 2.2 完成  
**目标**: 修复进度日志、空数据兜底分数、异常处理暴露、计数错误

### 任务清单

#### Task 2.3-A: 修复 `policy.py` 进度日志

文件：`tradingagents/screener/strategies/policy.py`

找到第 299-301 行的无意义进度行（`total * 100 // total` 恒等于 100），删除该行。

然后在主循环内（`cards.append()` 之后）添加：

```python
# 每 10% 打印一次进度
if (idx + 1) % log_interval == 0 or (idx + 1) == total:
    pct = (idx + 1) * 100 // total
    _logger.info(f"[Policy] Analysis: {idx+1}/{total} ({pct}%) ...")
```

#### Task 2.3-B: 修复 `technical.py` 空数据兜底分数

文件：`tradingagents/screener/strategies/technical.py`

找到 `_compute_hist_metrics()` 函数中的 `empty` 字典（约第 268-298 行），将所有子分的初始值从 30~45 改为 0.0：

```python
empty = {
    "hist_rows": 0,
    "trend_alignment_score": 0.0,
    "momentum_score": 0.0,
    "drawdown_resilience_score": 0.0,
    "volatility_score": 0.0,
    "trend_consistency_score": 0.0,
    "structure_risk_score": 0.0,
    "volume_confirmation_score": 0.0,
    "breakout_quality_score": 0.0,
    "volume_price_divergence_score": 0.0,
    # 其余字段保持原样
}
```

#### Task 2.3-C: 修复 `run_impl.py` 异常处理暴露 traceback

文件：`tradingagents/screener/cli/commands/run_impl.py`

找到约第 433-438 行的 `except Exception` 块：

```python
# 修复前
except Exception as e:
    console.print(f"[red]Unexpected error:[/red] {e}")
    if verbose:
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
    raise typer.Exit(code=1)

# 修复后
except Exception as e:
    console.print(f"[red]Unexpected error:[/red] {e}")
    # 不输出 traceback，防止内部路径和变量名暴露
    raise typer.Exit(code=1)
```

#### Task 2.3-D: 修复 `engine.py` 的 `llm_calls_total` 计数

文件：`tradingagents/screener/engine.py`

找到 `ScreenerMetrics` 构造处（约第 275 行）：

```python
# 修复前
llm_calls_total=1 if deep_results else 0,

# 修复后
llm_calls_total=len(deep_results) if deep_results else 0,
```

### 验证命令

```bash
# B-5: 确认 Policy 进度日志按 10%/20%/.../100% 输出
python -m tradingagents.screener.cli run --tickers 600519 --no-deep -v

# B-9: 确认无效 ticker 不出现在候选中
python -m tradingagents.screener.cli run --tickers 999999 --no-deep

# B-12: 带 Deep Analyzer 运行，检查 metrics.llm_calls_total 等于实际分析数量
python -m tradingagents.screener.cli run --max-stocks 3 --tickers 600519,000001,300750
```

**验收标准**: 进度日志逐步输出；无效股票不进入候选；异常不暴露 traceback；LLM 调用计数正确。

---

## Phase 2.4: 优化与增强

**优先级**: P2（低优先级优化）  
**前置**: Phase 2.3 完成  
**目标**: 完善警告暴露、改进 Merger 稳定性、优化重复请求

### 任务清单

#### Task 2.4-A: `ThrottledRequester` 警告暴露

文件：`tradingagents/screener/throttling.py` + `data_access.py`

1. 读取 `throttling.py`，确认 `_warnings` 列表和 `get_warnings()` 方法存在。
2. 在 `data_access.py` 的 `get_interface_capability_summary()` 中，如果 `ThrottledRequester` 实例有 `get_warnings()` 方法，将其输出加入 `capability_summary["warnings"]`：

```python
throttle_warnings = throttled_requester.get_warnings()
if throttle_warnings:
    capability_summary["warnings"].extend(throttle_warnings)
```

#### Task 2.4-B: Merger evidence 取最高分而非第一个

文件：`tradingagents/screener/merger.py`

找到 `_find_signal_metrics()` 函数（约第 38-42 行）：

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

#### Task 2.4-C: Stage B 输入截断

文件：`tradingagents/screener/engine.py`

在 `run()` 方法中，找到 `_logger.info(f"[Screener] Stage B starting: ...")` 这一行，在其之前添加：

```python
stageb_max = self.config.get("stageb_max_input", 1000)
if len(stagea_pass_tickers) > stageb_max:
    _logger.info(f"[Screener] Stage B limit applied: {len(stagea_pass_tickers)} -> {stageb_max}")
    stagea_pass_tickers = stagea_pass_tickers[:stageb_max]
```

#### Task 2.4-D: 进程级历史数据缓存

文件：`tradingagents/screener/data_access.py`

在 `ScreenerDataAccess` 类中增加进程级缓存：

1. 在 `__init__` 中增加：`self._hist_cache: Dict[str, pd.DataFrame] = {}`
2. 在 `fetch_hist()` 方法中，查询前先检查缓存：

```python
def fetch_hist(self, ticker, start_date, end_date, adjust="qfq"):
    # 先查缓存
    cache_key = f"{ticker}_{start_date}_{end_date}_{adjust}"
    if cache_key in self._hist_cache:
        return self._hist_cache[cache_key]
    # ... 原有的请求逻辑 ...
    # 请求成功后写入缓存
    self._hist_cache[cache_key] = result
    return result
```

> 注意：如果 `fetch_hist` 内部调用的是其他方法（如 `fetch_tencent_hist`），缓存逻辑需要加在最外层调用处。

### 验证命令

```bash
# B-6: 检查 JSON 输出包含限速警告
python -m tradingagents.screener.cli run --tickers 600519 --no-deep --output json

# B-7: 运行 Merger 相关测试
pytest tests/test_screener_merger.py -v

# B-8: 测试 Stage B 截断
python -m tradingagents.screener.cli run --stageb-max-input 50 --tickers 600519,000001,300750 --no-deep
```

**验收标准**: 警告能暴露；Merger 逻辑稳定；Stage B 截断生效；历史数据不重复请求。

---

## 执行记录

| 阶段 | 执行日期 | 执行状态 | 备注 |
|------|---------|---------|------|
| Phase 2.1 | 2026-05-18 | ✅ 完成 | B-1.1, B-1.2, B-10.1: CLI评分/terminal输出/traceback修复 |
| Phase 2.2 | 2026-05-18 | ✅ 完成 | B-3.1, B-3.2, B-4.1: Universe显式错误/ST多维识别 |
| Phase 2.3 | 2026-05-18 | ✅ 完成 | B-5.1, B-9.1, B-12.1: 进度日志/空数据兜底/LLM计数 |
| Phase 2.4 | 2026-05-18 | ✅ 完成 | B-6.1, B-7.1, B-8.1, B-11.1: 警告暴露/最高分evidence/StageB截断/进程缓存 |
| Phase 3 | 2026-05-18 | ✅ 完成 | P-5优化: StrategyOutcome导出/cache_ttl统一/cache_key统一 |
