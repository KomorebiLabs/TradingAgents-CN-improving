# PolicyStrategy 概念地位评分重构设计

**日期**: 2026-06-02
**状态**: 设计完成，待评审
**负责人**: TradingAgents Team

---

## 1. 背景与问题

### 1.1 当前 `board_rank` 的根本缺陷

当前 `board_rank_bucket` 依赖**今日板块涨跌排名**（THS HTML 爬虫获取的当日涨幅前10），存在三个致命问题：

| 缺陷 | 表现 | 投资意义 |
|---|---|---|
| **日间噪声** | 一只优质核心资产今天被大盘拖累排第15名，明天反弹到第3名 | 无参考价值的日内波动 |
| **数据盲区** | THS 只展示当日涨幅前10，大量优质资产不在列表中 | 大量优质股被标记为 `unconfirmed` |
| **概念错位** | 按涨幅排序 ≠ 按重要性排序，中石油涨幅小但才是"能源"板块核心 | 信号方向错误 |

根因：**用动态的短期动量数据来衡量静态的概念地位**，两者根本不匹配。

### 1.2 PolicyStrategy 的数据利用现状

PolicyStrategy 当前只用了"板块成分股"数据，但系统中已有但未被利用的更好的数据源：

| 数据源 | 被使用 | 代表什么 |
|---|---|---|
| 板块成分股（THS爬虫） | ✅ PolicyStrategy | 概念映射 |
| 龙虎榜当日明细 | ❌ (被SmartMoney用) | 机构席位动向 |
| 龙虎榜5日统计 | ❌ (被SmartMoney用) | 机构持续关注 |
| 北向资金 | ❌ (被SmartMoney用) | 外资动向 |
| PE/PB估值 | ❌ | 估值质量 |
| **指数成分股** | ❌ | 是否为核心资产 |

设计决策：**PolicyStrategy 只做概念映射，不引入机构信号**。机构信号（龙虎榜/北向）属于 SmartMoney 的职责。两者互补不重叠。

---

## 2. 设计目标

将 `board_rank` 从"今日板块涨跌排名"改为**静态概念地位评估**：

> **这只股票在它所在的板块中，是不是核心资产？**

---

## 3. 新方案：指数成分层级判断

### 3.1 数据源

使用已有的 AkShare 接口在 `PolicyStrategy.run()` 启动时一次性加载三个指数成分股：

| 指数代码 | 指数名称 | 含义 |
|---|---|---|
| `000300` | 沪深300 | A股最具代表性的大盘蓝筹，核心资产 |
| `000905` | 中证500 | 中盘优质企业，成长性强 |
| `399006` | 创业板指 | 科创成长龙头 |

接口已存在于 `data_access.py`：`fetch_index_constituents(symbol="000300")`

### 3.2 缓存策略

- 在 `PolicyStrategy.run()` 开始时一次性加载（约1-2秒）
- 存为 `self._index_constituents_cache: Dict[str, Set[str]]`
- 后续所有股票评分均为 O(1) 集合查找
- 缓存只存活于本次 run，次日重新加载（指数成分每半年调整一次，足够用）

### 3.3 评分公式

```
concept_weight_score = index_tier_score + concept_membership_score
```

**index_tier_score**（指数成分层级）：

| 状态 | 加分 |
|---|---|
| 沪深300成员 | +28 |
| 中证500成员 | +18 |
| 创业板指成员（非沪深300） | +18 |
| 不在任何指数中 | +0 |

**concept_membership_score**（THS成分确认）：

| 状态 | 加分 |
|---|---|
| 在THS板块成分列表中（`is_member=True`） | +12 |
| 不在THS板块成分列表中（`is_member=False`） | +0 |

**总分范围**：0 ~ 40 分（作为 Policy 总分 100 分中的一个子维度）

### 3.4 新概念地位标签

将 `board_rank_bucket` 替换为 `concept_weight_bucket`：

| 条件 | 标签 | 含义 |
|---|---|---|
| 沪深300成员 + THS成员 | `concept_weight_core` | 板块核心资产 |
| 中证500/创业板50成员 + THS成员 | `concept_weight_quality` | 优质标的 |
| 只在THS列表中（非指数成分） | `concept_weight_secondary` | 概念成员 |
| 不在任何列表中 | `concept_weight_unconfirmed` | 未确认 |

### 3.5 对 Policy 总分的影响

PolicyStrategy 当前总分公式（100分制）：

```
score = 0.22 * concept_heat + 0.22 * stock_strength_score + 0.20 * concept_conviction_score
      + 0.20 * cross_hit_score + 0.16 * top_selection_score
```

其中 `top_selection_score`（概念选择分）原本使用 board_rank：

```python
# 原代码（policy.py line 545-560）
top_selection_score = ...
if rank_position == 1: score += 28.0
elif rank_position <= 3: score += 20.0
elif rank_position <= 5: score += 12.0
```

新方案：`_compute_top_selection_score` 改为读 index_tier_score 和 is_member：

```python
# 新逻辑
def _compute_top_selection_score(member_metrics, concept_profiles, concept_name, raw_code):
    profile = concept_profiles.get(concept_name, {})
    index_tier = _get_index_tier(raw_code)  # hs300=28, csi500=18, cy50=18, none=0
    is_member = member_metrics.get("is_member", False)
    concept_membership = 12 if is_member else 0
    score = 55.0 + index_tier + concept_membership
    score += min(10.0, profile.get("concept_breadth_score", 0.0) * 0.12)
    return round(min(100.0, max(20.0, score)), 2)
```

---

## 4. 实现计划

### 4.1 文件修改清单

| 文件 | 修改内容 |
|---|---|
| `tradingagents/screener/strategies/policy.py` | 新增 index 缓存加载、`_get_index_tier()`、`_compute_top_selection_score()` 重构、`_build_board_rank_bucket()` → `_build_concept_weight_bucket()` |
| `tradingagents/screener/config.py` | 新增 `concept_weight` 配置节（可选，用于未来参数化） |

### 4.2 实现步骤

1. 在 `PolicyStrategy.__init__` 或 `run()` 开头加载三个指数成分股到缓存
2. 新增 `_get_index_tier(raw_code) -> int` 静态方法
3. 重构 `_compute_top_selection_score` 替换 rank_position 逻辑
4. 新增 `_build_concept_weight_bucket(member_metrics)` 替换 `_build_board_rank_bucket`
5. 更新 `SignalCard.concept_tags` 中的 `board_rank_*` → `concept_weight_*`
6. 更新 `risk_flags` 中的 `board_rank_*` → `concept_weight_*`
7. 更新 `trigger_reason` 逻辑

### 4.3 向后兼容性

- `SignalCard` 的 `concept_tags` 字段中不再包含 `board_rank_*` 标签
- merger 和报告层需要适配新的标签名称
- 现有日志中的 `board_rank` 相关打印需要同步更新

---

## 5. 预期效果

### 5.1 修复的问题

| 之前 | 之后 |
|---|---|
| 万科A不在AI PC涨幅前10 → `board_rank_unconfirmed` | 万科A是沪深300成分 → `concept_weight_core` |
| 一只垃圾股今天涨幅第一 → `board_rank_top3` | 一只垃圾股不在指数中 → `concept_weight_unconfirmed` |
| 优质股今天调整 → `board_rank_unconfirmed` | 优质股是沪深300 → `concept_weight_core`（稳定） |

### 5.2 评分变化预期

- **优质核心资产**（沪深300+概念成员）：`top_selection_score` 从 ~50-62 提升到 ~85-95
- **优质成长股**（中证500/创业板50+概念成员）：从 ~50-62 提升到 ~75-85
- **纯概念炒作**（不在指数+概念成员）：保持在 ~55-65
- **概念未确认**（不在指数+非成员）：保持在 ~35-50

---

## 6. 测试验证

1. **单元测试**：验证 `_get_index_tier()` 对沪深300/中证500/创业板/无成分股票返回正确分数
2. **集成测试**：跑一次 MVP，观察 `concept_weight_core` 和 `concept_weight_quality` 标签是否出现
3. **回归测试**：确认原有的 RiskFlags 和 TriggerReason 逻辑正确

---

## 7. 风险与限制

| 风险 | 缓解 |
|---|---|
| 指数成分股接口超时导致缓存为空 | 降级：缓存为空时退回 `concept_weight_unconfirmed`，不阻塞运行 |
| 指数成分每半年调整一次 | 缓存只存活于本次 run，次日自动更新 |
| ST股票在指数中 | 不影响评分，只影响最终 merger 的过滤 |

---

## 8. 架构自检

1. **边界清晰**：`PolicyStrategy` 只负责"这只股票在概念中的静态地位"，不侵入机构信号领域
2. **单一职责**：`SmartMoneyStrategy` 继续负责机构信号，两者互补
3. **降级友好**：任何数据获取失败都能降级到 `unconfirmed`，不崩溃
4. **YAGNI**：没有引入新的外部 API，没有引入市值/基本面数据，保持最小改动
