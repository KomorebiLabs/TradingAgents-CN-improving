# 面试演示手册：Analyzer + Screener

本手册用于复现项目的最小演示路径。默认以 Windows PowerShell 和仓库虚拟环境为例；真实 LLM 演示会消耗 Agnes 配额，先确认 `.env` 已配置并设置合理预算。

## 1. 离线护栏

```powershell
venv\Scripts\python.exe -m pytest tests/ -q
venv\Scripts\python.exe -m compileall -q tradingagents cli tests
```

预期全量测试为 `682 passed`。该步骤不需要网络或 LLM Key。

## 2. Screener 快速演示（不调用 LLM）

先用小预算验证数据、策略、Merger 和报告产物：

```powershell
venv\Scripts\python.exe -m tradingagents screener run `
  --mode FOCUSED `
  --focus-type index `
  --focus-value 000300 `
  --date 2026-08-24 `
  --stagea-max-input 5 `
  --stageb-max-input 3 `
  --max-stocks 3 `
  --no-deep
```

然后检查：

```powershell
Get-ChildItem reports\Screener -Recurse | Select-Object -First 30
Get-Content reports\Screener\acceptance_latest.json
```

正式候选必须同时查看 `recommendation_eligible`、`decision_quality` 和 `vendor_health`，不能只看分数或 BUY/HOLD/SELL 文本。

## 3. Analyzer Agnes 真实演示

确认 `.env` 使用 Agnes：

```text
LLM_PROVIDER=agnes
DEEP_THINK_LLM=agnes-2.5-flash
QUICK_THINK_LLM=agnes-2.5-flash
AGNES_API_KEY=你的密钥
```

小规模无交互运行：

```powershell
venv\Scripts\python.exe -m tradingagents analyze `
  --ticker 600519 `
  --date 2026-08-20 `
  --no-interactive
```

运行后按 `run_id` 检查 `reports/600519/2026-08-20/<run_id>/`，至少确认最终决策、验证摘要、Token/成本统计、`security_audit.json` 和工具日志均存在。不要把单次 `HOLD` 或 `BUY` 当成准确率证据。

## 4. 连续运行监控

```powershell
venv\Scripts\python.exe -m tradingagents.screener.acceptance `
  --reports-dir reports/Screener `
  --required-days 5 `
  --output reports/Screener/acceptance_latest.json
```

少于 5 个不同交易日时返回非零是预期行为，表示证据不足，不是程序故障。必须等待真实交易日运行积累，不能改日期或复制 artifact 绕过门槛。

## 5. 不建议在面试现场演示的内容

- 不现场执行完整 DeepAnalyzer 长链路，除非已准备预算和固定候选；
- 不现场启用 Tushare，当前账号权限/积分不足；
- 不现场承诺自动下单、收益率或模型准确率；
- 不使用 `--hitl` 作为第一次演示路径，HumanGate 的真实暂停/恢复仍应明确标注为待补充证据。

