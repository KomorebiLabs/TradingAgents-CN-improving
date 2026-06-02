"""
================================================================================
                   ALPHA_VANTAGE_FUNDAMENTALS.PY 详解
                        基本面与财务报表数据获取
================================================================================

【模块定位】
    本文件是 TradingAgents 数据获取层的"基本面数据模块"，专门处理公司
    基本面和三大财务报表（资产负债表、现金流量表、利润表）。

    在项目中的定位：
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                        interface.py (路由层)                            │
    │                              │                                          │
    │        VENDOR_METHODS["get_fundamentals"]["alpha_vantage"]  → 本文件  │
    │        VENDOR_METHODS["get_balance_sheet"]["alpha_vantage"]  → 本文件  │
    │        VENDOR_METHODS["get_cashflow"]["alpha_vantage"]      → 本文件  │
    │        VENDOR_METHODS["get_income_statement"]["alpha_vantage"]→ 本文件 │
    └─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │              alpha_vantage_fundamentals.py (当前文件)                     │
    │                                                                          │
    │  函数列表：                                                              │
    │    1. _filter_reports_by_date()   → 工具函数：防未来信息泄漏            │
    │    2. get_fundamentals()          → 获取公司概览（OVERVIEW API）         │
    │    3. get_balance_sheet()         → 获取资产负债表（BALANCE_SHEET API）  │
    │    4. get_cashflow()              → 获取现金流量表（CASH_FLOW API）      │
    │    5. get_income_statement()      → 获取利润表（INCOME_STATEMENT API）   │
    │                                                                          │
    └─────────────────────────────────────────────────────────────────────────┘

【设计特点】
    本文件是所有 alpha_vantage_*.py 中最薄的模块——只有 56 行。
    因为它的大部分工作都交给 alpha_vantage_common.py 的 _make_api_request() 去做。

    设计哲学：能用一行解决的，绝不多写一行。

【财务报表的基础知识】

    三大财务报表是从三个角度观察公司健康状况：

    ┌─────────────────┬───────────────────────────────────────────────────────┐
    │                 │                                                       │
    │  资产负债表      │  某一时点的"快照"                                    │
    │  (Balance Sheet) │  公司拥有什么（资产）vs 欠了什么（负债）            │
    │                 │  核心公式：资产 = 负债 + 股东权益                    │
    │                 │                                                       │
    ├─────────────────┼───────────────────────────────────────────────────────┤
    │                 │                                                       │
    │  利润表          │  一段时间的"成绩单"                                  │
    │  (Income Stmt) │  收入多少，花了多少费用，赚了多少利润                │
    │                 │  核心公式：净利润 = 收入 - 费用                      │
    │                 │                                                       │
    ├─────────────────┼───────────────────────────────────────────────────────┤
    │                 │                                                       │
    │  现金流量表      │  一段时间的"流水账"                                  │
    │  (Cash Flow)    │  实际收到多少现金，支出了多少现金                    │
    │                 │  核心公式：净现金流 = 经营 + 投资 + 融资现金流       │
    │                 │                                                       │
    └─────────────────┴───────────────────────────────────────────────────────┘

【为什么财务报表需要防"未来信息泄漏"】

    这是整个模块最重要的设计考量，理解它就理解了本文件一半的价值。

    问题：
        上市公司发布财报有时间滞后。例如：
        • Q1 (1-3月) 财报 → 通常 4 月底才发布
        • Q2 (4-6月) 财报 → 通常 7 月底才发布
        • 年报             → 通常 次年 2-4 月才发布

    如果模拟交易日期是 2024-04-15，但 Q1 财报 4 月 30 日才发布，
    交易员不应该"提前知道" Q1 的财务数据。

    解决方案：
        _filter_reports_by_date() 过滤掉 curr_date 之后才结束的财报期间。

================================================================================
"""

# ==============================================================================
# 导入层解析
# ==============================================================================
# 本文件只依赖 alpha_vantage_common.py
# 这体现了"底层工具"和"业务逻辑"分离的设计思想

from .alpha_vantage_common import _make_api_request


# ==============================================================================
# 工具函数 1: _filter_reports_by_date() — 防"未来信息泄漏"
# ==============================================================================

def _filter_reports_by_date(result, curr_date: str):
    """
    【函数功能】
        过滤掉 curr_date 之后才结束的财报期间，防止"未来信息泄漏"。

    【什么是"财报期间结束日"？】
        Alpha Vantage 返回的财务数据中，每个报告都有一个 fiscalDateEnding 字段：

        例如，对于 Q1 2024 的报告：
        • fiscalDateEnding = "2024-03-31"  ← 这是 Q1 结束的日期
        • 实际发布时间：2024-04-30          ← 发布日期可能更晚

        我们用 fiscalDateEnding（而非发布时间）来判断是否应该包含这条数据。
        因为 fiscalDateEnding 代表了这个报告覆盖的时间范围。

    【为什么不基于"发布时间"过滤？】
        因为 Alpha Vantage API 返回的数据中只有 fiscalDateEnding，
        没有"实际发布日期"字段。

    【curr_date 参数为空时】
        不做过滤，直接返回原始数据。
        这样在不需要日期过滤的场景下（如历史回测的最终报告获取）可以正常工作。

    【参数】
        result: Alpha Vantage API 返回的 JSON 字典
                格式：{"annualReports": [...], "quarterlyReports": [...]}
        curr_date: 当前模拟交易日期，格式 "YYYY-MM-DD"

    【返回值】
        过滤后的字典，只包含 curr_date 之前结束的财报期间

    【使用示例】
        场景：curr_date = "2024-04-15"

        原始数据（Alpha Vantage 返回）：
        quarterlyReports = [
            {"fiscalDateEnding": "2024-03-31", "totalRevenue": "100000"},  ← 保留
            {"fiscalDateEnding": "2024-06-30", "totalRevenue": "120000"},  ← 过滤掉
            {"fiscalDateEnding": "2023-12-31", "totalRevenue": "95000"},   ← 保留
        ]

        过滤后结果：
        quarterlyReports = [
            {"fiscalDateEnding": "2024-03-31", "totalRevenue": "100000"},
            {"fiscalDateEnding": "2023-12-31", "totalRevenue": "95000"},
        ]

        解释：
        • "2024-03-31" 在 2024-04-15 之前 → 保留（Q1 已结束）
        • "2024-06-30" 在 2024-04-15 之后 → 过滤（Q2 还未结束）
        • "2023-12-31" 在 2024-04-15 之前 → 保留（去年年报）
    """
    # 【教学】防御性检查：处理边界情况
    # curr_date 为空 → 不过滤
    # result 不是字典 → 不过滤（可能是错误响应）
    if not curr_date or not isinstance(result, dict):
        return result

    # 【教学】遍历两种报告类型：年度和季度
    for key in ("annualReports", "quarterlyReports"):
        if key in result:
            # 【教学】列表推导式过滤
            # 只保留 fiscalDateEnding <= curr_date 的报告
            # 字符串比较（"2024-03-31" <= "2024-04-15"）在日期格式正确时有效
            result[key] = [
                r for r in result[key]
                if r.get("fiscalDateEnding", "") <= curr_date
            ]
    return result


# ==============================================================================
# 函数 1: get_fundamentals() — 获取公司概览
# ==============================================================================

def get_fundamentals(
    ticker: str,
    curr_date: str = None
) -> str:
    """
    【函数功能】
        获取公司的基本信息和财务指标概览。

    【使用的 API】
        Alpha Vantage API: OVERVIEW

    【API 返回的数据类型】
        这是一个"公司信息字典"，包含 50+ 个字段，涵盖：

        ┌─────────────────────────────────────────────────────────────────────┐
        │                        OVERVIEW API 字段分类                          │
        ├─────────────────────┬───────────────────────────────────────────────┤
        │                     │                                               │
        │  【基本信息】         │  Symbol, AssetType, Name, Description,        │
        │                     │  Exchange, Currency, Country, Sector, Industry  │
        │                     │                                               │
        │  【市场数据】         │  MarketCapitalization, BookValue,             │
        │                     │  EBITDA, EPS, PEGRatio, WallStreetTargetPrice │
        │                     │                                               │
        │  【估值指标】         │  PERatio, ForwardPE, PriceToBookRatio       │
        │                     │                                               │
        │  【盈利指标】         │  ProfitMargin, OperatingMargin, ReturnOnEquity│
        │                     │  RevenueTTM, GrossProfitTTM, NetIncomeTTM      │
        │                     │                                               │
        │  【股东数据】         │  DividendYield, AnalystTargetPrice,           │
        │                     │  52WeekHigh, 52WeekLow, 50DayAverage           │
        │                     │                                               │
        │  【交易数据】         │  SharesOutstanding, TrailingAnnualDividendYield│
        │                     │  50DayMovingAverage, 200DayMovingAverage       │
        │                     │                                               │
        └─────────────────────┴───────────────────────────────────────────────┘

    【curr_date 参数的处理】
        注意：Alpha Vantage 的 OVERVIEW API 不支持日期过滤，
        因此 curr_date 参数在本函数中**不起作用**（被忽略）。

        这与 yfinance 版本的 get_fundamentals() 一致：
        两边的 curr_date 参数都被忽略。

        为什么被忽略？因为 OVERVIEW 返回的是"当前快照"数据，
        不是时间序列数据，没有"期"的概念。

    【返回值格式】
        Alpha Vantage 返回的是 JSON 字符串（不是格式化好的文本）。
        格式示例：
        {
            "Symbol": "IBM",
            "Name": "International Business Machines",
            "Sector": "Technology",
            "MarketCapitalization": "160000000000",
            "PERatio": "22.5",
            ...
        }

        这个 JSON 字符串会被 interface.py 传给 LLM，LLM 可以解析 JSON。

    【与 yfinance 版本的区别】
        ┌─────────────────┬─────────────────────────────┬─────────────────────────────┐
        │      维度        │   Alpha Vantage 版本        │     yfinance 版本          │
        ├─────────────────┼─────────────────────────────┼─────────────────────────────┤
        │   返回格式       │   JSON 字符串              │     Markdown 格式          │
        │   字段数量       │   50+ 字段，更完整          │     约 30 个精选字段        │
        │   curr_date     │   被忽略                    │     被忽略                  │
        │   数据实时性     │   实时快照                  │     实时快照                │
        └─────────────────┴─────────────────────────────┴─────────────────────────────┘
    """
    # 【教学】构建 API 参数
    # OVERVIEW API 只需要一个参数：symbol
    # 非常简洁，这是 Alpha Vantage API 设计得好的地方
    params = {
        "symbol": ticker,
    }

    # 【教学】调用 API 并返回
    # 直接返回 _make_api_request() 的结果
    # 不需要额外的处理或格式化
    return _make_api_request("OVERVIEW", params)


# ==============================================================================
# 函数 2: get_balance_sheet() — 获取资产负债表
# ==============================================================================

def get_balance_sheet(
    ticker: str,
    freq: str = "quarterly",
    curr_date: str = None
):
    """
    【函数功能】
        获取公司的资产负债表。

    【使用的 API】
        Alpha Vantage API: BALANCE_SHEET

    【API 返回的数据结构】
        {
            "symbol": "IBM",
            "annualReports": [    ← 年度报告
                {
                    "fiscalDateEnding": "2023-12-31",
                    "totalAssets": "168000000000",
                    "totalCurrentAssets": "52000000000",
                    "cashAndCashEquivalentsAtCarryingValue": "15000000000",
                    "inventory": "2000000000",
                    "totalLiabilities": "110000000000",
                    "totalCurrentLiabilities": "30000000000",
                    "shortTermDebt": "5000000000",
                    "longTermDebt": "40000000000",
                    "shareholderEquity": "58000000000",
                    ...
                }
            ],
            "quarterlyReports": [  ← 季度报告
                { ... },
                { ... }
            ]
        }

    【freq 参数的作用】
        Alpha Vantage API 本身同时返回 annualReports 和 quarterlyReports，
        freq 参数**在本函数中被忽略**。

        这是设计上的简化：
        • 不需要根据 freq 参数决定调用哪个 API
        • API 返回所有数据，本地过滤由调用者决定如何使用

        返回值包含两种报告，调用者（如 interface.py 或 LLM）
        可以自行决定使用哪种。

    【curr_date 参数的作用】
        用于 _filter_reports_by_date() 过滤
        只返回 curr_date 之前结束的财报期间

    【资产负债表的阅读要点】
        ┌─────────────────────────────────────────────────────────────────────┐
        │  关键指标                        │  解读                            │
        ├─────────────────────────────────────────────────────────────────────┤
        │  totalAssets                     │  总资产越大，通常实力越强         │
        │  totalLiabilities                │  总负债，过高则风险大            │
        │  shareholderEquity               │  股东权益 = 资产 - 负债         │
        │  totalCurrentAssets              │  流动资产（1年内变现）           │
        │  totalCurrentLiabilities         │  流动负债（1年内到期）           │
        │  longTermDebt                    │  长期负债，影响财务稳健性        │
        └─────────────────────────────────────────────────────────────────────┘
    """
    # 【教学】调用 BALANCE_SHEET API
    result = _make_api_request("BALANCE_SHEET", {"symbol": ticker})

    # 【教学】应用日期过滤，防止未来信息泄漏
    return _filter_reports_by_date(result, curr_date)


# ==============================================================================
# 函数 3: get_cashflow() — 获取现金流量表
# ==============================================================================

def get_cashflow(
    ticker: str,
    freq: str = "quarterly",
    curr_date: str = None
):
    """
    【函数功能】
        获取公司的现金流量表。

    【使用的 API】
        Alpha Vantage API: CASH_FLOW

    【API 返回的数据结构】
        {
            "symbol": "IBM",
            "annualReports": [...],
            "quarterlyReports": [...]
        }

        每个报告包含的典型字段：
        ┌─────────────────────────────────────────────────────────────────────┐
        │  经营活动现金流 (Operating)                                         │
        │    operatingCashflow        ← 主营业务产生的现金                     │
        │    paymentsForOperatingActivities ← 运营支出                         │
        │    netIncome               ← 净利润（会计）                         │
        │    depreciationAndAmortization ← 折旧摊销（非现金费用）             │
        ├─────────────────────────────────────────────────────────────────────┤
        │  投资活动现金流 (Investing)                                         │
        │    capitalExpenditures      ← 资本支出（购买设备等）                 │
        │    investments             ← 投资活动                              │
        ├─────────────────────────────────────────────────────────────────────┤
        │  融资活动现金流 (Financing)                                         │
        │    dividendPayout           ← 支付股息                              │
        │    stockRepurchase         ← 股票回购                               │
        │    debtRepayment           ← 偿还债务                              │
        └─────────────────────────────────────────────────────────────────────┘

    【freq 参数】
        与 get_balance_sheet() 一样，被忽略。
        API 同时返回年度和季度数据。

    【curr_date 参数】
        用于 _filter_reports_by_date() 过滤。

    【现金流量表的核心价值】
        ┌─────────────────────────────────────────────────────────────────────┐
        │  问题：利润表说公司赚了钱，但为什么银行账户里没有钱？                  │
        │                                                                       │
        │  原因：利润表用"权责发生制"（应收未收也算收入）                       │
        │                                                                       │
        │  答案：看现金流量表！它用"收付实现制"（真金白银才算）                  │
        │                                                                       │
        │  案例：公司卖了 100 万商品，客户 3 个月后才付款                         │
        │    • 利润表：+100 万收入 ✓                                          │
        │    • 现金流量表：0（还没收到钱）×                                  │
        └─────────────────────────────────────────────────────────────────────┘

    【分析要点】
        ┌─────────────────────────────────────────────────────────────────────┐
        │  经营活动现金流 > 0    → 公司主营业务赚钱（好事）                   │
        │  经营活动现金流 < 0    → 主业亏钱，靠融资维持（危险）               │
        │  资本支出过大          → 可能在扩张（要结合战略看）                  │
        │  分红 + 回购          → 管理层认为股价被低估                        │
        └─────────────────────────────────────────────────────────────────────┘
    """
    # 【教学】调用 CASH_FLOW API
    result = _make_api_request("CASH_FLOW", {"symbol": ticker})

    # 【教学】应用日期过滤
    return _filter_reports_by_date(result, curr_date)


# ==============================================================================
# 函数 4: get_income_statement() — 获取利润表
# ==============================================================================

def get_income_statement(
    ticker: str,
    freq: str = "quarterly",
    curr_date: str = None
):
    """
    【函数功能】
        获取公司的利润表（损益表）。

    【使用的 API】
        Alpha Vantage API: INCOME_STATEMENT

    【API 返回的数据结构】
        {
            "symbol": "IBM",
            "annualReports": [...],
            "quarterlyReports": [...]
        }

        每个报告包含的典型字段：
        ┌─────────────────────────────────────────────────────────────────────┐
        │  收入层                                                            │
        │    totalRevenue              ← 总收入                             │
        │    costOfRevenue             ← 营业成本                           │
        │    grossProfit               ← 毛利润 = 收入 - 成本                │
        ├─────────────────────────────────────────────────────────────────────┤
        │  费用层                                                            │
        │    researchAndDevelopment    ← 研发费用                           │
        │    sellingGeneralAndAdmin    ← 销售/管理费用                      │
        │    operatingIncome           ← 营业利润 = 毛利润 - 费用             │
        ├─────────────────────────────────────────────────────────────────────┤
        │  利润层                                                            │
        │    interestExpense            ← 利息支出                           │
        │    netIncome                 ← 净利润 = 最终利润                    │
        └─────────────────────────────────────────────────────────────────────┘

    【freq 参数】
        与前两个函数一样，被忽略。

    【curr_date 参数】
        用于 _filter_reports_by_date() 过滤。

    【利润表的核心公式】
        ┌─────────────────────────────────────────────────────────────────────┐
        │                                                                       │
        │    总收入 (Revenue)                                                 │
        │         -                                                            │
        │    营业成本 (Cost of Revenue)                                        │
        │         =                                                            │
        │    毛利润 (Gross Profit)                                              │
        │         -                                                            │
        │    运营费用 (Operating Expenses)                                      │
        │         =                                                            │
        │    营业利润 (Operating Income / EBIT)                                │
        │         -                                                            │
        │    利息和税                                                         │
        │         =                                                            │
        │    净利润 (Net Income)                                                │
        │                                                                       │
        └─────────────────────────────────────────────────────────────────────┘

    【关键财务比率】
        ┌─────────────────────────────────────────────────────────────────────┐
        │  毛利率      = 毛利润 / 收入                                         │
        │  净利率      = 净利润 / 收入                                         │
        │  营业利润率  = 营业利润 / 收入                                        │
        │                                                                       │
        │  毛利率 > 40% → 公司有定价权（护城河）                               │
        │  净利率 > 15% → 盈利能力强                                          │
        │  营业利润率为负 → 公司在烧钱                                          │
        └─────────────────────────────────────────────────────────────────────┘
    """
    # 【教学】调用 INCOME_STATEMENT API
    result = _make_api_request("INCOME_STATEMENT", {"symbol": ticker})

    # 【教学】应用日期过滤
    return _filter_reports_by_date(result, curr_date)
