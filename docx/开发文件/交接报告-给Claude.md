# 交接报告 · 给 Claude

> 交接方：DeepSeek Harness Agent（此前所有工作的执行者）
> 日期：2026-08（冲刺收官）
> 我的任务已全部提交在分支链上，仓库干净可接。这份报告让你 10 分钟内进入状态。

---

## 一、这是什么项目（一句话）

**面向 A 股的多智能体 LLM 交易框架**：LangGraph 状态机（分析师→多空辩论→交易员→风控辩论→决策）+ Screener 选股引擎（5 级供应商降级）+ 从"屎山"重构出的干净分层 + 439 个离线测试。上游是 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)，本仓库深度定制了 A 股数据/政策/资金流。

## 二、Git / 仓库现状（先核对）

- **本地路径**：`D:\cursor\HarmonyOS\Github project\TradingAgents-main`
- **当前分支**：`feat/r11`（HEAD `aa45d4d`），工作区干净
- **远程**：origin=`yyt-waiting/TradingAgents-CN-improving`；**实际推送目标 = `KomorebiLabs/TradingAgents-CN-improving`**（unconfigured remote，用 URL 推）
- **分支保护已启用**（main）：必须 PR + status check `CI / test (pull_request)` ⚠️ 注意 context 是 **gh pr checks 显示的真实 job 名 `test`**，不是 UI 名——当初在这个坑上卡了三次
- **PR 链（全部未合并，逐 PR 先合 main 再派生最干净）**：
  `feat/data-reliability`(R3) → `feat/backtest`(R1) → `feat/vendor-health`(R3-2) → `feat/ablation`(R4) → `feat/model-trust`(R8) → `feat/sensitivity`(R9) → `feat/eval`(R10) → `feat/r11`(R11)

## 三、已完成（可对着测试/报告验证）

| 板块 | 提交/分支 | 交付 | 关键数字 |
|---|---|---|---|
| 重构 A/B/C | main | merger/reflection/memory 千行拆包（golden+parity） | 347 测试起步 |
| R3 | feat/data-reliability | 失败可见性(27 fn)+反爬重试(429/403 不重试)+熔断+假成功可见 | 369 |
| R3-2 | feat/vendor-health | **供应商健康监控**(失败率/耗时/错误逐供应商)+缓存 hit/miss | 395 |
| R4 | feat/ablation | 多智能体消融框架（分析师×辩论） | 406 |
| R8 | feat/model-trust | **模型目录祛魅**（虚拟名→真实 ID，防回归测试） | 411 |
| R9 | feat/sensitivity | 参数敏感性扫描（engine 支持 config 注入） | 416 |
| R10 | feat/eval | 决策正确性评测集（混淆矩阵/方向准确率） | 428 |
| R11 | feat/r11 | 成本估算+结构化决策解析+可选 LLM 缓存 | 439 |

**真实产物（reports/ 已 gitignore，本地可看）**
- `reports/backtest/20260819_134532/`：**回测 82.86% / 夏普 2.17 / 超额 +56.57%**（12 个月 CSI300-80 池，月度 top5，technical 因子，future-function 已核查）
- `reports/sensitivity.md`：动量权重 −22% → 收益腰斩（真实敏感性证据）
- `reports/backtest/20260819_132132/`：smoke 版（含 equity_curve.png）

## 四、用户的最新定位（务必遵守）

> 用户原话（撤回前）：**不要求真实运行验证**（LLM 链路慢、运行中项目），聚焦**"表面功夫但有技术含量"的面试包装**；架构已无问题，目标是应对面试。
> 撤回事件：我一度把"治理报告 6"改成"面试包装导向版"，用户说"不对，撤回"——**报告已恢复原版**。但用户的**真实意图仍是面试包装**（README 亮点/架构图/面试导航），只是方式要稳妥、不造假。

**红线（勿踩）**：
1. **所有数字必须来自真实产物**（`pytest`/`reports/`/真实探测），可复现，不编造；
2. **82.86% 永远挂限制句**（单段、无成本、technical 因子 only、存续偏差）——不宣传成预测能力；
3. 验证过的（技术因子回测 ✅）和设计上的（消融/评测框架就绪 ❓未跑）**分开说**；
4. **vendors 类型化严禁一次性大改**；只做有真实触发点的 2 源闭环（东财/百度）。

## 五、待办（按用户目标排序）

### 面向面试的"门面"（用户最想要，全部免费）
1. **README 技术叙事化**：顶部加"项目亮点"区（回测/敏感性/439 测试/健康监控/六大千行拆解）+ 数字挂限制句；
2. **`docs/architecture.md`**：分层图（cli→application→graph/agents→ports→dataflows/screener）+ LangGraph 决策流程图 + 数据降级链图；
3. **`docs/interview-notes.md`**：面试护航（60 秒讲清项目 + FAQ + "它准吗"诚实应答话术）。

### 治理报告 6 的方案（`治理报告-6-残余不足与治理方案.md`，按需推进）
- P0/P1：多窗口回测（免费数据，真跑）、成本显式化（cost_bps）、point-in-time 审计；
- 明确不做的：端到端 LLM smoke、消融/评测实跑（需 key/慢，用户不需要）。

## 六、工作纪律（沿用，别破坏）

- **一个板块一个分支一个 PR**；不删文件（用户自己删）；不提交（用户审后提交）；
- **测试全离线**（无网络/无 LLM），新增测试沿用此标准；每步 `pytest -q`；
- 中文文档习惯：`报告-N-标题.md` 或 `交接文档-*.md`；追加"加更"而非重写；
- 改关键符号前做影响面分析（grep 交叉验证；无 gitnexus MCP 时用 grep+parity 顶替）。

## 七、已知坑与教训（血泪）

1. **分支保护 context**：必须用 `gh pr checks 3` 显示的 **API 真实 job 名**（`test`），不是 UI 的 `CI / test (pull_request)`；配错 = 永久 "Expected waiting"；
2. **每次 `TechnicalStrategy.run` 会触发全量 live probe（70 项）**——回测/敏感性会因此变慢；重跑大数据集注意把 probe 缓存利用好（同 da 实例）；
3. **管道截断杀进程**：`python x | Select-Object -First N` 会 BrokenPipe 杀进程、写不出报告——长跑一律重定向到文件再 tail；
4. **akshare 腾讯接口 10s+**（慢源）；东财 `stock_individual_fund_flow_em`、百度新闻当前**因 AkShare 版本漂移失效**（勿当它们可用）；
5. **`vendors/__init__` 必须显式 import 子模块**（否则独立用 ScreenerDataAccess 会 AttributeError——已修复，别再回退）；
6. 分支派生链很长（R1→…→R11），**别在旧分支上继续叠新 PR**——尽量从已合并的 main 派生。

## 八、文档导航

| 文档 | 内容 |
|---|---|
| `README.md` / `README_TECH.md` | 项目门面 / 技术手册（已祛魅） |
| `交接文档-给下一个Agent.md` | 上一轮重构交接（任务清单，已完成） |
| `屎山报告-1..5` | 诊断与七轮+重构施工记录 |
| `治理报告-6-残余不足与治理方案.md` | 下一阶段方案（恢复原版） |
| `项目发展路线规划-简历价值导向.md` | 简历导向路线（R1-R11 + 24h 冲刺计划） |
| `tests/`（18 个文件） | 439 个离线测试护栏 |

祝顺利——底层已硬，剩的是"把它讲出去，且经得起问"。
