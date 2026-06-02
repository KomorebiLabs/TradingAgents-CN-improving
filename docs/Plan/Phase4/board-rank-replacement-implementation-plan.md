# PolicyStrategy 概念地位评分重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `board_rank` 从"今日板块涨跌排名"改为基于沪深300/中证500/创业板指成分股的静态概念地位评分。

**Architecture:** 在 `PolicyStrategy.run()` 启动时一次性加载三个指数成分股到缓存，后续评分全为 O(1) 集合查找。评分公式从"今日涨幅排名"改为"指数成分层级+THS成员确认"，`board_rank_bucket` 标签体系迁移到 `concept_weight_bucket`。

**Tech Stack:** Python 3, pandas, akshare, 现有 `data_access.fetch_index_constituents()` 接口

---

## 文件变更总览

| 文件 | 操作 |
|---|---|
| `tradingagents/screener/strategies/policy.py` | 修改：新增 index 缓存 + 评分逻辑重构 |
| `tests/test_screener_strategy_policy.py` | 修改：更新测试断言以适配新标签体系 |
| `tradingagents/screener/merger.py` | 无需修改（`board_rank_*` 不在 POLICY_SELECTION_TAGS 中） |

---

## Task 1: 预备工作 — 更新 PolicyStrategy 的测试 fixture，增加 index 模拟

**Files:**
- Modify: `tests/test_screener_strategy_policy.py:6-57`

**目的:** `PolicyAccessReady` 和 `TailMemberAccess` 需要提供 `fetch_index_constituents` 方法的模拟，因为重构后的代码在启动时会调用它。

---

- [ ] **Step 1: 在 `PolicyAccessReady` 中添加 `fetch_index_constituents` 模拟方法**

在 `PolicyAccessReady.fetch_policy_news_baidu` 后添加：

```python
def fetch_index_constituents(self, index_code):
    import pandas as pd

    if index_code == "000300":
        # 000300 = 沪深300：000001 和 000300 都在其中
        return pd.DataFrame({"成分券代码": ["000001", "000300"], "成分券名称": ["平安银行", "CSI 300 Proxy"]})
    if index_code == "000905":
        # 000905 = 中证500：无成员
        return pd.DataFrame({"成分券代码": [], "成分券名称": []})
    if index_code == "399006":
        # 399006 = 创业板指：无成员
        return pd.DataFrame({"成分券代码": [], "成分券名称": []})
    return pd.DataFrame({"成分券代码": [], "成分券名称": []})
```

验证测试通过（回归）：
```bash
cd "d:\cursor\HarmonyOS\Github project\TradingAgents-main"
python -m pytest tests/test_screener_strategy_policy.py -v
```
预期：所有现有测试 PASS

---

- [ ] **Step 2: 在 `PolicyAccessDegraded` 中也添加 `fetch_index_constituents` 模拟**

```python
class PolicyAccessDegraded(PolicyAccessReady):
    def validate_interface_assumptions(self, trade_date=None):
        payload = super().validate_interface_assumptions(trade_date=trade_date)
        payload["concept_list_verified"] = False
        payload["strategy_capabilities"]["policy"]["status_hint"] = "degraded"
        return payload

    # Inherit fetch_index_constituents from PolicyAccessReady
```

验证：重新运行 Step 1 的测试，确保所有测试仍然 PASS。

---

## Task 2: 在 PolicyStrategy 中新增 index 成分股缓存加载

**Files:**
- Modify: `tradingagents/screener/strategies/policy.py:37-80`

**目的:** 在 `run()` 方法开头一次性加载沪深300/中证500/创业板指成分股，存为实例变量缓存。

---

- [ ] **Step 1: 在 `run()` 方法中 `capability` 获取之后，添加 index 缓存加载逻辑**

找到 `policy.py` 第 66-79 行（`concept_fallback` 赋值之后，`concept_df` 赋值之前），插入以下代码：

```python
        # Phase4: Load index constituents cache for concept_weight scoring
        # One-time load at startup (~1-2s), O(1) lookup per stock thereafter
        self._hs300_members: set = set()
        self._csi500_members: set = set()
        self._cy50_members: set = set()

        for _index_code, _cache_attr, _name_zh in [
            ("000300", "_hs300_members", "沪深300"),
            ("000905", "_csi500_members", "中证500"),
            ("399006", "_cy50_members", "创业板指"),
        ]:
            try:
                df = self.data_access.fetch_index_constituents(_index_code)
                if df is not None and not getattr(df, "empty", True):
                    cols = list(df.columns)
                    code_col = next((c for c in cols if "成分券代码" in str(c) or str(c).lower() in ("code", "symbol")), None)
                    if code_col:
                        codes = df[code_col].astype(str).str.zfill(6).tolist()
                        setattr(self, _cache_attr, set(codes))
                        print(f"[SCREENER] Stage B Policy: loaded {len(codes)} stocks for {_name_zh}")
            except Exception:
                pass
```

验证：
```bash
python -c "
import pandas as pd
class MockDA:
    def validate_interface_assumptions(self, **kw):
        return {'concept_list_verified': True, 'strategy_capabilities': {'policy': {'status_hint': 'ready', 'primary_dependencies': {}}}, 'warnings': [], 'freshness': []}
    def fetch_concept_boards(self):
        return pd.DataFrame({'name': ['人工智能'], 'code': ['A1']})
    def fetch_policy_news_baidu(self, *a, **kw):
        return pd.DataFrame({'事件': ['test']})
    def fetch_concept_constituents(self, n):
        return pd.DataFrame({'代码': ['000001'], '名称': ['A'], '涨跌幅': [1.0], '成交额': [1e8], '换手率': [1.0]})
    def fetch_index_constituents(self, code):
        import pandas as pd
        if code == '000300':
            return pd.DataFrame({'成分券代码': ['000001', '000300'], '成分券名称': ['A', 'B']})
        return pd.DataFrame({'成分券代码': [], '成分券名称': []})

from tradingagents.screener.strategies.policy import PolicyStrategy
s = PolicyStrategy(MockDA(), {})
s.run(['000001'], '2026-05-07')
print('_hs300_members:', s._hs300_members)
print('_csi500_members:', s._csi500_members)
print('_cy50_members:', s._cy50_members)
"
```
预期输出包含 "loaded 2 stocks for 沪深300"，`_hs300_members` 包含 `000001` 和 `000300`。

---

## Task 3: 新增 `_get_index_tier()` 静态方法

**Files:**
- Modify: `tradingagents/screener/strategies/policy.py:705-726`

**目的:** 给定股票代码，返回其所在的指数层级（沪深300=28, 中证500/创业板50=18, 无成分=0）。

---

- [ ] **Step 1: 在 `_build_board_rank_bucket` 方法之后添加 `_get_index_tier` 静态方法**

在 `_build_board_rank_bucket` 方法（大约第 717 行）之后添加：

```python
    @staticmethod
    def _get_index_tier(raw_code: str, hs300: set, csi500: set, cy50: set) -> int:
        """Return the index tier score for a stock based on index constituent membership.

        Scores:
            HS300 member  -> 28  (core blue chip, most representative A-share)
            CSI500 member -> 18  (quality mid-cap, strong growth)
            CY50 member   -> 18  (tech growth leader)
            None          ->  0  (not in any tracked index)
        """
        code = raw_code.zfill(6)
        if code in hs300:
            return 28
        if code in csi500 or code in cy50:
            return 18
        return 0
```

验证（单元测试）：
```bash
python -c "
from tradingagents.screener.strategies.policy import PolicyStrategy
hs300 = {'000001', '000002', '000300'}
csi500 = {'000905', '000001'}
cy50 = {'399006'}

# Test HS300 member
assert PolicyStrategy._get_index_tier('000001', hs300, csi500, cy50) == 28, '000001 is HS300'
assert PolicyStrategy._get_index_tier('000300', hs300, csi500, cy50) == 28, '000300 is HS300'

# Test CSI500 member (not in HS300)
assert PolicyStrategy._get_index_tier('000905', hs300, csi500, cy50) == 18, '000905 is CSI500'

# Test CY50 member
assert PolicyStrategy._get_index_tier('399006', hs300, csi500, cy50) == 18, '399006 is CY50'

# Test non-member
assert PolicyStrategy._get_index_tier('999999', hs300, csi500, cy50) == 0, '999999 not in any index'

# Test zero-padded
assert PolicyStrategy._get_index_tier('1', hs300, csi500, cy50) == 28, '1 -> 000001 is HS300'

print('All _get_index_tier tests PASS')
"
```

---

## Task 4: 重构 `_compute_top_selection_score` 替换 rank_position 逻辑

**Files:**
- Modify: `tradingagents/screener/strategies/policy.py:453-560`

**目的:** `top_selection_score` 的计算从"今日涨跌排名"改为"指数成分层级 + THS成员确认"。

---

- [ ] **Step 1: 找到 `_compute_top_selection_score` 方法并重构**

找到 `_compute_top_selection_score` 方法（大约第 453 行，方法签名 `def _compute_top_selection_score(`），用以下新实现替换整个方法体：

```python
    def _compute_top_selection_score(
        self,
        member_metrics: Dict[str, Any],
        concept_profiles: Dict[str, Any],
        concept_name: str,
        raw_code: str,
    ) -> float:
        """Compute the concept-selection score using static index membership instead of daily change rank.

        New formula (Phase4):
            score = 55.0
                    + index_tier_score   (HS300=28, CSI500/CY50=18, none=0)
                    + concept_membership  (+12 if is_member else +0)
                    + concept_breadth bonus (up to +10)
        """
        profile = concept_profiles.get(concept_name, {})

        index_tier = self._get_index_tier(
            raw_code,
            self._hs300_members,
            self._csi500_members,
            self._cy50_members,
        )
        is_member = member_metrics.get("is_member", False)
        concept_membership = 12.0 if is_member else 0.0

        score = 55.0 + index_tier + concept_membership
        score += min(10.0, profile.get("concept_breadth_score", 0.0) * 0.12)

        return round(min(100.0, max(20.0, score)), 2)
```

验证：运行 PolicyStrategy 完整测试（Task 1 的回归测试应仍然 PASS，因为 mock 数据中 `000001` 属于沪深300，逻辑一致）。

---

## Task 5: 新增 `_build_concept_weight_bucket` 替换 `_build_board_rank_bucket`

**Files:**
- Modify: `tradingagents/screener/strategies/policy.py:717-726`

**目的:** `board_rank_bucket` 标签体系迁移到 `concept_weight_bucket`，语义从"今日涨跌排名"变为"概念地位层级"。

---

- [ ] **Step 1: 替换 `_build_board_rank_bucket` 方法体，保留方法名不变**

找到 `_build_board_rank_bucket` 方法（大约第 717 行），用以下新实现替换：

```python
    @staticmethod
    def _build_board_rank_bucket(member_metrics: Dict[str, Any]) -> str:
        """Build the concept-weight bucket label (renamed from board_rank_bucket, Phase4).

        Labels:
            concept_weight_core       -> HS300 member + THS member (板块核心资产)
            concept_weight_quality    -> CSI500/CY50 member + THS member (优质标的)
            concept_weight_secondary  -> THS member only, no index membership (概念成员)
            concept_weight_unconfirmed-> Not in THS constituents (未确认)
        """
        hs300_code = member_metrics.get("_hs300_tier", 0)
        is_member = member_metrics.get("is_member", False)

        if hs300_code > 0 and is_member:
            return "concept_weight_core"
        if hs300_code == 0 and is_member:
            return "concept_weight_secondary"
        return "concept_weight_unconfirmed"
```

**注意:** `member_metrics` 字典中需要额外放入 `_hs300_tier` 字段。这个字段在 `_compute_member_metrics` 中注入。需要在 Task 6 中修改。

---

- [ ] **Step 2: 更新 `_compute_member_metrics` 注入 `_hs300_tier`**

找到 `_compute_member_metrics` 方法（大约第 510 行），在该方法返回 `empty` 或 `matched` 字典之前，添加：

```python
        # Phase4: inject index tier into member_metrics for bucket building
        empty["_hs300_tier"] = 0
        if matched is not None:
            matched["_hs300_tier"] = matched.pop("_hs300_tier", 0)
```

等等——这个方法本身不访问 `self._hs300_members`。正确的做法是在 `run()` 中预先把 `_hs300_tier` 注入到 `matched` 字典。找到调用 `_compute_member_metrics` 的地方（大约在 `run()` 第 162 行附近），在调用后立即注入。

具体修改：找到 `run()` 中调用 `_compute_member_metrics` 的那一行（应该在 `member_metrics = self._compute_member_metrics(...)` 之后），在该行之后插入：

```python
        # Phase4: attach index tier to member_metrics for concept_weight bucket
        member_metrics["_hs300_tier"] = self._get_index_tier(
            raw_code,
            self._hs300_members,
            self._csi500_members,
            self._cy50_members,
        )
```

验证：
```bash
python -m pytest tests/test_screener_strategy_policy.py::ScreenerPolicyStrategyTests::test_policy_strategy_ready_when_concept_chain_is_verified -v
```
预期：测试 PASS（因为 mock 中 `000001` 在沪深300，`is_member=True`，应得 `concept_weight_core`）

---

## Task 6: 更新 `SignalCard` 构建中的标签注入点

**Files:**
- Modify: `tradingagents/screener/strategies/policy.py:160-210`

**目的:** 确保 `concept_tags` 列表中不再包含旧的 `board_rank_*` 标签，使用新的 `concept_weight_*` 标签。

---

- [ ] **Step 1: 更新 `concept_tags` 的构建逻辑**

找到大约第 256 行附近：
```python
concept_tags=[mapped_concept, stock_selection_tag, board_rank_bucket],
```
改为：
```python
concept_tags=[mapped_concept, stock_selection_tag],
```

同时在 `run()` 方法开头附近找到 `board_rank_bucket = self._build_board_rank_bucket(member_metrics)` 的调用位置（约第 166 行），确认这个变量仍然被传给 `trigger_reason` 和 `risk_flags`，但不再放入 `concept_tags`。

验证：检查 `concept_tags` 中不包含 `board_rank_` 前缀的标签。

---

## Task 7: 更新 `trigger_reason` 逻辑

**Files:**
- Modify: `tradingagents/screener/strategies/policy.py:706-714`

---

- [ ] **Step 1: 更新 `trigger_reason` 中的 board_rank_bucket 引用**

找到 `_build_trigger_reason` 方法（约第 706 行），当前代码为：

```python
@staticmethod
def _build_trigger_reason(keyword_mode: bool, stock_selection_tag: str, board_rank_bucket: str) -> str:
    if stock_selection_tag == "policy_top_stock":
        return "policy_concept_top_pick"
    if board_rank_bucket == "board_rank_top10":
        return "policy_concept_core_member"
    if keyword_mode:
        return "policy_event_keyword_fallback"
    return "policy_event_concept_map"
```

替换为：

```python
@staticmethod
def _build_trigger_reason(keyword_mode: bool, stock_selection_tag: str, board_rank_bucket: str) -> str:
    if stock_selection_tag == "policy_top_stock":
        return "policy_concept_top_pick"
    if board_rank_bucket in ("concept_weight_core", "concept_weight_quality"):
        return "policy_concept_core_weight"
    if keyword_mode:
        return "policy_event_keyword_fallback"
    return "policy_event_concept_map"
```

同时，调用 `_build_trigger_reason` 的地方（约第 262 行）传递的 `board_rank_bucket` 参数值需要对应更新。

---

## Task 8: 更新 `risk_flags` 逻辑

**Files:**
- Modify: `tradingagents/screener/strategies/policy.py:766-792`

---

- [ ] **Step 1: 更新 `_build_risk_flags` 中的 board_rank 相关 flag**

找到 `_build_risk_flags` 方法中约第 784-787 行：

```python
if board_rank_bucket == "board_rank_member_tail":
    flags.append("board_tail_member")
if board_rank_bucket == "board_rank_unconfirmed":
    flags.append("board_rank_unconfirmed")
```

替换为：

```python
if board_rank_bucket == "concept_weight_secondary":
    flags.append("concept_weight_secondary")
if board_rank_bucket == "concept_weight_unconfirmed":
    flags.append("concept_weight_unconfirmed")
```

同时在方法参数中确认 `board_rank_bucket` 参数仍然保留（用于传递新标签值）。

---

## Task 9: 更新测试断言以适配新标签体系

**Files:**
- Modify: `tests/test_screener_strategy_policy.py`

---

- [ ] **Step 1: 更新 `test_policy_strategy_ready_when_concept_chain_is_verified` 中的断言**

找到第 89-90 行：
```python
self.assertEqual(card.signal_breakdown[0].raw_metrics["board_rank_bucket"], "board_rank_top3")
self.assertIn("board_rank_top3", card.concept_tags)
```

替换为（因为 `000001` 在 mock 的沪深300 中，`is_member=True`）：
```python
self.assertEqual(card.signal_breakdown[0].raw_metrics["board_rank_bucket"], "concept_weight_core")
self.assertIn("concept_weight_core", card.concept_tags)
```

找到第 78 行：
```python
self.assertIn("policy_top_stock", card.concept_tags)
```
保留不变（`policy_top_stock` 来自 `stock_selection_tag`，不受影响）。

找到第 85 行：
```python
self.assertTrue(card.signal_breakdown[0].raw_metrics["top_tier_hit"])
```
改为：
```python
self.assertTrue(card.signal_breakdown[0].raw_metrics["is_concept_member"])
```

找到第 79 行：
```python
self.assertGreater(card.signal_breakdown[0].raw_metrics["stock_strength_score"], 70)
```
改为：
```python
self.assertGreater(card.signal_breakdown[0].raw_metrics["stock_strength_score"], 50)
```
（因为去掉了 rank_position 的 +28 分数，分数会降低）

---

- [ ] **Step 2: 更新 `test_policy_strategy_marks_tail_member_when_not_top_tier`**

找到第 143 行：
```python
self.assertEqual(card.signal_breakdown[0].raw_metrics["board_rank_bucket"], "board_rank_top10")
```

替换为（`000300` 在 mock 沪深300，`is_member=True` → `concept_weight_core`）：
```python
self.assertEqual(card.signal_breakdown[0].raw_metrics["board_rank_bucket"], "concept_weight_core")
```

同时移除第 144 行的 `self.assertIn("non_top_concept_member", card.risk_flags)`（因为现在是 `concept_weight_core` 不是 `board_rank_member_tail`）。

---

- [ ] **Step 3: 运行所有测试验证**

```bash
cd "d:\cursor\HarmonyOS\Github project\TradingAgents-main"
python -m pytest tests/test_screener_strategy_policy.py -v
```

预期：所有测试 PASS。

---

## Task 10: 端到端验证

---

- [ ] **Step 1: 运行完整的 policy 测试套件**

```bash
python -m pytest tests/test_screener_strategy_policy.py tests/test_screener_merger.py -v
```

预期：全部 PASS。

- [ ] **Step 2: 语法验证**

```bash
python -m py_compile tradingagents/screener/strategies/policy.py
```
预期：无错误。

---

## 实现顺序

1. Task 1（测试 fixture）→ 2. Task 2（缓存加载）→ 3. Task 3（`_get_index_tier`）→ 4. Task 4（`_compute_top_selection_score`）→ 5. Task 5（`_build_board_rank_bucket` + `_hs300_tier`注入）→ 6. Task 6（concept_tags）→ 7. Task 7（trigger_reason）→ 8. Task 8（risk_flags）→ 9. Task 9（测试更新）→ 10. Task 10（端到端验证）

每个 Task 完成后运行回归测试（`pytest tests/test_screener_strategy_policy.py -v`），确保不破坏已有功能。
