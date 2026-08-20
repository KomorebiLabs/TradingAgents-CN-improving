# Point-in-Time 历史数据审计

> A5 治理阶段 · 仅静态审计和离线测试
>
> 本文审查 Agent 工具收到的 `trade_date` / `curr_date` 是否能够约束底层历史数据。**本阶段没有调用 AkShare、yfinance、Alpha Vantage、任何真实 API 或 LLM。**

## 1. 审计目标

回测和历史日期评测必须满足至少一条可解释的截止规则：

```text
工具输入的 trade_date / curr_date
        ↓
底层数据请求的 end_date / 请求日期
        ↓
返回结果的最终过滤
        ↓
不会出现截止日之后的数据
```

需要区分两种强度：

1. **价格 / 新闻数据截止**：返回记录的日期不晚于目标日期；
2. **真正的 point-in-time**：数据在目标日期已经公开，尤其是财务报表必须满足“公告时间 ≤ trade_date”。

本阶段只能对第一类做离线代码级验证，不能仅凭“报告期 ≤ trade_date”证明第二类成立。

## 2. 状态定义

| 状态 | 含义 |
|---|---|
| `SAFE` | 当前输入和返回过滤形成了明确的截止边界，并有离线测试支撑 |
| `CONDITIONAL` | 有截止参数或过滤逻辑，但依赖调用者、供应商语义或未审计的发布时间 |
| `REALTIME_ONLY` | 当前实现读取最新快照 / 当前数据，不适合历史日期正确性评估 |
| `NOT_AUDITED` | 本阶段没有足够源码证据，不能做安全承诺 |

`SAFE` 只表示“当前代码路径的日期边界可解释”，不表示供应商数据本身没有漂移或错误。

## 3. 工具族审计矩阵

| Agent 工具 | 默认实现路径 | 日期输入 | 当前行为 | 状态 | 后续动作 |
|---|---|---|---|---|---|
| `get_indicators` | `cn_indicators._get_cn_hist_data` → `MarketDataPort.fetch_hist` | `curr_date` | 请求 `end_date=curr_date`；本阶段新增返回结果二次 `Date <= curr_date` 防御 | **`SAFE`** | 保持回归测试 |
| `get_stock_data` | `dataflows/akshare/stock.py:get_akshare_stock_data` | 显式 `start_date` / `end_date` | 底层请求和输出区间由调用者提供，没有独立 `trade_date` 参数 | **`CONDITIONAL`** | 历史调用方必须把 `end_date` 设为信号日 |
| `get_news` | `dataflows/akshare/news.py:get_akshare_news` | `start_date` / `end_date` | 对供应商返回结果按发布时间再次过滤 | **`SAFE`** | 仍需关注供应商发布时间字段质量 |
| 技术 / 行业新闻 | `get_*_sector_news` | `curr_date` + look-back | 股票新闻按起止日期过滤；宏观新闻按目标日期倒推请求 | **`CONDITIONAL`** | 继续审计上游发布时间和时区语义 |
| `get_global_news` / `get_cn_policy_news` | `news.py` → `news_economic_baidu` | `curr_date` + look-back | 请求日期从 `curr_date` 向过去递减，不请求未来日期 | **`CONDITIONAL`** | 供应商发布时间与公告语义仍未独立验证 |
| `get_fundamentals` | `stock.py:get_akshare_fundamentals` | `curr_date` | 调用最新 `stock_individual_info_em` 快照，只在标题中标注 `as of curr_date` | **`REALTIME_ONLY`** | 不用于历史正确性结论，除非引入历史快照 |
| `get_balance_sheet` | `financials.py:get_akshare_balance_sheet` | wrapper 接收 `curr_date` | AkShare 实现读取最新报告表；第三位置实际是 `limit`，不是可用的 as-of 截止 | **`REALTIME_ONLY`** | 需先确认公告日期字段，再设计历史过滤 |
| `get_cashflow` / `get_income_statement` | `financials.py` 对应函数 | wrapper 接收 `curr_date` | 与资产负债表相同，没有公告时点过滤 | **`REALTIME_ONLY`** | 不纳入历史评测输入 |
| `get_insider_transactions` / `get_cn_market_flow` | 路由到当前供应商 | 无 `trade_date` 截止 | 当前工具没有可验证的历史截止参数 | **`REALTIME_ONLY`** | 只能用于实时分析，或补充历史快照接口 |
| `get_cn_earnings_calendar` / IPO / pledge / M&A | `dataflows/akshare/events.py` | look-forward / look-back 或无日期 | 事件窗口语义各不相同，不等同于公告时点审计 | **`CONDITIONAL`** | 按工具逐个补充历史日期契约 |
| yfinance 财务表 | `filter_financials_by_date` | `curr_date` | 按财务期间结束日期过滤 | **`CONDITIONAL`** | 期间结束日不等于公开公告日，不能直接当作 PIT 证据 |
| Alpha Vantage 财务 / 新闻 | legacy fallback | 供应商各自参数 | 本阶段没有对所有 fallback 做统一审计 | **`NOT_AUDITED`** | 单独建立 provider contract 后再纳入 |

## 4. 本阶段实际修复

`tradingagents/dataflows/cn_indicators.py` 原本已经把 `curr_date` 传给 `MarketDataPort.fetch_hist`，但只相信供应商遵守 `end_date`。本阶段在解析 `Date` 后增加第二道边界：

```python
df = df[df["Date"] <= pd.Timestamp(end_date)]
```

这样即使某个供应商忽略请求参数，未来 K 线也不会进入技术指标计算。对应离线回归测试见 [`tests/test_point_in_time.py`](../tests/test_point_in_time.py)。

新闻路径原本已有输出级日期过滤，本阶段补充 fixture 测试，确保截止日之后的新闻不会进入 LLM 可见结果。

## 5. 什么还不能声称

本审计**不能**声称：

- 所有供应商都提供了历史快照；
- 财务报告满足公告时间 `<= trade_date`；
- 最新基本面接口可以安全回放到历史日期；
- 免费数据源不存在修订、回填或接口漂移；
- A5 已经证明了整个 Analyzer 的业务预测正确性。

尤其要注意：

```text
报告期 <= trade_date
```

弱于：

```text
公告时间 <= trade_date
```

前者只说明报表描述的期间没有超过目标日期，后者才接近真实历史可用信息。当前项目没有把二者混为一谈。

## 6. 下一步治理建议

1. 为财务工具找到包含公告时间的历史接口或本地快照；
2. 将 `curr_date` 作为显式、命名的 as-of 参数传到各 provider adapter，而不是复用 `limit` 等位置参数；
3. 为每个 provider 建立不联网的 contract test，再用少量人工核验数据确认发布时间语义；
4. 在 point-in-time 审计通过后，再运行小规模正确性评测；
5. 在多窗口回测和成本敏感性完成前，不把单窗口 `82.86%` 写成策略预测能力。

## 7. 证据来源

- 技术截止实现：[`tradingagents/dataflows/cn_indicators.py`](../tradingagents/dataflows/cn_indicators.py)
- Port 契约：[`tradingagents/ports/market_data.py`](../tradingagents/ports/market_data.py)
- 新闻日期过滤：[`tradingagents/dataflows/akshare/news.py`](../tradingagents/dataflows/akshare/news.py)
- 财务和基本面实现：[`tradingagents/dataflows/akshare/financials.py`](../tradingagents/dataflows/akshare/financials.py)、[`tradingagents/dataflows/akshare/stock.py`](../tradingagents/dataflows/akshare/stock.py)
- 离线测试：[`tests/test_point_in_time.py`](../tests/test_point_in_time.py)
- 后续治理方案：项目交接材料中的 `治理报告-6-残余不足与治理方案.md`（当前分支不包含该历史材料文件）
