# Screener Trace-back

> **用途**: 给项目维护者看的开发追溯文档
> **目标**: 不是告诉你“下一步做什么”，而是告诉你“我为什么这样做、先后顺序为什么这样排、代码是怎么被一点点串起来的”
> **时间范围**: 本轮 Screener 从设计重写到策略真实化的整个实现过程

---

## 1. 先说结论

这轮 Screener 开发不是“直接写一个策略文件”那么简单。

真正的开发路径是：

1. 先修文档和基线
2. 再修数据源现实
3. 再修接口契约
4. 再搭稳定骨架
5. 再补策略闭环
6. 最后才开始真实化策略逻辑

如果顺序反过来，比如一开始就猛写 `technical.py`，后面一定返工，因为：

- 数据源主次关系当时还不稳定
- `policy/smart_money` 的 ready/degraded 语义还没统一
- merger/report/engine 还不具备承接真实策略结果的能力

所以这轮开发本质上是在做：

`把一个“概念上的 Screener”改造成“可落地、可迭代、可追溯的工程模块”`

---

## 2. 为什么先改文档

你一开始给我的不是一个完全可开工的实现规格，而是：

- 上一阶段汇报
- 一个设计文档
- 一套方向性的想法

这时如果直接写代码，会出现两个风险：

1. 代码按我理解写，和你心里想的不一致
2. 数据源现实一旦和文档假设冲突，后面整体返工

所以我先做了两件事：

- 重写 `SCREENER_DESIGN.md`
- 新建 `SCREENER_IMPLEMENTATION_PLAN.md`

这两份文档的分工是：

- `SCREENER_DESIGN.md`
  - 负责“系统最终应该长成什么样”
- `SCREENER_IMPLEMENTATION_PLAN.md`
  - 负责“按什么顺序做、每一步产出什么”

也就是说，先把“目标”和“路径”分开。

这是第一层工程逻辑。

---

## 3. 为什么后来会转向 Tencent-first

最开始设计里默认依赖了不少 EastMoney / AkShare-EM 路径。

但真实环境里你和我都遇到了问题：

- EastMoney/AkShare 相关接口被封
- VPN / 代理 / 本机网络问题一度干扰判断
- 即便排除本机因素，EastMoney 反爬强度依旧太高

所以我后面做的不是“继续赌它能恢复”，而是切架构基线：

- `Tencent` 负责历史K线主链
- `THS` 负责概念/行业/资金流主链
- `Sina` 负责实时/指数/龙虎榜
- `Baidu` 负责新闻/估值/人气
- `Baostock` 负责低频兜底
- `EastMoney` 降为兼容层

为什么要先做这个切换？

因为如果主源不稳，后面所有策略代码都会是伪稳定。

这就是第二层工程逻辑：

`先固定真实可运行的数据主链，再写业务策略`

---

## 4. 为什么要先修接口契约

后面 Cursor 做过一次 `data_access.py` 重构，功能上更强了，但它带来了一个典型问题：

- 数据层变了
- 策略层和报告层还按旧字段理解系统

结果就是：

- `TechnicalStrategy` 还在看 `fund_flow_bulk_verified`
- 新数据层却只给 `fund_flow_verified`
- `policy/smart_money` 的状态语义也开始漂移

这时候我先做的不是继续加功能，而是：

- 在 `data_access.py` 补兼容 alias
- 把 `report.py`、策略测试、引擎状态一起修回统一口径

这是因为：

如果契约不稳，新增任何功能都只是把问题埋得更深。

这就是第三层工程逻辑：

`先稳住“模块之间怎么说话”，再扩展“模块各自能做什么”`

---

## 5. 为什么先补骨架，再做真实策略

你看到我中间做了很多“看起来不像策略”的事情，比如：

- `universe.py`
- `merger.py`
- `report.py`
- `engine.py`
- `deep_analyzer.py`

原因很简单：

真实策略不是单文件问题，它必须有上下游。

比如 `technical.py` 的真实分数出来之后，至少要回答：

- 这些候选如何进入 merger？
- 被过滤的票怎么记录？
- 报告里怎么解释为什么留下/剔除？
- deep analyzer 怎么接？

所以我先把这些承接层补成稳定结构：

- `universe.py`
  - 负责“股票从哪来”
- `merger.py`
  - 负责“候选如何融合、如何剔除”
- `engine.py`
  - 负责“整个流程怎么跑起来”
- `report.py`
  - 负责“结果怎么被人看懂”

这就是第四层工程逻辑：

`策略不是孤立函数，必须先有可承接的流程容器`

---

## 6. 为什么先做 technical，再做 policy/smart_money

你后面确认了一个非常合理的顺序：

1. `technical.py`
2. `policy.py`
3. `smart_money.py`

这个顺序不是随便选的。

### 6.1 `technical.py` 为什么先做

因为它的主链最清晰：

- 输入最稳定：历史K线
- 主源最明确：Tencent
- 降级链也最清楚：Sina / Baostock / yfinance

所以它最适合作为“第一个从 placeholder 改成真实评分”的策略。

我在这里做的关键动作是：

- 不再按 `idx` 做递减分
- 改成基于历史价格序列算：
  - `trend_alignment_score`
  - `momentum_score`
  - `drawdown_resilience_score`
  - `volatility_score`

这一步对应文件：

- [tradingagents/screener/strategies/technical.py](D:/cursor/HarmonyOS/Github project/TradingAgents-main/tradingagents/screener/strategies/technical.py)

也就是说，Technical 先从“占位排序器”变成了“真实趋势评分器”。

### 6.2 `policy.py` 为什么第二个做

因为它的复杂度不在数值计算，而在映射：

- 新闻事件怎么找
- 概念怎么选
- 概念如何映射到股票
- 如果 LLM 不介入，最低限度怎么 fallback

所以我先做的是：

- 用 `Baidu news_economic_baidu` 抓政策敏感事件
- 用概念列表做合法集合
- 先用“概念名命中 + 关键词 fallback”
- 再往前推一层，接“概念成分股映射 + 成分股强度评分”

这里的关键不是一步到位，而是：

`先让 policy 至少能从“概念存在”走到“股票强弱”`

后面我又继续往前推了一层：

- 不再让 universe 里的股票“轮流分配概念”
- 而是改成：
  - 先拿概念成分股
  - 再和当前 universe 做真实交叉命中
  - 再做板块内部相对强度排序

这一步很重要，因为它让 Policy 第一次具备了真正的“选股”含义：

- 不是“这个概念热，所以 universe 里的几只票都沾边”
- 而是“这只票确实在这个概念成分里，而且在这个板块内部相对更强”

这就是从“事件主题映射”进入“主题内选股”的分水岭。

### 6.3 `smart_money.py` 为什么最后做

因为它最像“组合型策略”：

- 历史价格
- tick imbalance
- 龙虎榜
- 人气
- 估值

它依赖的信号天然是多路的，最容易出现“每样都有一点，但都不够强”的问题。

所以它不能一开始就当主突破口，否则最容易写成复杂但不稳的代码。

我先给它的主线是：

- `Tencent hist` 做最小可运行链路
- 再叠加：
  - `tick_data`
  - `vote_baidu`
  - `valuation_baidu`
  - `lhb_sina`

这样 Smart Money 的每一层增强都能解释清楚，不会变成黑箱。

后面再往前推一层时，我做的不是盲目加更多字段，而是加“连续性”：

- tick 不只看单次买卖偏向
- 龙虎榜不只看单日是否命中
- 而是开始看：
  - tick persistence
  - 龙虎榜上榜次数
  - 机构席位净额/买入次数

原因是：

单日资金特征很容易噪声过大，而连续性更接近“资金质量”本身。

所以 Smart Money 的加强方向不是“字段越多越好”，而是：

`让信号从一次性异动，变成更像持续性资金行为`

---

## 7. 为什么要不停补测试

你可能会发现，我几乎每改一轮都会补测试。

原因不是“形式化”，而是因为 Screener 这次改动有个特点：

- 不是改一个函数
- 而是在同时改：
  - 文档
  - 数据层
  - 策略层
  - merger
  - engine
  - report

这种场景如果不补测试，最容易出现的就是：

- 前面修好的 ready/degraded 契约被后面悄悄改坏
- report 不再显示关键字段
- merger 返回值变了但 engine 没同步

所以测试在这里不是“锦上添花”，而是“结构胶”。

你可以把测试理解成：

`把我此刻的设计意图钉进代码里`

---

## 8. 这几轮开发里最关键的文件关系

如果你想真正跟上，建议你按这个顺序读代码。

### 第一层：主流程骨架

1. [tradingagents/screener/engine.py](D:/cursor/HarmonyOS/Github project/TradingAgents-main/tradingagents/screener/engine.py)
2. [tradingagents/screener/report.py](D:/cursor/HarmonyOS/Github project/TradingAgents-main/tradingagents/screener/report.py)
3. [tradingagents/screener/merger.py](D:/cursor/HarmonyOS/Github project/TradingAgents-main/tradingagents/screener/merger.py)

先理解：

- Screener 如何启动
- 三策略结果如何汇总
- 报告怎么输出

### 第二层：数据入口

4. [tradingagents/screener/data_access.py](D:/cursor/HarmonyOS/Github project/TradingAgents-main/tradingagents/screener/data_access.py)

重点看：

- vendor baseline
- strategy capabilities
- 各 fetch 方法如何分主备源

### 第三层：三策略

5. [tradingagents/screener/strategies/technical.py](D:/cursor/HarmonyOS/Github project/TradingAgents-main/tradingagents/screener/strategies/technical.py)
6. [tradingagents/screener/strategies/policy.py](D:/cursor/HarmonyOS/Github project/TradingAgents-main/tradingagents/screener/strategies/policy.py)
7. [tradingagents/screener/strategies/smart_money.py](D:/cursor/HarmonyOS/Github project/TradingAgents-main/tradingagents/screener/strategies/smart_money.py)

最后再看：

- 每个策略的 score 是怎么来的
- degraded 是怎么定义的
- raw_metrics 为什么这么设计

### 第四层：测试

8. [tests/test_screener_strategy_technical.py](D:/cursor/HarmonyOS/Github project/TradingAgents-main/tests/test_screener_strategy_technical.py)
9. [tests/test_screener_strategy_policy.py](D:/cursor/HarmonyOS/Github project/TradingAgents-main/tests/test_screener_strategy_policy.py)
10. [tests/test_screener_strategy_smart_money.py](D:/cursor/HarmonyOS/Github project/TradingAgents-main/tests/test_screener_strategy_smart_money.py)

测试不是次要材料，反而是最快看懂“我想保证什么行为”的入口。

---

## 9. 你现在应该怎么跟

如果你想最快跟上，不建议你一上来读所有文件。

建议路径：

1. 先读 `engine.py`
2. 再读 `data_access.py`
3. 再读 `technical.py`
4. 再读 `policy.py`
5. 再读 `smart_money.py`
6. 最后看对应测试

每看一个文件，只回答三个问题：

1. 它的输入是什么
2. 它的输出是什么
3. 它依赖上一个文件的什么东西

你只要按这三个问题去追，代码就会自己串起来。

---

## 10. 这份追溯文档和 Plan3 的区别

`Plan3.md`
- 面向“开发执行”
- 回答的是：
  - 下一步做什么
  - 哪个阶段还没完成

`Trace-back.md`
- 面向“理解和学习”
- 回答的是：
  - 为什么先做这个
  - 为什么不是先做另一个
  - 代码是如何一步步从抽象设计长成现在这个样子的

所以你可以把这两份文档理解成：

- `Plan3.md` 是施工计划
- `Trace-back.md` 是施工纪录片

---

## 11. 当前真实状态

到这一刻为止，Screener 已经不是一个“只有设计，没有代码”的阶段了。

它现在已经完成了：

- 腾讯主源基线切换
- 数据访问层多源化
- 契约修复
- 骨架闭环
- merger/filter/report/engine 第一轮正式化
- `technical/policy/smart_money` 第一轮真实化
- `policy` 进入概念成分交叉命中与板块内相对排名
- `smart_money` 进入连续性/持续性资金特征阶段

但它还没有完成：

- universe 扩展到真实成分股层级
- policy 的更强概念股映射
- smart_money 的更细机构席位/资金画像
- 更完整的 production-grade 策略解释力

也就是说：

`我们已经过了“能不能做”的阶段，正式进入“怎么把它做强”的阶段`

这就是你现在应该理解的开发位置。

---

## 12. 为什么这一轮继续推进的是“板块内 top stock”和“资金质量标签”

这一轮你让我继续推：

- `policy.py` 更接近真实的概念板块内部 top stock 选择
- `smart_money.py` 更接近生产版的多日持续性 + 风险约束 + 资金质量标签

这两个方向表面上看不同，本质上其实在解决同一件事：

`让策略不只是会打分，还要会表达“它到底在选什么”`

前一轮的 `policy/smart_money` 已经不再是 placeholder，但它们还有一个共同问题：

- 分数已经比以前真实
- 但“被选中的原因”还不够像生产系统

也就是说，之前的版本更像：

- Policy: “这个概念热，这只票也在里面，所以给高一点分”
- Smart Money: “这些资金指标看起来不错，所以给高一点分”

这还不够。

生产版更需要的是：

- Policy: “这只票是不是这个概念里的头部票？”
- Smart Money: “这笔资金是持续性资金，还是短线情绪流？”

所以我这一轮没有去引入更多新数据源，而是优先把现有数据的“决策语义”做深。

---

## 13. Policy 为什么要从“概念命中”升级成“板块内选头部”

前一阶段的 `policy.py` 已经完成了三件关键事：

1. 政策新闻 -> 热概念
2. 热概念 -> 成分股
3. 成分股 -> 和当前 universe 做交叉命中

这已经让 Policy 第一次具备了“真的在选股”的含义。

但它还差最后一层：

`同一个概念里，到底谁更像应该被优先选择的票？`

所以这一轮我继续补的是：

- `concept_profiles`
  - 给每个候选概念做一个板块画像
  - 不是只知道概念名，而是知道：
    - 概念热度
    - 成分股数量
    - universe 命中数量
    - 板块 breadth
    - top selection score
- `member_rank_metrics`
  - 给每只股票做“它在板块内部的位置”画像
  - 关注：
    - 是否真实属于该概念
    - 板块内部排名
    - 是否属于 top tier
    - 成员强度 composite
- `board_leadership_score`
  - 明确把“是不是板块头部票”变成显式分数

这样一来，Policy 的行为从：

- “概念热 + 概念命中”

推进成：

- “概念热 + 真实成分股命中 + 板块内部相对强弱 + 头部优先选择”

这是一个很重要的工程升级，因为它把 Policy 从“主题映射器”继续推向“主题内选股器”。

### 13.1 为什么要新增 `stock_selection_tag`

我这轮没有只把信息继续塞进数值分里，而是补了显式标签：

- `policy_top_stock`
- `policy_core_member`
- `policy_cross_hit_candidate`
- `policy_keyword_fallback`

原因是：

如果只有数值分数，你知道“高低”，但不知道“高在哪里”。

标签化之后，report/debug/trace-back 都更容易解释：

- 这只票被选中，是因为它是概念头部票
- 还是只是一个普通成分股
- 还是只是关键词 fallback 兜底

这一步对后续 merger 和 deep analyzer 也有价值，因为它们以后可以直接读这些语义标签，而不是重复猜分数含义。

---

## 14. Smart Money 为什么要从“连续性分数”升级成“资金质量标签”

前一轮的 `smart_money.py` 已经从单点信号推进到了连续性：

- tick imbalance
- tick persistence
- 龙虎榜出现次数
- 机构席位净额 / 买入次数

这一步已经比“只看单日异动”强很多。

但它还没有真正解决一个核心问题：

`资金强，不代表资金质量高。`

例如：

- 热度极高
- tick 买盘很猛
- 但估值很贵
- 龙虎榜连续性弱
- 波动/回撤很差

这种标的如果只按“资金热”去看，很容易被误当成高质量机会。

所以这一轮我继续推进的重点不是再加数据源，而是加约束：

- `multi_day_persistence_score`
  - 把 20 日趋势、tick persistence、龙虎榜 continuity 合并起来
  - 让“持续性”不再只依赖单一路径
- `risk_constraint_score`
  - 把波动、回撤、热度-估值错配、tick 强而 continuity 弱等情况显式惩罚
  - 让资金策略第一次具备“会刹车”的能力
- `capital_quality_tag`
  - 直接把结果归类成：
    - `capital_quality_high`
    - `capital_quality_persistent`
    - `capital_quality_mixed`
    - `capital_quality_speculative`

这一步的意义非常大。

因为从这一步开始，Smart Money 不只是回答：

- “这里有没有资金异动？”

而是开始回答：

- “这股资金更像长期偏好的持续性资金，还是偏情绪化的短线炒作资金？”

这才更接近生产系统的真实需求。

### 14.1 为什么要把风险约束单独做成 `risk_constraint_score`

如果把风险完全揉进总分里，会出现一个问题：

- 你知道最后分数变低了
- 但你不知道是因为趋势不够，还是风险太高

所以我把风险单独抽出来成为一个显式维度。

这样后续你在看报告时就能区分：

- “这只票不是不强，而是风险约束不过关”
- “这只票不是没热度，而是热度和估值严重错配”

这类表达在实盘和复盘里都很关键。

---

## 15. 这一轮为什么是“生产语义增强”，而不是“新增大功能”

你可能会发现，这一轮代码虽然改了不少，但没有大改主流程，也没有再引入很多新接口。

这是刻意为之。

因为当前阶段的重点已经不是：

- 再多接一个数据源
- 再多写一个独立模块

而是：

`把已经接上的真实数据能力，变成更可信、更可解释的决策逻辑`

这也是为什么这一轮我特别强调：

- 标签
- 分层
- 风险约束
- 选择语义

这些东西不会立刻让“看起来的功能数量”变多，但会显著降低后期返工成本。

因为一旦你后面要继续做：

- merger 二次筛选
- report 更细解释
- Deep Analyzer 提示词拼装
- 人工复盘

这些语义化字段都会直接复用。

---

## 16. 你现在再回头看代码，应该重点关注什么

如果你要跟这一轮思路，建议你重点读下面几个函数。

Policy 方向：

- [tradingagents/screener/strategies/policy.py](D:/cursor/HarmonyOS/Github project/TradingAgents-main/tradingagents/screener/strategies/policy.py)
  - `_build_concept_profiles`
  - `_compute_member_rank_metrics`
  - `_compute_board_leadership_score`
  - `_build_stock_selection_tag`

Smart Money 方向：

- [tradingagents/screener/strategies/smart_money.py](D:/cursor/HarmonyOS/Github project/TradingAgents-main/tradingagents/screener/strategies/smart_money.py)
  - `_compute_multi_day_persistence_score`
  - `_compute_risk_constraint_score`
  - `_build_capital_quality_tag`
  - `_build_risk_flags`

你读这些函数时，不要只看公式本身，重点回答两个问题：

1. 这个函数是在把哪个“模糊判断”变成显式逻辑？
2. 这个逻辑以后会不会被 report / merger / Deep Analyzer 直接复用？

只要按这两个问题去看，你就能理解为什么这一步不是“加点分数”，而是在补生产语义。

---

## 17. 为什么还要把这些语义继续下沉到 merger / report

这一轮你继续要求我做的不是再改策略本身，而是：

- 把 `policy_top_stock / policy_core_member` 下沉到 `merger/report`
- 把 `capital_quality_tag` 接入最终保留/剔除规则

这一步非常关键，因为如果这些语义只停留在策略内部，就会出现一个典型问题：

- 策略层已经知道“这是一只板块头部票”
- merger 还是只把它当作普通高分卡片
- report 也不直接展示这个语义

这样就会导致：

- 你明明已经做出了更强的策略语义
- 但最终系统没有真正利用它

所以这一步本质上是在做：

`让策略层新增的业务判断，真正进入最终决策层和最终展示层`

### 17.1 merger 为什么必须理解语义，而不是只看总分

如果 merger 永远只看：

- `screening_score`
- `risk_flags`
- 通用硬过滤

那它就分不清：

- 一个普通概念命中票
- 一个真实板块头部票

也分不清：

- 一个高热度但投机性很强的资金票
- 一个持续性更好的高质量资金票

所以我在 `merger.py` 里做了两件事：

1. 给合并后的卡片补 `semantic_priority`
   - `policy_top_stock` / `policy_core_member` 加分
   - `capital_quality_high` / `capital_quality_persistent` 加分
   - `capital_quality_speculative` 减分
2. 把 `capital_quality_speculative` 从“解释字段”升级成“真实可触发剔除”的条件

这意味着 merger 第一次开始理解：

- 哪些候选是“业务上更值得保留”的
- 哪些候选虽然有分，但语义上更像应该谨慎处理甚至直接剔除

### 17.2 report 为什么要直接展示这些语义

如果 report 还只是展示：

- Score
- Confidence
- Risks

你还是需要回到代码里翻 `raw_metrics` 才知道：

- 这只票是不是概念板块头部票
- 这只票是不是高质量持续资金

所以我把这两块直接抬到了 markdown 报告层：

- `Policy Selection`
- `Smart Money Quality`

这样一来，最终报告第一次开始直接讲“业务语言”，而不是只讲技术字段。

---

## 18. 为什么还要继续下沉到 engine 决策摘要和 Deep Analyzer 提示词

到上一阶段为止，我们已经做到：

- merger 会理解 `policy_top_stock` / `capital_quality_tag`
- report 会展示 `Policy Selection` / `Smart Money Quality`

但如果只停在这里，系统还有最后一个断点：

- merger 的“保留/剔除理由”还没有变成统一的语义摘要
- Deep Analyzer 也还不知道这些语义意味着什么

这会导致一个典型问题：

- 策略层已经知道“这是板块头部票”
- merger 也已经因此优先保留它
- 但 Deep Analyzer 继续把它当成一张普通卡片去分析

这就浪费了前面做出来的策略语义。

所以这一轮继续下沉的目标是：

`把策略层的语义判断，真正变成最终分析阶段可消费的上下文`

### 18.1 为什么 engine 要输出 retained / dropped semantic summaries

如果 engine 只返回：

- candidates
- dropped_candidates

你依旧需要自己再去推理：

- 它为什么留下？
- 它为什么被丢？

所以我把 merger 产生的语义决策摘要继续汇总到 engine metrics 里：

- `retained_semantic_summaries`
- `dropped_semantic_summaries`

这样一来，engine 不再只是“流程执行器”，而开始具备“决策解释索引”的作用。

### 18.2 为什么 Deep Analyzer 必须读懂这些语义

Deep Analyzer 的价值不只是“再跑一轮更深分析”，而是：

`基于 Screener 已经知道的结构化判断，做更聪明的后续分析`

所以我把以下内容直接喂给了 `screener_context`：

- `policy_selection_tag`
- `capital_quality_tag`
- `semantic_decision_summary`
- 以及一段自然语言 `semantic_context_summary`

这样后续深度分析阶段就可以直接知道：

- 这是 `board top-stock`
- 还是 `board core member`
- 这是 `high-quality persistent capital`
- 还是 `high-heat low-quality speculative capital`

这一步的本质是：

`把 Screener 的输出，从“结果列表”推进成“可被下游理解的结构化判断”`

这对以后如果你继续做：

- 更强的 graph prompt 组装
- deep analysis reasoning chain
- 候选复盘解释

都会直接产生收益。

---

## 19. 为什么 semantic summary 还要继续进化成“报告卡片”和“prompt slots”

到上一轮为止，我们已经把语义打通到了：

- merger 决策摘要
- engine metrics
- report 展示
- Deep Analyzer 上下文

但这里还有两个层次可以继续做强：

1. 给人看的表达
2. 给下游模型/graph 看的表达

这两者不应该混在一起。

### 19.1 为什么 report 要做成“Retention Card / Drop Card”

如果 report 只是继续往候选下面堆字段，信息虽然有了，但阅读体验还是像调试输出。

所以我把它进一步整理成：

- `Retention Card`
- `Drop Card`

这样做的好处是：

- 你可以一眼看出“这只票为什么留下”
- 也可以一眼看出“这只票为什么被丢掉”
- 并且每张卡片都把策略语义和规则语义放在一起

这一步本质上是在把 report 从“字段汇总”推进成“决策解释界面”。

### 19.2 为什么 Deep Analyzer 要拆成 `prompt_slots`

自然语言摘要适合人看，但不适合稳定喂给下游 graph/prompt。

因为一旦只靠摘要，下游模块要么：

- 重新解析一段自然语言
- 要么只能粗糙使用

这都不稳定。

所以我把 `semantic_context` 又拆了一层：

- `policy_role`
- `policy_interpretation`
- `capital_quality`
- `capital_interpretation`
- `decision_summary`
- `risk_flags`
- `trigger_reason`
- `strategy_sources`

这样以后如果你开启真实 graph 分析，图里的 prompt 组装就不需要再“猜”这张卡的身份了，而是能直接读这些稳定槽位。

这一步非常像前面修接口契约时做的事：

`不是只让信息存在，而是让信息以稳定、可复用的格式存在。`

---

## 20. 为什么这一轮算是“真实 graph 消费接入”

你这一步要求的不是：

- 再给 prompt 多拼一句注释

而是：

- 让 graph 真的消费 `semantic_prompt_slots`
- 并且让不同 agent 的关注重点发生变化

这两者差别很大。

如果只是把一段语义摘要塞进 Deep Analyzer 的最终输出，那只是“展示增强”。
但这次我做的是：

1. `Propagator` 把 `screener_context / semantic_prompt_slots` 正式写进 graph state
2. analyst / manager / trader / portfolio manager 的 prompt 都开始读取这些槽位
3. 不同 audience 拿到的是不同的语义关注指令

也就是说，现在 graph 不是“知道有这回事”，而是“真的开始按这套语义做不同判断”。

### 20.1 为什么要做统一的语义指令生成器

如果每个节点都自己硬编码：

- `policy_top_stock` 怎么处理
- `capital_quality_speculative` 怎么处理

后面一定会出现：

- 口径不一致
- 某个节点忘了更新
- prompt 风格越来越散

所以我没有把逻辑散写到 7 个节点里，而是抽成统一函数：

- `build_screener_semantic_instruction(state, audience)`

这样做的意义是：

- 语义解释集中维护
- 不同 audience 只拿到自己需要的重点
- 后续如果你再新增 `policy_role` / `capital_quality` 类型，也只改一处

### 20.2 这一步的真实效果是什么

现在如果 Screener 给出：

- `policy_role=policy_top_stock`
- `capital_quality=capital_quality_speculative`

那么：

- `news_analyst` 会更关注它到底是不是真政策受益主线，还是情绪热点
- `market_analyst` 会更关注是否是假突破、执行压力、领导股失效风险
- `fundamentals_analyst` 会更主动验证估值/业绩是否支撑当前热度
- `trader` 会更偏向战术仓位、 tighter stop、事件驱动执行
- `portfolio_manager` 会更严格地处理仓位、情景分析和降级阈值

这就意味着：

`不同 agent 不再拿同一张 Screener 卡走同一套模板，而是开始按卡片语义做差异化消费。`

这就是“真实 graph 消费接入”的核心标志。

---

## 21. 为什么 production-grade 还必须补“schema/version + 辩论层接入”

到上一轮为止，graph 已经开始消费 `semantic_prompt_slots`，但还差两个 production 级别的保障：

1. 这套 slots 的格式要可演进
2. 辩论层也必须消费它，而不只是 analyst / manager / trader

### 21.1 为什么 `semantic_prompt_slots` 一定要有 schema/version

如果没有 schema/version，后面继续迭代时非常危险。

例如你以后可能会：

- 新增 `board_breadth_tier`
- 重命名 `capital_quality`
- 把 `decision_summary` 改成结构化数组

如果 graph 侧没有显式校验，就会出现最麻烦的一类问题：

- 代码不报错
- 但 prompt 消费逻辑已经悄悄偏了
- 最终分析结论开始 drift

这种问题最难发现，因为它不是 crash，而是“表面正常、语义变味”。

所以我这轮补的是：

- 产出端在 `deep_analyzer` 里写明：
  - `schema_name`
  - `schema_version`
- 消费端在 `Propagator / TradingGraph / agent_utils` 里显式校验
- 如果 schema/version 不匹配，就给出明确 warning，而不是静默接受

这一步的价值不是当前立即多一个功能，而是：

`以后继续长功能时，不会在 graph 侧无声漂移。`

### 21.2 为什么辩论层也必须接 semantic routing

如果只有 analyst / trader / portfolio manager 读这套语义，而：

- `bull_researcher`
- `bear_researcher`
- `aggressive / conservative / neutral`

都不读，那么中间最关键的“观点对冲层”还是通用模板。

这会导致一个问题：

- 上游分析已经知道它是 `policy_top_stock`
- 下游 portfolio manager 也知道它是 `capital_quality_speculative`
- 但中间的辩论层却没围绕这个核心矛盾展开

于是 debate 的价值就被削弱了。

所以我把这套语义继续接到了：

- `bull_researcher`
- `bear_researcher`
- `aggressive_debator`
- `conservative_debator`
- `neutral_debator`

这样辩论层也开始按不同语义改变重点，例如：

- `policy_top_stock`
  - bull 会更强调主线领导地位
  - bear 会更主动质疑“是不是伪龙头”
- `capital_quality_speculative`
  - aggressive 可能会辩护为“高风险高回报”
  - conservative 会更强调回撤、仓位、失败率
  - neutral 会更强调“战术参与而不是战略重仓”

这意味着 debate 不再只是泛泛争论，而是开始围绕 Screener 已知的核心矛盾展开。

这一步才更接近 production-grade 多 agent 系统的味道：

`不是所有 agent 都重复说一遍市场观点，而是围绕结构化分歧做分工化对抗。`

---

## 22. 为什么下一步必须走到“语义驱动流程控制”

前面几轮我们做的是：

- 让不同 agent 读懂 Screener 语义
- 让 prompt 根据 `policy_role / capital_quality` 调整关注点

这已经很重要，但还不够。

因为如果流程本身还是固定的，那么系统只是：

- 用不同的话去跑同一个流程

而不是：

- 因为标的语义不同，所以真的走不同流程

这两者差别非常大。

### 22.1 为什么 `capital_quality_speculative` 要影响 debate/risk 节奏

如果 Screener 已经告诉你：

- 这是 `capital_quality_speculative`

那它的流程风险含义是很明确的：

- 研究层不用辩太久
- 风险层应该更强、更严
- 组合经理不该把它和普通高质量资金标的一样看

所以我把这类语义进一步转成了：

- `debate_round_limit`
- `risk_round_limit`
- `force_risk_review`
- `risk_hardening`

这样就不是“提示里说一句要小心”，而是：

- 多空辩论轮次直接缩短
- 风险辩论优先级直接提高
- 在达到正常收敛条件后，还会额外要求保守派再压一次风险

这就是从“语言提醒”走向“流程控制”。

### 22.2 为什么 `policy_top_stock / policy_core_member` 要影响 analyst 编排

如果一个标的是：

- `policy_top_stock`

那它最关键的分析矛盾本来就不在每个 analyst 身上平均分布。

它更需要的是：

- `news`
  - 核验政策主线、事件催化、真实受益逻辑
- `market`
  - 核验龙头结构、承接、延续性
- `social`
  - 判断是否过热

而不是默认所有票都一视同仁地跑完整套 analyst 流水线。

同理：

- `policy_core_member`
  - 也要优先 `news + market + fundamentals`
  - 但不一定要给 `social` 同样高权重

所以我把 analyst 选择从固定列表推进成了：

- `derive_semantic_selected_analysts(...)`

这意味着 analyst pipeline 本身开始对语义有感知。

### 22.3 这一轮的本质升级

你可以把这一轮理解成：

- 前面几轮：语义进入了“内容层”
- 这一轮：语义进入了“流程层”

内容层解决的是：

- 每个 agent 说什么

流程层解决的是：

- 哪些 agent 先上
- 哪些 agent 可以少说
- 哪个阶段必须更严格

这一步一旦完成，Screener 才真正从“选股前置器”开始变成“驱动全链路分析节奏的上游控制器”。

这一步对你后续复盘非常有帮助，因为你已经不需要先理解内部字段，才能看懂候选为什么被保留或丢弃。

---

## 23. 为什么现在要回头补 A1 的 universe 骨架

前面几轮我们把大量精力放在：

- 数据源主链切换
- 三策略真实化
- merger/report/deep analyzer 语义下沉
- graph 侧 semantic routing

这些工作都很重要，但它们默认了一个前提：

`上游 universe 至少应该是一个稳定、可演进、可被 engine/report 理解的结构`

而当时的 `universe.py` 实际上还停留在很早期的占位骨架：

- 只有 `mode -> index_codes`
- cache 文件名只跟 mode 绑定
- engine 还是隐式调用默认配置
- metadata 里没有 profile / expansion_mode / source_signature

这会带来两个后续风险：

1. 以后 universe 一旦扩展到真正的成分股层，会很难知道“当前这次构建到底是哪种 universe 语义”
2. engine/report 即使拿到了 universe 结果，也无法可靠区分：
   - 这是 MVP 还是 EXTENDED
   - 是 index union 还是 constituent expansion
   - 当前 cache 命中的到底是哪套 universe 基线

所以这一步虽然看起来不像“加功能”，本质上是在补一个长期会被反复依赖的上游契约。

### 23.1 我为什么把 `SCREENER_UNIVERSE` 从简单列表改成 profile 结构

旧版本更像这样：

- `mvp -> [000300, 000905]`
- `growth_extended -> [000300, 000905, 399006, 000688]`

这种结构的最大问题不是“信息少”，而是“后续没地方长”。

因为 universe 将来肯定不只需要：

- index codes

还会需要：

- 当前 profile 名称
- 构建来源
- expansion mode
- cache key
- source signature
- 当前是否已经具备 constituent expansion 的 readiness

所以我把它改成 profile-based dict，不是为了好看，而是为了让 universe 成为一个真正可扩展的配置契约。

### 23.2 为什么 `build_screening_universe()` 不能再只看 mode

如果 `build_screening_universe()` 永远只吃 `mode`，那么：

- `MVP`
- `EXTENDED`
- `EXPERIMENTAL`

只能作为一种固定写死的流程分支存在。

但后面真实开发里你一定会遇到这些需求：

- 同一个 `mode` 下临时切换 universe profile
- 对 `EXPERIMENTAL` 做更细的指数/主题扩展
- 把某一类成分扩张行为挂在 config 上而不是写死在函数里

所以我这次做的是：

- `config["universe"]["mode_profile_map"]`
- `profile -> universe definition`

也就是说，`mode` 现在更多只是“运行意图”，而真正的 universe 语义由 profile 决定。

这会让后续你继续做 universe 扩张时，不需要推倒整个调用链。

### 23.3 为什么 metadata 一定要补 `profile / expansion_mode / cache_key / source_signature`

这四个字段不是装饰品，而是后续排障和演进的关键信息。

- `profile`
  - 告诉你这次 universe 到底属于哪一档语义
- `expansion_mode`
  - 告诉你当前只是 index union，还是已经进入 constituent expansion
- `cache_key`
  - 告诉你当前 cache 命中的到底是哪套构建结果
- `source_signature`
  - 告诉你这次 universe 是由哪组指数/配置签名拼出来的

如果没有这些字段，后面你在看 report 或做缓存调试时会非常痛苦，因为你只能看到：

- universe size
- index codes

但不知道“这是哪套 universe 逻辑下生成的 size”。

### 23.4 为什么 `engine.py` 要显式传 config

旧版本的一个隐患是：

- engine 已经有自己的 screener config
- 但 universe 构建却仍然可能退回默认配置

这意味着即使你在 engine 里切了：

- profile
- cache dir
- mode/profile mapping

universe 层也未必真的吃到。

所以我这次把 `engine -> build_screening_universe(mode, config=self.config)` 显式串起来。

这一步的意义是：

`让 universe 不再是 engine 旁边一个“看起来被调用了，实际上还可能按默认值运行”的模块。`

### 23.5 为什么 A1 现在必须补测试，而不是只改实现

这次 universe 骨架升级如果没有测试，后面非常容易被“顺手改回去”。

因为很多人看到 universe 只是：

- 返回一组 ticker

就会低估它其实承载了大量上游契约语义。

所以我补的测试重点不是“能不能返回代码列表”，而是：

- `MVP / EXTENDED / EXPERIMENTAL` 是否真的有不同 profile 语义
- metadata 是否真的带了新的关键字段
- cache 文件名是否跟 `cache_key` 而不是单纯 `mode` 绑定
- engine 跑实验模式时，最终结果里是否真的带到了新的 universe metadata

这类测试的价值在于：

`把这次 A1 universe 升级，从“代码实现”钉成“项目契约”。`

---

## 24. 为什么这一步先修 runtime/config 契约，再继续推进 A2

你这次让我做的是两件连续的事：

1. 确认 `models / runtime / throttling` 和当前 `engine` 契约一致
2. 如果一致，继续推进 A2

这看起来像一个很短的确认动作，但我实际检查之后发现，里面有两个很容易被忽略的问题。

### 24.1 第一类问题：配置“看起来存在”，但 engine 不一定真的在用

最明显的例子就是：

- `SCREENER_CONFIG["run_time"]`

之前它已经定义了：

- `earliest`
- `latest_next_day`
- `allow_weekend`
- `allow_non_trading_day_override`
- `allow_experimental_intraday`
- `max_data_age_days`

但 `engine.py` 在调用 `validate_screener_run()` 时，并没有把这些配置真正传进去。

也就是说，当时的系统状态其实是：

- 文档和配置里写了运行时约束
- 但 runtime guard 还是在按自己的默认值工作

这类问题很危险，因为它不会报错，却会让你误以为：

- “我已经改了配置，所以运行时行为应该变了”

实际上并没有。

所以这一步我先做的不是继续深挖策略，而是把：

- `engine -> RuntimeTimeConfig -> validate_screener_run`

这条链显式接起来。

### 24.2 第二类问题：测试环境依赖会伪装成业务失败

这一步继续跑 Screener 测试时，我又碰到一个现实问题：

- 系统 Python 有 `pytest`，但没有 `pandas`
- bundled Python 有 `pandas`，但没有 `pytest`

如果不处理这个问题，后面你看到的失败会混在一起：

- 有些是业务逻辑失败
- 有些只是导入链过重、环境缺依赖

这会严重干扰判断。

所以我这次顺手继续收紧了 import 边界：

- `ScreenerEngine` 不再在模块导入时硬拉 `strategies`
- 也不再在模块导入时硬拉 `ScreenerDataAccess`
- 改成 `_build_strategies()` / `_build_data_access()` / `_build_deep_analyzer()` 的惰性构造

这样做的意义不是“优雅一点”，而是：

`把“环境依赖是否齐全”和“业务契约是否正确”拆开。`

只有先拆开，后面的 A2/A3/A5 测试才真正有判断价值。

### 24.3 为什么 A2 这一步先做“统一输出层”，而不是立刻大改分数逻辑

当前三策略其实已经不是 placeholder 了：

- `technical`
  - 已经是真实 hist/trend 评分
- `policy`
  - 已经是概念成分映射 + 板块内部 top-stock 语义
- `smart_money`
  - 已经是 Tencent-first + 多日持续性 + 资金质量标签

所以 A2 继续往前推时，优先级已经不是：

- “先让它从 0 到 1 能跑起来”

而是：

- “让三者的输出结构更统一，更容易被 merger/report/deep analyzer 稳定消费”

因此我这一步先补的是统一的策略输出语义：

- `score_family`
- `degraded_context`
- `vendor_trace`

这三个字段分别解决的是：

- `score_family`
  - 这张分数卡到底属于哪类评分模型
- `degraded_context`
  - 当前 degraded 的具体上下文是什么，不只是一个字符串
- `vendor_trace`
  - 这张卡到底走了哪条主备 vendor 路径

这一步非常重要，因为后续你要继续做：

- 报告解释增强
- deep analyzer prompt 细化
- 候选复盘
- 合并器更细语义过滤

都需要稳定吃到这些字段。

所以这一轮虽然看起来是“补点结构化字段”，本质上是在继续把 A2 从：

- “各策略分别变强”

推进成：

- “各策略变强的同时，输出口径也开始统一成系统契约”

---

## 25. 为什么 A2 第二轮要继续往“结构特征 + 语义解释”推，而不是只继续调分数

A2 第一轮完成之后，三策略已经具备了比较统一的输出骨架：

- `score_family`
- `degraded_context`
- `vendor_trace`

这时再往前推，如果只是继续调权重，收益会开始变小。

因为系统下一步真正缺的，不只是“分数更像”，而是：

1. 分数背后的结构判断更像生产版
2. 下游 report / merger 能直接读懂这些判断

所以第二轮我没有只做“再加一点分数项”，而是按三个策略各自最值得深入的方向补。

### 25.1 Technical 为什么要补 `trend_consistency / structure_risk / extension`

第一轮 `technical.py` 已经不是 placeholder 了，但它更偏：

- 趋势方向
- 动量强弱
- 回撤/波动

这还差最后一层很关键的现实判断：

`这个趋势是不是结构上已经过度延伸，或者内部一致性其实并不好？`

所以我这轮补的是：

- `trend_consistency_score`
  - 看正收益天数比例
  - 看均线 spread
  - 看回撤是否打断趋势一致性
- `structure_risk_score`
  - 看价格是否明显偏离 MA20
  - 看 MA20 / MA60 结构是否健康
  - 看波动和回撤是否已经把结构打坏
- 辅助字段
  - `ma_spread_pct`
  - `recent_extension_pct`
  - `positive_days_ratio_pct`

这一步的价值是：

- 不再只会说“涨了很多”
- 而是开始会说“这个趋势本身是不是已经危险”

这也是为什么我让 `technical` 新增：

- `trend_structure_extended`
- `trend_consistency_weak`
- `lost_ma20_support`

这些风险标签。

因为 production 里真正有用的技术策略，不只是找强势票，还要识别：

- 强，但是否已经太挤
- 强，但是否结构已经开始失真

### 25.2 Policy 为什么要把概念链路边界直接做成 `concept_linkage_boundary`

前面 `policy.py` 已经能做：

- 政策新闻 -> 热概念
- 热概念 -> 成分股
- 成分股 -> 和 universe 交叉命中
- 板块内部 top-stock 选择

这已经很强了。

但如果这些信息只存在于策略内部，你在 report 里还是很难一眼判断：

- 这是“真实成分交叉命中”
- 还是“关键词 fallback”
- 还是“概念源未验证”

所以我这轮没有再往前乱接更多数据源，而是把这个边界显式结构化：

- `concept_linkage_boundary`
  - `linkage_mode`
  - `confidence_tier`
  - `concept_primary_vendor`
  - `concept_fallback_vendor`
  - `news_auxiliary_vendor`
  - `constituent_cross_hit`
  - `constituent_count`

这一步非常关键，因为它把 Policy 的“真实能力边界”第一次变成了可被 report 直接读懂的字段。

你后面再看报告时，就不需要自己反推：

- “这只票是实锤概念头部，还是只是关键词兜底？”

### 25.3 Smart Money 为什么要把 `capital_quality` 从标签推进成权重和 summary

前一轮的 `smart_money.py` 已经能输出：

- `capital_quality_high`
- `capital_quality_persistent`
- `capital_quality_mixed`
- `capital_quality_speculative`

但如果它只停留在“标签”，后续 merger/report 虽然能看到这个词，却未必真的利用它。

所以我这轮继续推进的是：

- `capital_quality_weight`
  - 让高质量资金获得显式加分
  - 让投机性资金获得显式减分
- `capital_quality_summary`
  - 把连续性、风险约束、机构参与度浓缩成一句可读语义

这样做之后，`smart_money` 不再只是：

- “给你一个 capital_quality_tag”

而是开始变成：

- “这个质量标签会实际影响分数、排序和最终解释”

这就是为什么我又继续把它往下游推到了：

- `merger`
  - retained/dropped semantic summary
  - dropped card 中的 capital quality explanation
- `report`
  - `Smart Money Quality` 直接显示 summary，而不是只显示 tag

这一步的意义在于：

`资金质量不再只是附注，而是开始进入最终候选优先级语义。`

### 25.4 为什么 report 测试也要改成 stub 契约测试

这一步还顺手暴露了一个工程事实：

- 如果 report 测试依赖真实 `engine -> data_access`
- 那它很容易被环境依赖拖住，例如 `requests / pandas / pytest` 的解释器分叉

所以我这轮把 `test_screener_report.py` 改成：

- 用结构化 `ScreeningResult` 样例直接测渲染契约

原因不是偷懒，而是为了让 report 测试真正回答它应该回答的问题：

- report 是否能读懂：
  - `concept_linkage_boundary`
  - `capital_quality_summary`
  - retained / dropped semantic cards

而不是去回答：

- 当前这台机器有没有完整装好所有网络与数据依赖

这和前面处理 engine / data_access 惰性导入是同一条工程思路：

`把“业务契约正确性”和“环境依赖完整性”拆开。`

---

## 26. 为什么这一轮必须把 Technical 结构风险继续下沉到 merger / report

到上一轮为止，`technical.py` 已经能输出：

- `trend_consistency_score`
- `structure_risk_score`
- `recent_extension_pct`
- `positive_days_ratio_pct`
- `trend_structure_extended / trend_consistency_weak / lost_ma20_support`

这说明策略层已经知道：

- 趋势是不是一致
- 结构是不是健康
- 当前是否已经偏离均线过远

但如果这些判断只停留在 `technical.py` 内部，还会留下一个明显断层：

- `merger` 排序时仍然主要看总分和已有语义
- `report` 仍然只能展示 policy / smart-money 语义
- 最终候选解释里看不出“这只票为什么虽然涨得强，却仍然不该优先保留”

这会让系统出现一种很危险的假象：

`策略层已经看到了结构风险，但最终决策层和展示层还像没看见一样。`

所以这一轮我做的不是“再加一个技术字段”，而是把这些结构判断继续推进到下游消费层。

### 26.1 merger 为什么必须显式消费 technical structure risk

如果 `merger.py` 不理解这些技术结构语义，就会有两个问题：

1. 一只分数不低、但结构已经坏掉的票，仍可能因为总分凑得过去而留在最终候选里
2. 即使它被别的规则顺手剔除了，系统也说不清楚“它其实是因为技术结构很差”

所以这轮我在 `merger.py` 里继续补了三层逻辑：

1. `technical_structure_penalty`
   - 对 `structure_risk_score` 很低
   - `trend_consistency_score` 很弱
   - 丢失 `MA20/MA60` 支撑
   - 近期过度延伸
   的票施加语义惩罚
2. `technical_structure_summary`
   - 把结构风险、趋势一致性、extension、positive-days、flags 收敛成一条可复用摘要
3. `technical_structure_risk` hard-filter
   - 当结构已经很差、趋势一致性也很弱、且综合分数不够高时，直接进入 dropped path

这一步之后，`merger` 对 technical 的理解就不再只是：

- “这张卡有一个技术分数”

而是开始变成：

- “这张卡虽然可能涨得不错，但结构语义告诉我它已经不健康”

这和前面把 `policy_top_stock`、`capital_quality_speculative` 下沉到 merger 是同一种工程动作：

`让策略层的真实业务判断，真正进入最终候选收敛逻辑。`

### 26.2 report 为什么也要同步展示 Technical Structure Card

如果这一步只改 `merger`，你在报告里仍然会遇到一个问题：

- 你知道某只票被保留或剔除了
- 但你看不到它背后的 technical 结构语义

这样就会导致：

- `policy` 语义可见
- `smart_money` 语义可见
- `technical` 最关键的结构风险反而不可见

这显然不平衡，也不利于人工复盘。

所以这一轮我让 `report.py` 继续补了：

- 候选区直接显示 `Technical Structure`
- `Retention Card` 里带上 `technical_structure`
- `Drop Card` 里也带上 `technical_structure`

这一步之后，报告终于能比较完整地解释三类主语义：

1. `Policy Selection`
   - 它是不是板块头部票 / 核心成员 / fallback
2. `Smart Money Quality`
   - 它是不是高质量持续资金，还是高热低质资金
3. `Technical Structure`
   - 它的趋势结构是不是健康，还是已经明显走坏/过度延伸

这样你在复盘时就不再只是看一堆分数，而是能直接看到：

- 为什么留
- 为什么丢
- 技术层面到底出了什么问题

### 26.3 为什么这一轮还要补 engine / merger / report 的解释测试

这一步如果不补测试，最容易出现三种静默回退：

1. `merger` 以后重构时不再把 technical structure 写进 `semantic_decision_summary`
2. `report` 改版时把 `Technical Structure` 展示悄悄丢掉
3. `engine` 继续输出 retained / dropped summaries，但里面已经不再包含技术结构语义

所以我这轮补的测试不是“多写几个断言”，而是在给这条新链路上保险：

- `test_screener_merger.py`
  - 验证弱技术结构候选会被降权/剔除
- `test_screener_report.py`
  - 验证 markdown 里能直接看到 `Technical Structure`
- `test_screener_engine.py`
  - 验证 engine metrics 中 retained/dropped semantic summaries 仍携带这类解释字段

这一步很关键，因为它把“technical 结构风险下沉到最终解释层”正式固定成了契约，而不是一次性的临时实现。

### 26.4 这一轮结束后，系统能力相比上一轮具体提升了什么

相比上一轮，现在系统多了一个非常重要的能力：

`不仅知道一只票强不强，还开始知道“它强得健不健康”，并且这种判断已经真实进入最终保留/剔除与报告解释。`

这意味着：

- technical 不再只是上游算分器
- merger 不再只是总分排序器
- report 不再只是字段拼接器

三者第一次在“技术结构风险”这个维度上形成了真正闭环。

这也是为什么我判断这一轮属于：

- A3 的联动收尾
- A5 的解释层补强
- A6 的契约固化

而不是单纯继续在 A2 里堆 strategy 细节。

---

## 27. 为什么 A4 不能只停在“把 semantic_prompt_slots 传给 Deep Analyzer”

到这一阶段为止，前面的工作已经把很多语义打通了：

- `policy_top_stock / policy_core_member`
- `capital_quality_high / speculative`
- `technical_structure_summary`
- `cross_strategy_conflict`

但如果 A4 只做成：

- `SignalCard -> semantic_prompt_slots -> Deep Analyzer`

那其实还只完成了“信息传过去了”，并没有完成“图真的按这个信息改路由”。

这会留下一个非常典型的伪闭环：

- 上游已经知道这是一只板块头部票
- 也知道它是高热低质资金票
- 也知道它技术结构是不是坏了
- 但 graph 侧仍然默认跑同一套 analyst / debate 流程

也就是说：

`语义被传过去了，但没有真正改变流程。`

所以 A4 后续增强的核心就不再是“再多传几个字段”，而是：

`让 semantic slots 真正进入 graph 路由控制。`

### 27.1 为什么要把 route_decision 显式做出来

如果只是把 `semantic_prompt_slots` 扔给 graph，让下游节点自己随便读，会有两个问题：

1. 你很难知道 graph 到底“读懂了什么”
2. 你很难审计 graph 是依据哪条规则改变 analyst / debate 的

所以我把中间这层明确结构化成了：

- `route_decision`

它不是再造概念，而是把“图为什么这么走”显式写出来，例如：

- `policy_role`
- `capital_quality`
- `conflict_tier`
- `analyst_focus`
- `debate_rounds`
- `debate_risk_weight`
- `selected_analysts`
- `semantic_flow_controls`

这一步的价值是：

- 以前你只能看到“图怎么走了”
- 现在你还能看到“它为什么这么走”

这就是 A4 从“桥接”走向“可审计桥接”的关键一步。

### 27.2 为什么要把 selected_analysts / semantic_flow_controls 继续下沉

前面 graph 层其实已经有一些可复用能力：

- `derive_semantic_selected_analysts(...)`
- `derive_semantic_flow_controls(...)`

这意味着项目原本就已经具备：

- 根据语义裁剪 analyst pipeline
- 根据语义缩短或加强 debate / risk review

如果这一步不接起来，就会出现一个很浪费的状态：

- graph 框架层已经支持语义路由
- screener 也已经能提供语义槽位
- 但两边仍然是松散并列，没有形成真正联动

所以我在 A4 里继续做的其实是“接线”：

1. 在 `DeepAnalyzer` 里基于 semantic slots 生成：
   - `selected_analysts`
   - `semantic_flow_controls`
2. 把它们写进：
   - `route_decision`
   - `graph_config`
   - `screener_context`

这样 graph 在真正执行时，就不再只是拿到一段语义摘要，而是直接拿到了：

- 要跑哪些 analyst
- debate 是否压缩
- risk review 是否强制
- 当前分析优先级是什么

这一步的本质是：

`让 A4 从“提示词增强”升级成“流程控制增强”。`

### 27.3 为什么还要把 graph route 再回写到 report / engine

你后面问了一个非常关键的问题：

`为什么要让最终报告直接展示“这只票为什么走了这条 graph 路由”？`

这个动作的意义其实很大，不只是“让报告更丰富”。

如果 route decision 只存在于 deep analyzer 的内部 state，你会遇到几个实际问题：

1. 你看到最终分析结果，但不知道 graph 侧到底是按什么模式分析它的
2. 你以后修改路由规则，很难比较修改前后到底变了什么
3. 如果某只票被分析得很奇怪，你很难判断问题在：
   - strategy 语义
   - merger 决策
   - graph 路由
   - 还是 graph 内部 agent 本身

所以我把它继续回写到：

- `report.py`
  - 直接显示 `Route Summary`
- `engine.py`
  - 记录 `deep_route_summaries`

这意味着你最后拿到的不是一个黑盒结果，而是一条可追踪链路：

1. 策略层为什么判断这只票有价值
2. merger 为什么保留/剔除它
3. deep analyzer 为什么给它选这组 analyst / debate 路由
4. 最终 graph 是正常执行，还是 fallback 成 dry-run

这一步非常关键，因为它第一次让 graph 路由本身也变成了“最终产物的一部分”，而不是内部实现细节。

### 27.4 这一步对你后续开发最大的帮助是什么

这一步最大的帮助，不是界面更好看，而是：

`你以后终于能把“分析结果错了”拆成更具体的层次去排查。`

比如以后你看到一只票分析得不对，就可以依次判断：

1. 是不是策略层给错了语义？
2. 是不是 merger 误保留了它？
3. 是不是 route decision 选错了 analyst pipeline？
4. 是不是 graph fallback 了，根本没走真实分析？
5. 还是 graph 真实跑了，但某个 agent 结论本身有问题？

如果没有这层 route 回写，你在复盘时会非常痛苦，因为：

- 结果是黑盒
- graph 是黑盒
- 只有 prompt slots 还不够

而现在不同了：

- `semantic_prompt_slots` 说明输入语义
- `route_decision` 说明流程控制
- `graph_config_snapshot` 说明桥接状态
- `Route Summary` 说明最终展示语义
- `deep_route_summaries` 说明 engine 层可审计记录

这就是为什么我判断这一轮不是单纯 A4 内部增强，而是：

- A4 的路由控制增强
- A5 的展示层增强
- A6 的可回归契约增强

---

## 28. 当前阶段判断：为什么我现在把优先级放在 A2 / A4 后段 / A5 / A6

你刚刚要求我把当前进度重新细化回 Plan3，这一步本质上是在把“代码已经做到哪里了”变成“下一步该按什么顺序做”。

截至现在，更准确的阶段判断是：

- `A3`：基本完成
- `A4`：进入后段
- `A5`：基本完成但需打磨
- `A2` / `A6`：仍是后续主要工作量来源

这个判断不是凭感觉，而是基于当前代码已经形成的结构闭环：

### 28.1 为什么说 A3 基本完成

A3 的核心任务是让 merger 从“排序器”变成“候选收敛器”。

现在它已经具备：

- hard filter
- dropped audit
- semantic priority
- policy / capital / technical 的语义下沉
- 多策略冲突归并

这意味着它的“结构角色”已经完成。

后续还可以继续做得更生产化，但那属于：

- 规则打磨
- 冲突文案压缩
- 细化阈值

而不是 A3 的主体缺失。

### 28.2 为什么说 A4 进入后段

A4 一开始的任务是桥接 `SignalCard -> TradingAgentsGraph`。

现在它已经做到：

- semantic prompt slots
- route decision
- selected analysts
- semantic flow controls
- fallback / graph config 审计
- report / engine 回写

所以桥接本身已经不只是“接上了”，而是“可审计地接上了”。

接下来真正还需要做的是：

- graph 内部节点如何更深地消费这些 route decision
- analyst / debate 内部如何进一步差异化

这一轮我又继续把 `route_decision` 写进了 `graph/reflection.py` 的 route summary、structured metadata 和 route memory，
所以 A4 现在已经不只是“把路由传过去”，而是开始“让图的反射层也真实消费并回收这套路由语义”。

因此 A4 不是基础未完成，而是进入了后半段的“深消费”阶段。

### 28.3 为什么说 A5 基本完成但需打磨

A5 的目标是让报告可复盘、可解释。

现在报告已经能展示：

- retained / dropped cards
- policy / smart money / technical 三类语义
- route summary
- deep analysis 的分析模式与 fallback 语义

这说明 A5 的主体目标已经达成。

但它还可以继续打磨成更生产化的样子，比如：

- 更短、更像卡片的展示格式
- 更强的决策摘要压缩
- 更少冗余字段

所以 A5 现在不是“没做完”，而是“已经可用，但可以更像正式产品”。

### 28.4 为什么 A2 仍然是后续主要工作量来源

虽然 A2 已经进入真实策略 MVP 第二层，但它本身仍是 Screener 的业务核心。

也就是说：

- A3/A4/A5 解决的是“怎么收敛、怎么桥接、怎么展示”
- A2 解决的是“到底筛出什么样的票”

所以只要你还想继续把 Screener 往 production-grade 推，A2 一定还会是持续投入最大的部分。

现在 A2 已经不是 placeholder，而是真实策略层；但它要继续向生产版演进，仍然需要：

- 更细的语义
- 更稳的数据源边界
- 更成熟的风险约束

这一轮的推进，已经把 A2 继续推向：

- `technical`
  - `trend_failure_streak / support_loss_count / trend_grade`
- `policy`
  - `board_rank_bucket / board top-stock / core-member / tail-member`
- `smart_money`
  - `continuity_grade / capital_quality_band / speculative risk constraints`

### 28.5 为什么 A6 仍然是后续主要工作量来源

A6 的任务不是“写几个测试”，而是防止前面所有语义化、桥接化、报告化的成果被后续重构悄悄破坏。

现在 Screener 已经不再是简单流水线，而是：

- universe
- strategy
- merger
- deep analyzer
- report
- engine metrics

多层联动之后，契约漂移风险非常高。

所以 A6 接下来仍然是重头戏，因为它承担的是：

`把已经做出来的结构，固定成不会轻易倒退的工程事实。`

而这一轮新增了 `reflection route summary`、`technical trend semantics`、`policy board-rank semantics`、`smart_money quality band`，
因此 A6 的契约防漂移优先级实际上更高了。
