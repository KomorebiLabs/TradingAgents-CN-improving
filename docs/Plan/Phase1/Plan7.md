# TradingAgents CLI Brand Mascot Plan 7

> 目标：给 TradingAgents CLI 启动流程增加一个**品牌化 Terminal Mascot**。  
> 角色名：**Komo**。  
> 定位：**小灰猫 / 温柔 / 极简 / 日系 / 静态 / 启动只出现一次**。  
> 技术约束：使用 **Rich**，不使用 Textual，不使用动画，不使用事件系统，不引入 TUI。  
> 生效范围：所有人机交互型 CLI 启动入口。  
> 日期：2026-05-15

---

## 0. 设计原则

1. 只做“启动品牌记忆点”，不改变任何业务逻辑。  
2. 只显示一次，且只在启动阶段显示。  
3. 视觉必须是“灰猫品牌卡”，不是简单线条 ASCII。  
4. 默认只在 TTY 交互终端显示，`--help`、CI、批处理模式不显示。  
5. 不拆现有 CLI 架构，不重写启动流程。

---

## 1. 目标效果

启动时，用户先看到一个静态的 Rich 卡片：

- 灰色系
- 轻柔
- 极简
- 有辨识度
- 名字 `Komo` 显示在宠物下面

要求：

1. 看起来像“这个 AI 的品牌开场白”。  
2. 不能只是 `/\_/\\`、`(=ω=)` 这种裸线条堆叠。  
3. 要有“填充感”和“灰度层次感”。  
4. 不动、不开播、不闪烁。  
5. 启动后只出现一次，后续 prompts 不重复。

---

## 2. 视觉规范

### 2.1 色彩

建议使用 Rich 灰度层次，不要高饱和色：

- 主体灰：`grey62`
- 阴影灰：`grey39`
- 轮廓灰：`grey74`
- 文字灰：`grey70`
- 名称灰：`bright_black` 或 `grey58`

### 2.2 造型

Komo 必须是“块面感”而不是“空心轮廓感”：

1. 允许使用 `░▒▓█` 这类灰阶块字符。  
2. 允许用 Rich 的背景色做“填充”。  
3. 允许少量留白表现眼睛/鼻子。  
4. 不允许只靠细线框出猫形。

### 2.3 名称位

- `Komo` 必须出现在宠物下方。  
- 位置居中。  
- 字号不需要大，但要稳定可见。  
- 文字风格偏温柔、克制。

---

## 3. 生效范围

### 3.1 必须显示的入口

1. `python -m cli.main`
2. `tradingagents` 命令入口
3. `python -m tradingagents.screener.cli`

### 3.2 不显示的场景

1. `--help`
2. shell completion
3. CI / 自动化脚本
4. 非 TTY 输出

### 3.3 一次性规则

1. 每次进程启动只显示一次。  
2. 交互流程内不得重复打印。  
3. 子函数或二次进入不得重复渲染。  
4. 退出后重启才允许再次显示。

---

## 4. 推荐实现方式

### 4.1 共享渲染器

新增一个共享模块，供两个 CLI 入口共同调用：

- `tradingagents/ui/terminal_mascot.py`

职责：

1. 生成 Komo 的 Rich 渲染块。  
2. 提供一次性显示函数。  
3. 提供“是否显示”的判断逻辑。  
4. 提供统一的品牌标题和副标题。

### 4.2 入口注入

在以下入口处调用共享渲染器：

- `cli/main.py`
- `tradingagents/screener/cli/app.py`

要求：

1. 只在真正进入交互流程时显示。  
2. `--help` 分支不触发。  
3. 不要把渲染逻辑散落到各个 prompt 里。

---

## 5. 任务拆解

## Task P7-1 统一品牌规范

目标：先定义 Komo 的视觉规范和行为边界，再写代码。

修改文件：
- `docs/Plan7.md`
- `docs/use.md`

实现内容：

1. 确定 Komo 的固定命名。  
2. 确定灰阶色板。  
3. 确定只在启动时显示一次。  
4. 确定不使用动画/TUI/事件系统。  
5. 确定输出位置在第一屏、第一交互之前。

验收标准：

1. 规范不会随实现者自由发挥而漂移。  
2. 两个 CLI 入口遵守同一套品牌规则。  
3. 文档可以直接指导 Cursor 实施。

---

## Task P7-2 创建共享 Mascot 渲染模块

目标：把品牌渲染集中在一个地方，避免重复实现。

修改文件：
- `tradingagents/ui/terminal_mascot.py`

实现内容：

1. 用 Rich 生成静态品牌卡。  
2. 用灰度块、软边框、低饱和文字表现 Komo。  
3. 名称 `Komo` 放在宠物下方。  
4. 提供 `print_terminal_mascot(console, entrypoint=...)` 之类的统一接口。  
5. 提供一次性 guard。

验收标准：

1. 模块可被两个 CLI 入口复用。  
2. 模块本身不依赖业务引擎。  
3. 渲染结果是静态图块，不是动画。

---

## Task P7-3 接入 TradingAgents 主 CLI

目标：让原 `cli.main` 进入时先展示 Komo，再进入现有选项流程。

修改文件：
- `cli/main.py`

实现内容：

1. 在交互选择开始前调用 Komo 渲染器。  
2. 保持原有选择流程不变。  
3. 不影响分析逻辑和报告逻辑。  
4. 不影响 `--help`。

验收标准：

1. `python -m cli.main` 启动先看到 Komo。  
2. `python -m cli.main --help` 不出现 Komo。  
3. 原有多步骤选择逻辑继续正常工作。

---

## Task P7-4 接入 Screener CLI

目标：让 Screener 的交互式启动页也带上同一只 Komo。

修改文件：
- `tradingagents/screener/cli/app.py`
- `tradingagents/screener/cli/interactive.py`

实现内容：

1. 在 Screener 交互页最前面显示 Komo。  
2. 保持一次性显示，不在每个 prompt 重复。  
3. 与主 CLI 共用同一渲染器。  
4. 不改变 `run` 子命令的执行语义。

验收标准：

1. `python -m tradingagents.screener.cli` 先看到 Komo。  
2. `python -m tradingagents.screener.cli run ...` 的业务输出不被破坏。  
3. 视觉风格统一。

---

## Task P7-5 一次性与静默规则

目标：保证 Komo 只在合适的启动场景出现一次。

修改文件：
- `tradingagents/ui/terminal_mascot.py`
- `cli/main.py`
- `tradingagents/screener/cli/app.py`

实现内容：

1. 增加一次性 guard。  
2. 识别 `--help`、completion、非 TTY、CI。  
3. 在上述场景自动静默。  
4. 避免同一进程重复打印。

验收标准：

1. 启动一次只出现一次。  
2. 帮助信息不被污染。  
3. 脚本/自动化环境不会被品牌卡干扰。

---

## Task P7-6 文档同步

目标：让用户知道 Komo 是启动品牌层，而不是业务功能。

修改文件：
- `docs/use.md`

实现内容：

1. 说明 Komo 只在启动页出现一次。  
2. 说明它不影响业务输出。  
3. 说明两套 CLI 都会看到同一个品牌入口。  
4. 说明关闭条件（help / CI / non-TTY）。

验收标准：

1. 文档与行为一致。  
2. 用户不会误以为这是 TUI 或新交互框架。  
3. 可指导 Cursor 继续扩展品牌层。

---

## 6. 实现约束

1. 不使用 Textual。  
2. 不使用动画。  
3. 不使用事件系统。  
4. 不引入持续刷新。  
5. 不改 Screener/TradingAgents 的业务状态机。  
6. 不把 Komo 做成一个“功能模块”，它只是启动品牌层。

---

## 7. 最小验证

Cursor 完成后只做最小启动验证：

```bash
python -m cli.main --help
python -m cli.main
python -m tradingagents.screener.cli --help
python -m tradingagents.screener.cli
```

验证重点：

1. Komo 只显示一次。  
2. help 不显示。  
3. 两个 CLI 入口风格统一。  
4. 不影响后续交互与执行。

---

## 8. 完工标准

满足以下条件即可宣布 Plan7 完成：

1. TradingAgents 启动时有静态品牌吉祥物 Komo。  
2. Screener 启动时有同一品牌吉祥物 Komo。  
3. 只显示一次。  
4. 只在启动阶段显示。  
5. 视觉是“灰色、温柔、极简、填充感”，不是线条涂鸦。

---

## 9. 给 Cursor 的一句话指令

按本 Plan7 只做启动品牌层，不动业务逻辑；用 Rich 实现一个静态、一次性显示的灰猫吉祥物 Komo，并把它接入 TradingAgents 与 Screener 的交互式启动入口，保证 help / CI / 非 TTY 不显示。
