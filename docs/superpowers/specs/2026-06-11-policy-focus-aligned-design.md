# Design: PolicyStrategy Focus-Aware 概念选择修复

**Date:** 2026-06-11
**Status:** Draft
**Root Issue:** #PolicyConceptSelection

---

## 问题

当前 `_select_policy_concepts()` 在 `news_df` 匹配失败时执行 fallback：

```python
return concept_names[:5], True  # THS 字母序前5个，与 universe focus 完全无关
```

导致 `semiconductor` 主题跑出了「阿尔茨海默概念」「AI手机」「阿里巴巴概念」，所有 10 只股票被标记为 `policy_keyword_fallback`（policy_strength=0），触发了 `weak_policy_discount_under_technical_stress` 规则，全部被 Merger 丢弃。

---

## 调用链分析

```
engine.py:212    universe = build_screening_universe(mode=mode, config=self.config)
engine.py:249    policy_outcome = policy_strategy.run(stagea_pass_tickers, trade_date)

universe.py:368  metadata["focus_type"]  = focus_type   # e.g. "sector"
universe.py:380  metadata["focus_value"] = focus_value   # e.g. "semiconductor"
```

`universe.metadata` 已知 focus，但 engine 调用 `run()` 时没有传递。PolicyStrategy 的 `__init__` 已接收 `self.config`。

---

## 修改计划

### Step 1: engine.py — 注入 focus 到 config

在 `_build_strategies()` 调用前，从 `universe.metadata` 提取 focus 并注入 `self.config`：

```python
# 在 engine.py run() 方法中，build_screening_universe 之后
if universe.metadata.get("focus_type"):
    self.config["policy_focus"] = {
        "focus_type": universe.metadata["focus_type"],
        "focus_value": universe.metadata["focus_value"],
    }

technical_strategy, policy_strategy, smart_money_strategy = self._build_strategies(data_access)
```

`self.config` 是 `ScreenerEngine` 实例变量，传递给三个 Strategy 的 `__init__`。

### Step 2: policy.py — 修改 `_select_policy_concepts()` 签名

```python
# Before
@staticmethod
def _select_policy_concepts(concept_df: Any, news_df: Any) -> tuple[list[str], bool]:

# After
@staticmethod
def _select_policy_concepts(
    concept_df: Any,
    news_df: Any,
    policy_focus: Dict[str, str] | None = None,
) -> tuple[list[str], bool, str]:  # 新增返回值: selection_mode
```

返回值的第三个元素 `selection_mode` 取值：
- `"news_matched"` — news 内容精确命中
- `"focus_aligned"` — news 失败，用 focus 语义匹配
- `"keyword_fallback"` — 完全失败，THS 前5个兜底

### Step 3: policy.py — 实现 focus 语义匹配逻辑

```python
# 新增常量（文件顶部 POLICY_KEYWORDS 附近）
_FOCUS_ALIAS_KEYWORDS: Dict[str, List[str]] = {
    "semiconductor": ["半导体", "芯片", "集成电路", "集成电路制造", "半导体设备"],
    "new_energy": ["新能源", "光伏", "储能", "电池", "新能源汽车"],
    "AI": ["人工智能", "AI", "大模型", "算力", "AI芯片"],
    "robot": ["机器人", "自动化", "智能制造", "人形机器人"],
    "low_altitude": ["低空", "无人机", "通航", "eVTOL"],
}

def _select_policy_concepts(concept_df, news_df, policy_focus=None):
    if concept_df is None or getattr(concept_df, "empty", True):
        return [], True, "keyword_fallback"

    concept_names = concept_df["name"].astype(str).tolist()
    if not concept_names:
        return [], True, "keyword_fallback"

    # Step A: news_df 无数据（None/empty）→ 无法判断，返回 THS 前5 + keyword_mode=True
    if news_df is None or getattr(news_df, "empty", True):
        return concept_names[:5], True, "keyword_fallback"

    # Step B: news_df 有内容，尝试精确匹配
    text_columns = [col for col in news_df.columns
                    if str(col) in {"事件", "内容", "标题", "event"}]
    joined = " ".join(str(v) for col in text_columns
                      for v in news_df[col].astype(str).tolist())
    matched = [name for name in concept_names if name in joined]
    if matched:
        return matched[:5], False, "news_matched"

    # Step C: POLICY_KEYWORDS 匹配（原有逻辑）
    keyword_concepts = []
    for concept_name, keywords in POLICY_KEYWORDS.items():
        if any(kw in joined for kw in keywords):
            keyword_concepts.append(concept_name)
    keyword_fallback = [n for n in concept_names if any(s in n for s in keyword_concepts)]
    if keyword_fallback:
        return keyword_fallback[:5], True, "keyword_fallback"

    # Step D: news 匹配失败但存在 focus → 用 focus 语义匹配（新增）
    if policy_focus and policy_focus.get("focus_value"):
        focus_value = policy_focus["focus_value"].lower()
        focus_aliases = _FOCUS_ALIAS_KEYWORDS.get(focus_value, [])
        if not focus_aliases:
            focus_aliases = [policy_focus["focus_value"]]  # 直接用 focus_value 本身

        matched = [
            name for name in concept_names
            if any(alias in name for alias in focus_aliases)
        ]
        if matched:
            return matched[:5], True, "focus_aligned"

    # Step E: 完全兜底（原有行为，保留）
    return concept_names[:5], True, "keyword_fallback"
```

**精确包含匹配说明：** 同花顺概念名为规范中文（如 "半导体"），无需 fuzzy match。THS 的 373 个概念中，预期命中：
- `"半导体"` 直接命中
- `"集成电路"` 被 `"集成电路制造"` 间接覆盖（alias 包含即可）
- `"AI手机"`, `"阿里巴巴概念"` 不在任何 focus_aliases 中 → 正确过滤

### Step 4: policy.py — 修改 `run()` 调用点

```python
policy_focus = self.config.get("policy_focus")  # 提取 focus

selected_concepts, keyword_mode, selection_mode = self._select_policy_concepts(
    concept_df,
    news_df,
    policy_focus,
)
```

### Step 5: policy.py — 修改 `_build_stock_selection_tag()`

当前决策树：

```python
def _build_stock_selection_tag(member_metrics, cross_hit_score, keyword_mode):
    if member_metrics.get("top_tier_hit"):
        return "policy_top_stock"      # strength=3 ✓
    if member_metrics.get("is_member"):
        return "policy_core_member"     # strength=2 ✓
    if cross_hit_score >= 80 and not keyword_mode:
        return "policy_cross_hit_candidate"
    return "policy_keyword_fallback"    # strength=0 ← 错误：focus_aligned 但非 member 时误判
```

**问题：** 当 `is_member=False` 且 `keyword_mode=True` 时，无论是否 focus_aligned，都返回 `policy_keyword_fallback`（strength=0）。对于 focus_aligned 但非 THS 成分股的股票，应该返回 `policy_cross_hit`（strength=1）。

**修复：** 新增 `selection_mode` 参数，区分三种 fallback 来源：

```python
def _build_stock_selection_tag(
    member_metrics: Dict[str, Any],
    cross_hit_score: float,
    keyword_mode: bool,
    selection_mode: str = "keyword_fallback",  # 新增: news_matched | focus_aligned | keyword_fallback
) -> str:
    if member_metrics.get("top_tier_hit"):
        return "policy_top_stock"
    if member_metrics.get("is_member"):
        return "policy_core_member"
    if cross_hit_score >= 80 and not keyword_mode:
        return "policy_cross_hit_candidate"
    # Focus aligned 但非 member → 给予 strength=1 而非 0
    if selection_mode == "focus_aligned":
        return "policy_focus_aligned"
    return "policy_keyword_fallback"
```

同时修改 `run()` 中的调用点：

```python
stock_selection_tag = self._build_stock_selection_tag(
    member_metrics,
    cross_hit_score,
    keyword_mode,
    selection_mode,  # 新增
)
```

### Step 5.5: policy.py — 修改 `_build_trigger_reason()`

当前逻辑：`keyword_mode=True` 时返回 `"policy_event_keyword_fallback"`。

问题是 `keyword_mode=True` 包含两种情况：
1. `selection_mode == "keyword_fallback"` — 真正的无匹配 fallback
2. `selection_mode == "focus_aligned"` — 有语义匹配，只是没有 news 数据

**修复：** `_build_trigger_reason()` 增加 `selection_mode` 参数：

```python
@staticmethod
def _build_trigger_reason(
    keyword_mode: bool,
    stock_selection_tag: str,
    concept_weight_bucket: str,
    selection_mode: str = "keyword_fallback",  # 新增
) -> str:
    if stock_selection_tag == "policy_top_stock":
        return "policy_concept_top_pick"
    if concept_weight_bucket in ("concept_weight_core", "concept_weight_quality"):
        return "policy_concept_core_member"
    if stock_selection_tag == "policy_focus_aligned":
        return "policy_event_focus_aligned"  # 新增：focus 语义对齐
    if keyword_mode:
        return "policy_event_keyword_fallback"
    return "policy_event_concept_map"
```

### Step 7: policy.py — 修改 `run()` 中 `_build_trigger_reason()` 调用点

在 `run()` 方法中将 `_build_trigger_reason()` 调用增加 `selection_mode` 参数：

```python
trigger_reason = self._build_trigger_reason(
    keyword_mode,
    stock_selection_tag,
    concept_weight_bucket,
    selection_mode,  # 新增
)
```

### Step 8: merger.py — 新增 `policy_focus_aligned` 分支

在 `_policy_strength()` 中新增：

```python
elif tag == "policy_focus_aligned":
    return 1  # strength=1，位于 keyword_fallback(0) 和 core_member(2) 之间
```

此处的 strength=1 是因为 focus_aligned 比纯 keyword_fallback 有更好的语义关联，但没有 THS 成分股验证。

**注意：** 当 focus_aligned 的股票同时是 THS 成分股（`is_member=True`）时，`_build_stock_selection_tag` 会返回 `policy_core_member`，Merger 取 strength=2。这是正确的行为。

### Step 9: 完整返回值调整

`_select_policy_concepts()` 最终返回 3 值：

```python
return concept_names[:5], True, "keyword_fallback"  # (selected, keyword_mode, selection_mode)
return matched[:5], False, "news_matched"
return matched[:5], True, "focus_aligned"
```

`keyword_mode` 控制技术分和策略逻辑，`selection_mode` 控制 tag 决策树。

### Step 10: 测试验证

| 测试用例 | 预期结果 |
|---------|---------|
| FOCUSED mode, focus=semiconductor, news 无半导体 | 概念选为「半导体」系，tag=`policy_focus_aligned` |
| FOCUSED mode, focus=new_energy, news 无新能源 | 概念选为「新能源」系，tag=`policy_focus_aligned` |
| FOCUSED mode, focus=semiconductor, news 有半导体 | 概念选为 news 命中，tag=`policy_top_stock` 或 `policy_core_member`（不变） |
| FULL/MVP mode, 无 focus | 保留原有 `concept_names[:5]` 行为，tag=`policy_keyword_fallback`（strength=0） |

---

## 非 FOCUSED 模式处理（Step 3 调整）

用户确认：非 FOCUSED 模式走方案一（保留原有 `concept_names[:5]` 行为）。

当前设计 Step 3 中：
- `if policy_focus` 为 None → 直接跳到 Step C 兜底，保留原有行为

未来可探索：非 FOCUSED 模式用 universe 股票列表反向推断概念（方案二），作为独立优化项。

---

## 改动文件清单

| 文件 | 改动类型 |
|------|---------|
| `tradingagents/screener/engine.py` | 修改：注入 focus 到 config |
| `tradingagents/screener/strategies/policy.py` | 修改：`_select_policy_concepts()`, `run()`, `_build_stock_selection_tag()` |
| `tradingagents/screener/merger.py` | 修改：`_policy_strength()` |
| `tests/test_screener_policy_focus.py` | 新增：单元测试 |

---

## 设计原则

- **YAGNI：** 不做 fuzzy match，不做 score 阈值排序，精确包含匹配即可
- **最小侵入：** 不改数据源、不改 Merger 阈值、不改接口签名（`PolicyStrategy.run()` 不变）
- **透明标记：** `keyword_mode` 仍为 True，但 `policy_selection_tag` 区分了 `focus_aligned` vs `keyword_fallback`
