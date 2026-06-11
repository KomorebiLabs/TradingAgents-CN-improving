# PolicyStrategy Focus-Aware 概念选择修复 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 当 `news_df` 匹配失败时，用 universe 的 focus 语义选择同花顺概念，而非按字母序取前5个。

**Architecture:** 在 `_select_policy_concepts()` 中新增 Step D（focus 语义匹配）；在 `_build_stock_selection_tag()` 和 `_build_trigger_reason()` 中新增 `selection_mode` 参数以区分 `focus_aligned` vs `keyword_fallback`；在 `merger.py` 中为 `policy_focus_aligned` 赋予 strength=1。

**Tech Stack:** Python, pandas, 修改现有 screener 策略模块

---

## 准备工作：理解现有代码

在开始之前，实现者需要阅读以下文件以了解上下文：

- `tradingagents/screener/engine.py` 第185–260行（`run()` 方法，Step 1 改动位置）
- `tradingagents/screener/strategies/policy.py` 第1–115行（imports、POLICY_KEYWORDS、`run()` 前半部分）
- `tradingagents/screener/strategies/policy.py` 第360–395行（`_select_policy_concepts()` 现有实现）
- `tradingagents/screener/strategies/policy.py` 第760–800行（`_build_stock_selection_tag()` 和 `_build_trigger_reason()`）
- `tradingagents/screener/strategies/policy.py` 第190–210行（`run()` 中两个方法的调用点）
- `tradingagents/screener/merger.py` 第1–80行（`_policy_strength()` 位置）

---

## Task 1: engine.py — 注入 focus 到 config

**Files:**
- Modify: `tradingagents/screener/engine.py`

**Change:** 在 `run()` 方法中，`build_screening_universe()` 成功后、`_build_strategies()` 调用前，提取 universe focus 注入 `self.config`。

- [ ] **Step 1: 找到插入位置**

在 `engine.py` 中，找到第212行 `universe = build_screening_universe(mode=mode, config=self.config)` 之后、紧接着 `_build_strategies()` 调用之前的位置。

在两者之间插入：

```python
        # P5-focus: propagate universe focus to strategy config
        if universe.metadata.get("focus_type"):
            self.config["policy_focus"] = {
                "focus_type": universe.metadata["focus_type"],
                "focus_value": universe.metadata["focus_value"],
            }

```

完整插入上下文（供参考）：

```python
        try:
            universe = build_screening_universe(mode=mode, config=self.config)
        except RuntimeError as e:
            raise RuntimeError(
                f"Universe construction failed: {e}\n"
                "Hint: Try --mode CUSTOM with --tickers <list> to skip index constituent fetching."
            )

        # P5-focus: propagate universe focus to strategy config
        if universe.metadata.get("focus_type"):
            self.config["policy_focus"] = {
                "focus_type": universe.metadata["focus_type"],
                "focus_value": universe.metadata["focus_value"],
            }

        print_stage_header("Stage A", f"light pre-screening of {len(universe.tickers)} stocks")
```

- [ ] **Step 2: 验证语法**

运行：`python -m py_compile tradingagents/screener/engine.py`
预期：无输出（语法正确）

- [ ] **Step 3: Commit**

```bash
git add tradingagents/screener/engine.py
git commit -m "feat(screener): inject universe focus into config for PolicyStrategy"
```

---

## Task 2: policy.py — `_select_policy_concepts()` 新增 focus 语义匹配

**Files:**
- Modify: `tradingagents/screener/strategies/policy.py`

**Change:** 新增 `_FOCUS_ALIAS_KEYWORDS` 常量；修改 `_select_policy_concepts()` 签名和实现。

- [ ] **Step 1: 添加 `_FOCUS_ALIAS_KEYWORDS` 常量**

在 `policy.py` 文件中，找到 `POLICY_KEYWORDS` 定义（约第28–34行），在其下方添加：

```python
# P5-focus: mapping from universe focus_value to THS concept name aliases
# Used when news_df matching fails but universe has a focus (FOCUSED mode)
_FOCUS_ALIAS_KEYWORDS: Dict[str, List[str]] = {
    "semiconductor": ["半导体", "芯片", "集成电路", "集成电路制造", "半导体设备"],
    "new_energy": ["新能源", "光伏", "储能", "电池", "新能源汽车"],
    "AI": ["人工智能", "AI", "大模型", "算力", "AI芯片"],
    "robot": ["机器人", "自动化", "智能制造", "人形机器人"],
    "low_altitude": ["低空", "无人机", "通航", "eVTOL"],
}
```

- [ ] **Step 2: 修改 `_select_policy_concepts()` 签名**

找到第360行的方法定义：

```python
def _select_policy_concepts(concept_df: Any, news_df: Any) -> tuple[list[str], bool]:
```

替换为：

```python
def _select_policy_concepts(
    concept_df: Any,
    news_df: Any,
    policy_focus: Dict[str, str] | None = None,
) -> tuple[list[str], bool, str]:
    """Select policy concepts from THS concept list.

    Returns:
        selected_concepts: list of concept names
        keyword_mode: bool — True if relying on keyword/fallback matching (reduces scores)
        selection_mode: str — "news_matched" | "focus_aligned" | "keyword_fallback"
    """
```

- [ ] **Step 3: 替换方法实现**

找到第360–389行的整个 `_select_policy_concepts` 方法体（从 `if concept_df is None` 到 `return concept_names[:5], True`），替换为以下实现：

```python
    if concept_df is None or getattr(concept_df, "empty", True):
        return [], True, "keyword_fallback"

    concept_names = concept_df["name"].astype(str).tolist() if "name" in concept_df.columns else []
    if not concept_names:
        return [], True, "keyword_fallback"

    # Step A: news_df 无数据（None/empty）→ 无法判断，返回 THS 前5 + keyword_mode=True
    if news_df is None or getattr(news_df, "empty", True):
        return concept_names[:5], True, "keyword_fallback"

    # Step B: news_df 有内容，尝试精确匹配
    text_columns = [col for col in news_df.columns if str(col) in {"事件", "内容", "标题", "event"}]
    joined = " ".join(
        str(value)
        for col in text_columns
        for value in news_df[col].astype(str).tolist()
    )
    matched = [name for name in concept_names if name in joined]
    if matched:
        return matched[:5], False, "news_matched"

    # Step C: POLICY_KEYWORDS 匹配（原有逻辑）
    keyword_concepts: List[str] = []
    for concept_name, keywords in POLICY_KEYWORDS.items():
        if any(keyword in joined for keyword in keywords):
            keyword_concepts.append(concept_name)

    keyword_fallback = [n for n in concept_names if any(seed in n for seed in keyword_concepts)]
    if keyword_fallback:
        return keyword_fallback[:5], True, "keyword_fallback"

    # Step D: news 匹配失败但存在 focus → 用 focus 语义匹配（新增）
    if policy_focus and policy_focus.get("focus_value"):
        focus_value = policy_focus["focus_value"].lower()
        focus_aliases = _FOCUS_ALIAS_KEYWORDS.get(focus_value, [])
        if not focus_aliases:
            # focus_value 不在已知别名表，尝试直接用 focus_value 本身匹配
            focus_aliases = [policy_focus["focus_value"]]

        matched = [
            name for name in concept_names
            if any(alias in name for alias in focus_aliases)
        ]
        if matched:
            return matched[:5], True, "focus_aligned"

    # Step E: 完全兜底（原有行为，保留）
    return concept_names[:5], True, "keyword_fallback"
```

- [ ] **Step 4: 验证语法**

运行：`python -m py_compile tradingagents/screener/strategies/policy.py`
预期：无输出（语法正确）

- [ ] **Step 5: Commit**

```bash
git add tradingagents/screener/strategies/policy.py
git commit -m "feat(screener): add focus-aware concept selection in PolicyStrategy"
```

---

## Task 3: policy.py — 更新 `run()` 调用点

**Files:**
- Modify: `tradingagents/screener/strategies/policy.py`

**Change:** 在 `run()` 中提取 `policy_focus` 并传递给 `_select_policy_concepts`；更新两个下游方法的调用点。

- [ ] **Step 1: 修改 `_select_policy_concepts()` 调用点**

找到第109行附近：

```python
selected_concepts, keyword_mode = self._select_policy_concepts(concept_df, news_df)
```

替换为：

```python
        policy_focus = self.config.get("policy_focus")
        selected_concepts, keyword_mode, selection_mode = self._select_policy_concepts(
            concept_df,
            news_df,
            policy_focus,
        )
```

注意：这段代码需要正确处理缩进。它在 `run()` 方法内部，有额外的一级缩进（4空格）。在编辑器中找到原有行，替换为以上两段代码。

- [ ] **Step 2: 更新 `_build_stock_selection_tag()` 调用点**

找到第194行附近：

```python
stock_selection_tag = self._build_stock_selection_tag(member_metrics, cross_hit_score, keyword_mode)
```

替换为：

```python
stock_selection_tag = self._build_stock_selection_tag(
    member_metrics,
    cross_hit_score,
    keyword_mode,
    selection_mode,
)
```

- [ ] **Step 3: 更新 `_build_trigger_reason()` 调用点**

找到第200–205行附近（`trigger_reason = self._build_trigger_reason(` 那一行），找到对应的调用：

```python
trigger_reason = self._build_trigger_reason(
    keyword_mode,
    stock_selection_tag,
    concept_weight_bucket,
)
```

替换为：

```python
trigger_reason = self._build_trigger_reason(
    keyword_mode,
    stock_selection_tag,
    concept_weight_bucket,
    selection_mode,
)
```

- [ ] **Step 4: 验证语法**

运行：`python -m py_compile tradingagents/screener/strategies/policy.py`
预期：无输出（语法正确）

- [ ] **Step 5: Commit**

```bash
git add tradingagents/screener/strategies/policy.py
git commit -m "refactor(screener): wire selection_mode through PolicyStrategy run() call chain"
```

---

## Task 4: policy.py — 修改 `_build_stock_selection_tag()` 和 `_build_trigger_reason()`

**Files:**
- Modify: `tradingagents/screener/strategies/policy.py`

**Change:** 两个方法增加 `selection_mode` 参数并实现对应分支。

- [ ] **Step 1: 修改 `_build_stock_selection_tag()`**

找到第760–771行的方法定义：

```python
def _build_stock_selection_tag(
    member_metrics: Dict[str, Any],
    cross_hit_score: float,
    keyword_mode: bool,
) -> str:
    if member_metrics.get("top_tier_hit"):
        return "policy_top_stock"
    if member_metrics.get("is_member"):
        return "policy_core_member"
    if cross_hit_score >= 80 and not keyword_mode:
        return "policy_cross_hit_candidate"
    return "policy_keyword_fallback"
```

替换为：

```python
def _build_stock_selection_tag(
    member_metrics: Dict[str, Any],
    cross_hit_score: float,
    keyword_mode: bool,
    selection_mode: str = "keyword_fallback",
) -> str:
    if member_metrics.get("top_tier_hit"):
        return "policy_top_stock"
    if member_metrics.get("is_member"):
        return "policy_core_member"
    if cross_hit_score >= 80 and not keyword_mode:
        return "policy_cross_hit_candidate"
    # P5-focus: focus_aligned but not a THS member → better than pure keyword fallback
    if selection_mode == "focus_aligned":
        return "policy_focus_aligned"
    return "policy_keyword_fallback"
```

- [ ] **Step 2: 修改 `_build_trigger_reason()`**

找到第773–793行的方法定义：

```python
def _build_trigger_reason(
    keyword_mode: bool,
    stock_selection_tag: str,
    concept_weight_bucket: str,
) -> str:
    """Build the trigger reason string for a signal card.

    New Phase4 logic (replaces board_rank_bucket references):
        policy_top_stock              -> policy_concept_top_pick
        concept_weight_bucket starts with concept_weight_core/quality -> policy_concept_core_member
        keyword_mode                  -> policy_event_keyword_fallback
        otherwise                     -> policy_event_concept_map
    """
    if stock_selection_tag == "policy_top_stock":
        return "policy_concept_top_pick"
    if concept_weight_bucket in ("concept_weight_core", "concept_weight_quality"):
        return "policy_concept_core_member"
    if keyword_mode:
        return "policy_event_keyword_fallback"
    return "policy_event_concept_map"
```

替换为：

```python
def _build_trigger_reason(
    keyword_mode: bool,
    stock_selection_tag: str,
    concept_weight_bucket: str,
    selection_mode: str = "keyword_fallback",
) -> str:
    """Build the trigger reason string for a signal card.

    Phase4 + P5-focus logic:
        policy_top_stock              -> policy_concept_top_pick
        concept_weight_core/quality    -> policy_concept_core_member
        policy_focus_aligned          -> policy_event_focus_aligned
        keyword_mode                  -> policy_event_keyword_fallback
        otherwise                     -> policy_event_concept_map
    """
    if stock_selection_tag == "policy_top_stock":
        return "policy_concept_top_pick"
    if concept_weight_bucket in ("concept_weight_core", "concept_weight_quality"):
        return "policy_concept_core_member"
    # P5-focus: distinguish focus_aligned from pure keyword fallback
    if stock_selection_tag == "policy_focus_aligned":
        return "policy_event_focus_aligned"
    if keyword_mode:
        return "policy_event_keyword_fallback"
    return "policy_event_concept_map"
```

- [ ] **Step 3: 验证语法**

运行：`python -m py_compile tradingagents/screener/strategies/policy.py`
预期：无输出（语法正确）

- [ ] **Step 4: Commit**

```bash
git add tradingagents/screener/strategies/policy.py
git commit -m "feat(screener): add selection_mode parameter to tag and trigger methods"
```

---

## Task 5: merger.py — 新增 `policy_focus_aligned` 分支

**Files:**
- Modify: `tradingagents/screener/merger.py`

**Change:** 在 `_policy_strength()` 中为 `policy_focus_aligned` 赋予 strength=1。

- [ ] **Step 1: 找到 `_policy_strength()` 方法**

在 `merger.py` 中搜索 `_policy_strength` 方法，阅读其内容，找到处理 `policy_keyword_fallback` 的 `else` 分支。

典型结构如下（行号可能不同）：

```python
def _policy_strength(tag: str) -> int:
    if tag == "policy_top_stock":
        return 3
    if tag == "policy_core_member":
        return 2
    if tag == "policy_cross_hit":
        return 1
    return 0
```

或者可能在 `elif` 链中。找到 `return 0` 之前的最后一个分支，在其后、`return 0` 之前插入：

```python
    # P5-focus: focus-aligned fallback is semantically better than keyword fallback
    if tag == "policy_focus_aligned":
        return 1
```

即，在 `if tag == "policy_cross_hit": return 1` 之后添加。

- [ ] **Step 2: 验证语法**

运行：`python -m py_compile tradingagents/screener/merger.py`
预期：无输出（语法正确）

- [ ] **Step 3: Commit**

```bash
git add tradingagents/screener/merger.py
git commit -m "feat(screener): assign strength=1 to policy_focus_aligned in merger"
```

---

## Task 6: 新增单元测试

**Files:**
- Create: `tests/test_screener_policy_focus.py`

**Change:** 为 focus-aware 概念选择逻辑写单元测试。

- [ ] **Step 1: 写测试文件**

创建 `tests/test_screener_policy_focus.py`，内容如下：

```python
"""Tests for PolicyStrategy focus-aware concept selection (P5-focus)."""

from __future__ import annotations

import pandas as pd
from tradingagents.screener.strategies.policy import (
    PolicyStrategy,
    _FOCUS_ALIAS_KEYWORDS,
)


class TestSelectPolicyConcepts:
    """Test _select_policy_concepts with focus-aware logic."""

    def _make_concept_df(self, names):
        return pd.DataFrame({"name": names})

    def _make_news_df(self, text):
        return pd.DataFrame({"事件": [text]})

    # --- focus_aligned cases ---

    def test_focus_aligned_returns_semiconductor_concepts(self):
        """When news misses semiconductor but focus=semiconductor, selects 半导体/芯片."""
        concept_df = self._make_concept_df([
            "阿尔茨海默概念", "AI手机", "阿里巴巴概念", "半导体", "芯片"
        ])
        news_df = self._make_news_df("今日市场平稳")
        policy_focus = {"focus_type": "sector", "focus_value": "semiconductor"}

        result = PolicyStrategy._select_policy_concepts(concept_df, news_df, policy_focus)
        concepts, keyword_mode, selection_mode = result

        assert selection_mode == "focus_aligned", f"Expected focus_aligned, got {selection_mode}"
        assert keyword_mode is True
        assert "半导体" in concepts
        assert "芯片" in concepts
        assert "AI手机" not in concepts

    def test_focus_aligned_unknown_focus_uses_fallback(self):
        """When focus_value not in _FOCUS_ALIAS_KEYWORDS, falls back to raw value matching."""
        concept_df = self._make_concept_df(["未知概念", "新材料"])
        news_df = self._make_news_df("今日市场平稳")
        policy_focus = {"focus_type": "sector", "focus_value": "new_material"}

        concepts, keyword_mode, selection_mode = PolicyStrategy._select_policy_concepts(
            concept_df, news_df, policy_focus
        )

        assert selection_mode == "focus_aligned"
        assert "新材料" in concepts

    def test_focus_aligned_empty_concept_df(self):
        """Empty concept_df returns empty list + keyword_fallback."""
        concept_df = pd.DataFrame(columns=["name"])
        news_df = self._make_news_df("半导体利好")
        policy_focus = {"focus_type": "sector", "focus_value": "semiconductor"}

        concepts, keyword_mode, selection_mode = PolicyStrategy._select_policy_concepts(
            concept_df, news_df, policy_focus
        )

        assert concepts == []
        assert selection_mode == "keyword_fallback"

    def test_focus_aligned_none_concept_df(self):
        """None concept_df returns THS-style first-5 + keyword_fallback."""
        news_df = self._make_news_df("半导体利好")
        policy_focus = {"focus_type": "sector", "focus_value": "semiconductor"}

        concepts, keyword_mode, selection_mode = PolicyStrategy._select_policy_concepts(
            None, news_df, policy_focus
        )

        assert concepts == []
        assert selection_mode == "keyword_fallback"

    # --- news_matched cases (existing logic unchanged) ---

    def test_news_matched_exact_concept(self):
        """When news contains exact concept name, returns news_matched."""
        concept_df = self._make_concept_df(["半导体", "AI手机", "新能源"])
        news_df = self._make_news_df("半导体板块今日走强")

        concepts, keyword_mode, selection_mode = PolicyStrategy._select_policy_concepts(
            concept_df, news_df, None
        )

        assert selection_mode == "news_matched"
        assert keyword_mode is False
        assert "半导体" in concepts

    # --- keyword_fallback cases ---

    def test_keyword_fallback_no_focus(self):
        """When no news and no focus, returns keyword_fallback with first 5."""
        concept_df = self._make_concept_df(["阿尔茨海默概念", "AI手机", "阿里巴巴概念"])
        news_df = None

        concepts, keyword_mode, selection_mode = PolicyStrategy._select_policy_concepts(
            concept_df, news_df, None
        )

        assert selection_mode == "keyword_fallback"
        assert keyword_mode is True
        assert len(concepts) == 3  # only 3 concepts exist

    # --- priority: news > keyword > focus > fallback ---

    def test_priority_news_over_keyword_over_focus(self):
        """Selection priority: news_matched > keyword_fallback > focus_aligned."""
        concept_df = self._make_concept_df(["半导体", "新能源"])
        news_df = self._make_news_df("半导体板块走强")
        policy_focus = {"focus_type": "sector", "focus_value": "new_energy"}

        concepts, keyword_mode, selection_mode = PolicyStrategy._select_policy_concepts(
            concept_df, news_df, policy_focus
        )

        assert selection_mode == "news_matched"


class TestBuildStockSelectionTag:
    """Test _build_stock_selection_tag with selection_mode parameter."""

    def test_focus_aligned_returns_policy_focus_aligned_tag(self):
        """When focus_aligned but not member, returns policy_focus_aligned."""
        tag = PolicyStrategy._build_stock_selection_tag(
            member_metrics={"is_member": False, "top_tier_hit": False},
            cross_hit_score=40.0,
            keyword_mode=True,
            selection_mode="focus_aligned",
        )
        assert tag == "policy_focus_aligned"

    def test_keyword_fallback_returns_keyword_fallback_tag(self):
        """When keyword_fallback and not member, returns policy_keyword_fallback."""
        tag = PolicyStrategy._build_stock_selection_tag(
            member_metrics={"is_member": False, "top_tier_hit": False},
            cross_hit_score=40.0,
            keyword_mode=True,
            selection_mode="keyword_fallback",
        )
        assert tag == "policy_keyword_fallback"

    def test_is_member_overrides_selection_mode(self):
        """When is_member=True, returns policy_core_member regardless of selection_mode."""
        tag = PolicyStrategy._build_stock_selection_tag(
            member_metrics={"is_member": True, "top_tier_hit": False},
            cross_hit_score=40.0,
            keyword_mode=True,
            selection_mode="focus_aligned",
        )
        assert tag == "policy_core_member"


class TestBuildTriggerReason:
    """Test _build_trigger_reason with selection_mode parameter."""

    def test_focus_aligned_returns_focus_aligned_reason(self):
        """policy_focus_aligned tag maps to policy_event_focus_aligned."""
        reason = PolicyStrategy._build_trigger_reason(
            keyword_mode=True,
            stock_selection_tag="policy_focus_aligned",
            concept_weight_bucket="concept_weight_unconfirmed",
            selection_mode="focus_aligned",
        )
        assert reason == "policy_event_focus_aligned"

    def test_keyword_fallback_returns_keyword_fallback_reason(self):
        """keyword_mode=True with keyword_fallback maps to policy_event_keyword_fallback."""
        reason = PolicyStrategy._build_trigger_reason(
            keyword_mode=True,
            stock_selection_tag="policy_keyword_fallback",
            concept_weight_bucket="concept_weight_unconfirmed",
            selection_mode="keyword_fallback",
        )
        assert reason == "policy_event_keyword_fallback"


class TestFocusAliasKeywords:
    """Test that _FOCUS_ALIAS_KEYWORDS covers expected focus values."""

    def test_semiconductor_has_expected_aliases(self):
        assert "半导体" in _FOCUS_ALIAS_KEYWORDS["semiconductor"]
        assert "芯片" in _FOCUS_ALIAS_KEYWORDS["semiconductor"]

    def test_new_energy_has_expected_aliases(self):
        assert "新能源" in _FOCUS_ALIAS_KEYWORDS["new_energy"]
        assert "光伏" in _FOCUS_ALIAS_KEYWORDS["new_energy"]
```

- [ ] **Step 2: 运行测试**

运行：`python -m pytest tests/test_screener_policy_focus.py -v`

在实现之前，测试应该因为缺少参数或方法不存在而失败。实现完成后，所有测试应该通过。

- [ ] **Step 3: Commit**

```bash
git add tests/test_screener_policy_focus.py
git commit -m "test(screener): add unit tests for focus-aware concept selection"
```

---

## 集成验证

完成所有 Tasks 后，运行完整的回归测试：

```bash
python -m pytest tests/test_screener_*.py -v --tb=short
```

确保没有破坏现有功能。

如果 Screener 可以快速运行，可以考虑：

```bash
cd tradingagents && python -m screener run --mode FOCUSED --focus-sector semiconductor --tickers 688981.SH
```

验证输出中 `policy_selection_tag` 为 `policy_focus_aligned` 而非 `policy_keyword_fallback`。
