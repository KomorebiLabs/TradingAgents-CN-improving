# 交接文档：TradingAgents 重构接力（给下一个 Agent）

> 撰写：ZCode（第七轮施工结束时）｜日期：2026-08-16
> 读者：接手继续重构/二开的下一个 agent（或未来的你）
> 配套阅读：`屎山报告-1/2/3`（诊断）、`屎山报告-4-重构施工记录.md`（七轮施工全记录，最重要）、`PROJECT_ARCHITECTURE_REVIEW.md`（最初的体检）

---

## 一、项目现状快照（接手第一件要做的事：核对这一切仍然成立）

```bash
cd "D:\cursor\HarmonyOS\Github project\TradingAgents-main"
venv/Scripts/python.exe -m pytest tests/ -q     # 预期：385 passed，~30 秒
```

- **测试**：385 个用例 / 18 个测试文件，全部离线（无网络无 LLM），覆盖：导入无副作用、版本单一源、状态 canonical 契约、供应商路由、数据端口、AST 依赖图无环、解析器纯函数、执行事件协议、图拓扑分解形态、merger golden/parity、reflection stub-LLM parity、memory parity。
- **架构分层**（依赖只能向左）：
  `cli/`（UI）→ `tradingagents/application/`（契约+事件+服务）→ `graph/`+`agents/`（领域）→ `ports/`（端口）→ `dataflows/`+`screener/vendors/`（基础设施）
- **大文件榜现状**：B 组六大千行文件已**全部拆分完成**（merger / reflection / memory 由交接后的第 8-10 轮完成），当前不再有千行单文件，剩余最大单文件为：
  - `screener/strategies/policy.py` 957、`dataflows/y_finance.py` 883（不在拆分需求内）
  - 拆分产物：`screener/merger/`（9 文件）、`graph/reflection/`（5 文件）、`agents/utils/memory/`（6 文件）
- **硬性不变量**（有测试看守，改坏会红）：模块级 import 图无环；dataflows 不得 import screener；`cli/analyze/run_impl.py` 不得出现 chunk 字段名；版本号只在 pyproject；`AnalysisResult.to_dict()` 的 10 个键不得漂移；`setup_graph` ≤40 行且不内联布线。

## 二、七轮施工已完成的内容（按提交顺序）

| 轮次 | 内容 | 关键产物 |
|---|---|---|
| 1 | Phase 0–2 + Phase 3 半：入口收口、删静默降级、`stream_analysis()` 统一图驱动、配置深合并 | 188 测试起步 |
| 2 | Phase 3 后半：状态 canonical 化 schema v2 | `_ensure_structured_state` 双向补缺失 |
| 3 | Phase 4 首批：`MarketDataPort`、四模块依赖环归零、类型化供应商错误 | `ports/`、`dataflows/errors.py` |
| 4 | Phase 4 主体：`ScreenerDataAccess` 1905→546 拆六层 | `screener/vendors/` 等 |
| 5 | 契约层：`AnalysisRequest/Result` + `AnalysisService` + 9 种执行事件 | `application/` 包 |
| 6 | B组①：`akshare_interface` 1619→41 门面 | `dataflows/akshare/` 七模块 |
| 7 | B组②④：`agent_utils` 944→37 门面；`setup_graph` 471→38 行 | `agents/utils/tools/` 四模块 + 8 个阶段方法 |
| 8 | 任务 A：`merger.py` 1050 → `screener/merger/` 包（9 模块） | golden characterization 17 + legacy-parity 8 |
| 9 | 任务 B：`reflection.py` 1302 → `graph/reflection/` 包（5 模块） | stub-LLM parity 9 |
| 10 | 任务 C：`memory.py` 1124 → `agents/utils/memory/` 包（6 模块） | parity 18 |

详细 diff 说明见 `屎山报告-4` 对应"加更"章节。交接后的 **第 8-10 轮**（merger / reflection / memory 拆分）已在 `refactor/merger-pipeline` 分支依次提交，对应测试见 `tests/test_merger_golden.py`、`tests/test_merger_legacy_parity.py`、`tests/test_reflection_parity.py`、`tests/test_memory_parity.py`。

## 三、待办任务清单（按优先级，含施工指南）

### 任务 A（B组③）：`screener/merger.py` 1050 行 → 纯函数管道 ⭐ ✅ 已完成（第 8 轮）

**为什么**：这是加新筛选规则的必经之路；路线图 4.1 的原始要求是 `normalize_cards → aggregate_strategy_scores → evaluate_conflicts → apply_hard_filters → apply_semantic_policy → diversify_by_sector → rank_candidates → build_decision_explanations` 八段管道，每段输入输出不可变。

**施工指南**：
1. 侦察：`grep -n "^def \|^class " screener/merger.py`；外部调用面 = `grep -rn "from.*merger import\|merger\." --include="*.py" tradingagents | grep -v merger.py`（预计：`screener/engine.py` 是主调用方）。
2. 通读全文（1050 行，分 3 段读），画出每个 helper 属于哪个管道阶段。
3. 拆分方案建议：`screener/merger/` 包：`pipeline.py`（主入口，一屏可读）、`aggregation.py`、`conflicts.py`、`filters.py`（硬过滤）、`semantic.py`（语义政策）、`diversify.py`（行业分散）、`ranking.py`、`explanations.py`。原 `merger.py` 留薄转发或直接改 import（调用方只有 engine，数量少可直接改）。
4. **golden fixtures 是本任务的验收核心**（路线图 4.4）：造 10–20 组 `SignalCard` 输入 fixture（读 `screener/models.py` 了解 SignalCard 字段），冻结：冲突规则、hard drop reason、行业分散、policy focus、score 排序、解释文案 payload。先写 characterization 测试冻结现状行为，再动结构。
5. 风险：业务逻辑密集，**不要**在拆分的同时"顺手修 bug"——发现可疑逻辑记下来单独汇报。

### 任务 B（B组⑤）：`graph/reflection.py` 1302 行 → Reflector 拆分 ✅ 已完成（第 9 轮）

**为什么**：Reflector 一个类混了 LLM 反思（reflect_bull/bear/trader/invest_judge/portfolio_manager）、路由统计（get_route_summary/get_route_statistics）、结论摘要（generate_conclusion_summary）。路线图 2.5 要求拆为 MemoryStore / MemoryRetriever / ReflectionService / RouteAnalytics / ConclusionRepository。

**施工指南**：
1. 调用面：`trading_graph.py`（reflect_and_remember、_log_state 用 get_route_summary）。
2. 建议拆法：`graph/reflection/` 包或同文件先拆方法簇 → `ReflectionService`（LLM 反思）、`route_analytics.py`（纯函数，get_route_summary 系列，**先拆这个**，它无 LLM 依赖可立即加测试）、`conclusion.py`（结论摘要）。
3. 注意：`reflect_and_remember` 里那个 `except Exception: pass`（记忆持久化静默吞错）——拆分时保留行为但记录到"待治理异常清单"。

### 任务 C（B组⑥）：`agents/utils/memory.py` 1124 行 → StructuredMemory 拆分 ✅ 已完成（第 10 轮）

**施工指南**：类内混了存储、BM25 检索、过滤、统计、趋势分析。建议按 `memory/` 包拆 `store.py`（CRUD+持久化）、`retrieval.py`（BM25+过滤）、`analytics.py`（统计+趋势）。调用面：`trading_graph.py`（6 个记忆实例）、`memory_manager.py`。BM25 是本地实现，**保留**（报告 2 §4 明确不引入向量库）。

### 任务 D（小件，建议先做）：CI 流水线 ✅ 已完成（提交 e6eaa7c，`.github/workflows/ci.yml`）

`.github/workflows/ci.yml`：push/PR 触发 `pip install -e . && pip install pytest && pytest -q`。纯新增文件，零风险，立刻让 313 个测试从"本机跑"变"每次 push 自动跑"。用户是 GitHub 仓库，直接可加。

### 任务 E（小件）：README 清理 ✅ 已完成（README.md 去除上游英文冗余、克隆链接改 KomorebiLabs、目录树更新；README_TECH.md 路径引用修正 + 2026-08 拆分附录；本交接文档已同步刷新）

README.md 混着上游英文 README、克隆链接指向上游、README_TECH.md 的精确数字已因拆分失真（data_access 行数、akshare_interface 行数等）。对照 `屎山报告-4` 的行数表更新。

### 任务 F（按需，破坏性）：`cli` 顶层包迁入 `tradingagents.cli`

`pyproject.toml:39` 仍把 `cli*` 发布为 site-packages 顶层包（撞名风险）。迁移 = 移动 `cli/` → `tradingagents/cli/` + 全库改 import（约 20 处）+ 更新 pyproject packages + 入口。建议等下一次大版本一次性做，做前跑全套测试。

### 任务 G（长期）：171 处 `except Exception` 分类收窄

地基已铺（`dataflows/errors.py` 的 VendorError 族）。方法：`grep -rn "except Exception" --include="*.py" tradingagents | grep -v test` 逐个分类——预期失败（供应商挂/数据缺）改抛/接类型化错误；编程错误（AttributeError/TypeError/KeyError）删除捕获让它冒泡。**跟着 bug 修，不要专项大扫除**。

### 任务 H（二开功能项，非重构）

- confidence score 真实实现（现在 AnalysisResult.confidence=None，UI 显示 N/A）——入口在 `application/service.py` 的 result 装配处，需要从 final_state 提取或让 Portfolio Manager 产出。
- 状态 v2.1 里程碑：节点停写平铺字段（改 `state_helpers.sync_*` 系列即可，全节点已走这些 helper）。

### 任务 I（清理，用户确认后执行）：删除三个 `_legacy.py` 遗留文件

merger / reflection / memory 拆分后原单文件保留为 `*_legacy.py`（供 parity 验证）。等价性已被 `tests/test_merger_legacy_parity.py`（8 用例）、`tests/test_reflection_parity.py`（9 用例）、`tests/test_memory_parity.py`（18 用例）钉死。用户确认后：

```powershell
git rm tradingagents/screener/merger_legacy.py tradingagents/graph/reflection_legacy.py tradingagents/agents/utils/memory_legacy.py
# 同时删除对应的 *_parity.py 测试（它们 import legacy）
git rm tests/test_merger_legacy_parity.py tests/test_reflection_parity.py tests/test_memory_parity.py
```

删除后跑 `pytest -q`，预期剩余测试仍全绿（golden/unit 测试不依赖 legacy）。

> 附带：`tradingagents/commands/` 与 `tradingagents/screener/cli/` 在磁盘上只剩 `__pycache__` 空壳（git 已无跟踪源码），可随此轮一并手动清理目录。

## 四、已验证的施工方法论（照抄即可，七轮实战沉淀）

1. **侦察三连**：函数清单 grep → 外部调用面 grep → gitnexus impact（记得 `--repo TradingAgents-CN-improving`，且索引可能滞后，**grep 交叉验证**）。
2. **AST 机械拆分优于手抄**：按顶层 def/class 边界切块。⚠️ 三个已踩过的坑：
   - 块收集要处理 `AnnAssign`（`X: Dict = {}` 带注解赋值）——第六轮漏了两个常量；
   - 切块之间的"间隙语句"（未映射的顶层代码）会静默丢失——拆完必须跑名字解析检查；
   - 段落嵌入新方法时**不要 dedent**（原方法体 8 空格缩进恰好就是新方法体缩进）——第七轮第一版就栽在这。
3. **名字解析检查**（拆分后必跑）：AST 收集模块内 defined（含 import/函数参数/循环变量/全局声明），遍历所有 Load 的 Name 报未解析项。脚本见报告加更五/六，约 40 行。
4. **等价性验证**（改控制流时）：AST 提取新旧版本的节点/边/调用集合做 diff；遇到循环变量要展开（For + 字面量 tuple → 逐值代入）。
5. **门面 + 重导出**保公开 API 零变化；消费方多的（agent_utils 18 个）必用门面，消费方少的（merger 只有 engine）可直接改 import。
6. **每步全量回归** `pytest -q`；收尾 `npx gitnexus detect-changes --repo TradingAgents-CN-improving` 核对影响面。
7. **不删文件**（用户自己删）、**不提交**（用户审后自己提交）、拆分时发现的行为疑点**记录不修**。

## 五、关键约束（违反会被测试或用户抓）

- `AGENTS.md`：改符号前跑 gitnexus impact；HIGH/CRITICAL 要告知用户；提交前 detect-changes。
- 兼容层必须薄（≤3 行转发），禁止复制实现。
- 测试全部离线：不准引入真实网络/LLM 调用；新测试沿用此标准。
- 中文文档习惯：报告系列用 `屎山报告-N-标题.md` 命名，追加"加更"章节而非重写。

## 六、文档索引

| 文档 | 内容 |
|---|---|
| `屎山报告-1-现状总览.md` | 首轮诊断基线（部分数字已过时） |
| `屎山报告-2-根基问题剖析.md` | 七大根基问题（五大已铲平、两大半程） |
| `屎山报告-3-清理与重构路线.md` | 原路线图 + 可删清单（大部分已执行） |
| `屎山报告-4-重构施工记录.md` | **七轮施工全记录**，含每轮验证数据与提交命令 |
| `清洗.md` | 早期文件删除清单（已完成，仅存档价值） |
| `PROJECT_ARCHITECTURE_REVIEW.md` / `REFACTORING_ROADMAP.md` | 上一位 agent 的体检与路线图（历史参照） |

祝施工顺利。这个仓库已经从"不敢动的屎山"变成了"有 313 个测试护栏的可演进平台"——请保持这个标准。
