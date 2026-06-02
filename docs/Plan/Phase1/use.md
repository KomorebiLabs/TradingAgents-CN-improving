# TradingAgents 项目命令行使用说明（Screener + 深度分析）

## 0. 品牌吉祥物 Komo

P7: 项目启动时会显示品牌吉祥物 **Komo**（小灰猫）。

- 只在交互式启动时显示一次
- 灰色系、极简风格
- 不影响业务输出
- `--help` / CI / 非 TTY 环境下不显示

---

## 1. 目标说明

你问的"同时开启两个板块功能"在当前项目里有两种方式：

1. 串行联动（推荐）
   先运行 `Screener` 产出候选，再对候选逐个运行 `TradingAgents` 深度分析。

2. 双终端并行（可选）
   在两个终端分别启动 `Screener` 和 `TradingAgents`。这不属于单进程内联动，而是并行运行两个 CLI。

当前架构下，最稳妥的是串行联动。

---

## 2. 环境准备

在项目根目录执行：

```powershell
cd "D:\cursor\HarmonyOS\Github project\TradingAgents-main"
.\venv\Scripts\activate
```

如果你是首次安装依赖：

```powershell
pip install -e .
```

确保 `.env` 中至少有你要使用的 LLM provider key（如 `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` 等）。

---

## 3. Screener CLI（第一阶段）

### 3.1 入口说明

Screener CLI 有两种使用方式：

| 方式 | 命令 | 用途 |
|------|------|------|
| **交互式** | `python -m tradingagents.screener.cli` | 日常使用，分步骤选择 |
| **命令式** | `python -m tradingagents.screener.cli run ...` | 自动化/批处理 |

### 3.2 交互式启动（推荐新手）

```powershell
python -m tradingagents.screener.cli
```

会进入交互式选择页面，按提示选择模式/日期/范围后直接运行。

### 3.3 命令式运行

```powershell
# 查看帮助
python -m tradingagents.screener.cli run --help

# MVP 模式（默认）
python -m tradingagents.screener.cli run --mode MVP --date 2026-05-14 --max-stocks 5

# FULL 模式（全市场）
python -m tradingagents.screener.cli run --mode FULL

# FOCUSED 模式（按板块）
python -m tradingagents.screener.cli run --mode FOCUSED --focus-type sector --focus-value semiconductor

# CUSTOM 模式（自定义列表）
python -m tradingagents.screener.cli run --mode CUSTOM --tickers 600519,000001,300750 --no-deep
```

### 3.4 三层运行模式说明

| 模式 | 描述 | 适用场景 |
|------|------|----------|
| **FULL** | 近全市场扫描 | 离线正式筛选 |
| **FOCUSED** | 限定板块/主题 | 盘中半实时迭代 |
| **CUSTOM** | 显式 ticker 列表 | 策略调参快速验证 |

### 3.5 输出结果

默认会写到 `~/.tradingagents/logs/screener/`，可用参数指定输出目录：

```powershell
python -m tradingagents.screener.cli run --tickers 600519,000001 --output-dir .\reports\screener_runs
```

---

## 4. TradingAgents CLI 深度分析（第二阶段）

原项目 CLI 入口保持可用：

```powershell
tradingagents analyze
```
或
```powershell
python -m cli.main analyze
```

进入交互界面后：
1. 输入 ticker（建议使用 Screener 输出的候选）
2. 输入分析日期（建议与 Screener 同一天）
3. 选择 LLM provider / 模型 / research depth
4. 等待多 agent 流程完成并保存报告

---

## 5. 推荐工作流

### 方式一：交互式（推荐新手）

```powershell
# Step 1: 交互式跑 Screener
python -m tradingagents.screener.cli
# 选择 FULL/FOCUSED/CUSTOM 模式，按提示完成

# Step 2: 从输出报告选 Top 候选

# Step 3: 深度分析
python -m cli.main analyze
```

### 方式二：命令式（适合自动化）

```powershell
# Step 1: 命令式跑 Screener
python -m tradingagents.screener.cli run --tickers 600519,000001,300750 --mode MVP --max-stocks 3

# Step 2: 查看结果
# 报告保存在 ~/.tradingagents/logs/screener/

# Step 3: 深度分析
python -m cli.main analyze
```

---

## 6. 常见问题

1. **命令找不到 `tradingagents`**
   - 用 `python -m cli.main analyze` 代替。
   - 或重新执行 `pip install -e .`。

2. **Screener 周末运行报 runtime guard**
   - 如确需运行，加 `--allow-weekend`。

3. **想减少耗时**
   - Screener 先用 `--no-deep` 快筛，再只对 Top1~3 跑深度分析。

4. **交互式卡住了怎么办**
   - 按 `Ctrl+C` 退出
   - 或直接使用命令式：`python -m tradingagents.screener.cli run ...`

---

## 7. 最短可执行示例

```powershell
cd "D:\cursor\HarmonyOS\Github project\TradingAgents-main"
.\venv\Scripts\activate

# 方式一：交互式（推荐）
python -m tradingagents.screener.cli

# 方式二：命令式
python -m tradingagents.screener.cli run --tickers 600519,000001,300750 --mode MVP --max-stocks 3
python -m cli.main analyze
```
