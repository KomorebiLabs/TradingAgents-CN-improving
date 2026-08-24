# AI-Agent 工程深化接力修复实施计划

> For agentic workers: 使用 executing-plans 按任务执行。每个任务完成后必须运行对应验证；不要把所有模块一次性重写。

目标：在保留 GLM 当前未提交改动的基础上，修复 P0 回归，补齐 A5、A6、A4、B3、B5、E2、E3 的关键验收缺口，并用离线集成测试和可审计产物证明结果。

架构：保持现有 CLI → AnalysisService → TradingAgentsGraph → GraphSetup 分层。HumanGate 恢复载荷只在应用服务层透传；安全审计使用 run-scoped context 写入运行产物；B3/B5 约束通过纯函数校验器后由现有 ConstraintEnforcer 接线；A4/B2 时间证据通过 ToolMessage 元数据和请求日期边界完成最小闭环。

技术栈：Python 3.10、LangGraph、LangChain messages、PyYAML、pytest、GitNexus。

执行状态（2026-08-24）：Task 0–6 已完成；Task 7 已完成离线全量验收、静态检查和审查报告更新。真实 API 长链路与真实 CLI HITL 运行未执行，原因及剩余风险已写入审查报告，不将离线证据冒充真实运行证据。

---

## 执行规则

- 当前工作区包含 GLM 的未提交修改；只修改本计划涉及的文件，不执行 reset、checkout 或大范围格式化。
- 修改函数、类或方法前，先运行 GitNexus impact，方向为 upstream，记录调用者、执行流和风险。
- 每个新行为遵循 RED → GREEN：先添加复现问题的失败测试，再写最小实现。
- 每个阶段完成后运行该阶段测试；全部阶段完成后运行全量测试、compileall、detect_changes，并补充审查报告。
- 不在本计划中提交 Git commit，只留下可审查的工作区修改和验证结果。

## 文件责任地图

| 文件 | 责任 |
|---|---|
| tradingagents/application/service.py | run_id、resume_payload、安全审计和 abandoned 产物 |
| tradingagents/graph/trading_graph.py | LangGraph Command resume 和暂停边界 |
| cli/analyze/run_impl.py | HumanGate comment/proceed/abort 适配 |
| tradingagents/application/events.py | 安全过滤和中止状态的稳定事件 |
| tradingagents/agents/utils/untrusted_wrap.py | run-scoped 盐、过滤、审计 |
| tradingagents/dataflows/interface.py、rag_news_tools.py | 新闻/RAG 文本统一包装 |
| tradingagents/agents/utils/portfolio_context.py | YAML 组合配置和校验 |
| tradingagents/agents/utils/decision_constraints.py | B3/B5 纯函数校验 |
| tradingagents/agents/utils/exchange_rules.py | A 股规则配置和输出检查 |
| tradingagents/graph/setup.py | PM 后约束校验接线 |
| tradingagents/agents/utils/evidence_verifier.py | verified/derived/unverified 和时间证据 |
| tradingagents/dataflows/alpha_vantage_common.py | E3 日期异常路径 |
| tradingagents/screener/vendor_http.py | E2 Retry-After、退避和 403 |
| tests/test_handoff_fixes.py | 新增接力修复测试 |

---

## Task 0：建立基线和变更边界

文件：
- 读取 docx/开发文件/审查报告-8-AI-Agent工程深化一周计划-GLM完成情况.md
- 读取本计划和当前 git diff
- 测试 existing tests

- [ ] Step 1：记录状态和基线。

~~~powershell
git status --short
git branch --show-current
venv\Scripts\python.exe -m pytest tests -q
~~~

预期：GLM 修改仍存在；基线为当前已知的 541 passed；若变化，先记录差异。

- [ ] Step 2：对第一批符号做 GitNexus 影响分析。

至少分析 AnalysisService.stream_events、AnalysisEventStream.__iter__、run_analysis、format_datetime_for_api、VendorHttp.tencent_direct、sanitize_untrusted、get_rag_news、create_constraint_enforcer_node。

- [ ] Step 3：固定阶段验证命令。

~~~powershell
venv\Scripts\python.exe -m pytest tests/test_handoff_fixes.py tests/test_run_resume.py tests/test_phase3.py -q
venv\Scripts\python.exe -m pytest tests -q
venv\Scripts\python.exe -m compileall -q tradingagents cli tests
~~~

---

## Task 1：修复 A5 HumanGate 应用层恢复和 abort 产物

文件：
- 修改 tradingagents/application/service.py
- 修改 tradingagents/graph/trading_graph.py
- 修改 cli/analyze/run_impl.py
- 测试 tests/test_handoff_fixes.py、tests/test_run_resume.py、tests/test_phase3.py

- [ ] Step 1：先写 service resume_payload 失败测试。

测试使用可注入 graph stub，断言 graph.stream_analysis 的关键字参数中存在同一个 payload：

~~~python
def test_service_forwards_human_gate_resume_payload(monkeypatch, tmp_path):
    from unittest.mock import MagicMock
    from tradingagents.application import service as service_module
    from tradingagents.application.contracts import AnalysisRequest
    from tradingagents.application.service import AnalysisService
    from tradingagents.graph.trading_graph import _AnalysisStream

    monkeypatch.setattr(service_module, "_PROJECT_ROOT", tmp_path)
    graph = MagicMock()
    graph.run_id = "a5resume1234"
    graph.debug = False
    graph.graph_setup.selected_analysts = ["market"]
    graph.propagator.create_initial_state.return_value = {"messages": []}
    graph.propagator.get_graph_args.return_value = {"stream_mode": "values", "config": {}}
    graph.graph.stream.return_value = iter([{"messages": [], "final_trade_decision": "BUY"}])
    graph._ensure_structured_state.side_effect = lambda state: dict(state)
    graph.process_signal.return_value = "BUY"
    graph.stream_analysis.side_effect = lambda *a, **kw: _AnalysisStream(
        graph, "600519", "2026-08-20",
        resume=kw["resume"], resume_payload=kw.get("resume_payload")
    )

    service = AnalysisService.__new__(AnalysisService)
    service._graph_factory = lambda: (lambda *a, **kw: graph)
    service._debug = False
    payload = {"action": "comment", "text": "注意批价风险"}
    stream = service.stream_events(
        AnalysisRequest(ticker="600519", trade_date="2026-08-20"),
        run_id="a5resume1234", resume=True, resume_payload=payload,
    )
    list(stream)
    assert graph.stream_analysis.call_args.kwargs["resume_payload"] == payload
~~~

- [ ] Step 2：运行该测试，预期当前以 unexpected keyword argument resume_payload 失败。

~~~powershell
venv\Scripts\python.exe -m pytest tests/test_handoff_fixes.py::test_service_forwards_human_gate_resume_payload -q
~~~

- [ ] Step 3：做最小透传修复。

给 AnalysisService.stream_events、AnalysisEventStream.__init__ 增加 resume_payload；保存到流对象；调用 graph.stream_analysis 时同时传入 resume 和 resume_payload。保持普通新运行和 AnalysisService.resume_run 的行为不变。

- [ ] Step 4：增加 abandoned.json 测试和实现。

增加 AnalysisEventStream.mark_abandoned(reason, choice)，写入 run_id、ticker、trade_date、choice、reason、costs 和时间戳。CLI 的 abort 分支调用它并返回 decision 为 ABORTED，不能继续执行要求最终决策存在的 assert。

- [ ] Step 5：覆盖 comment、proceed、abort 三条应用层行为。

comment 必须进入 human_override_comment；proceed 必须复用同一 run_id；abort 必须只有 abandoned artifact，不产生伪造交易决策；auto 模式保持无 interrupt。

- [ ] Step 6：运行 A5/E1 测试。

~~~powershell
venv\Scripts\python.exe -m pytest tests/test_handoff_fixes.py tests/test_run_resume.py tests/test_phase3.py -q
~~~

---

## Task 2：修复 E3 Alpha Vantage 回归并补供应商重试语义

文件：
- 修改 tradingagents/dataflows/alpha_vantage_common.py
- 修改 tradingagents/screener/vendor_http.py
- 测试 tests/test_handoff_fixes.py、tests/test_data_reliability.py

- [ ] Step 1：写日期异常分支测试。

~~~python
def test_alpha_vantage_accepts_datetime_string_after_date_parse_miss():
    from tradingagents.dataflows.alpha_vantage_common import format_datetime_for_api
    assert format_datetime_for_api("2024-01-15 14:30") == "20240115T1430"
~~~

- [ ] Step 2：运行失败测试，确认当前是 logger 未定义。

~~~powershell
venv\Scripts\python.exe -m pytest tests/test_handoff_fixes.py::test_alpha_vantage_accepts_datetime_string_after_date_parse_miss -q
~~~

- [ ] Step 3：把 logging import 和 logger 定义放到模块可执行区域，删除误插入文档字符串的代码，保留日期格式和最终 ValueError 语义。

- [ ] Step 4：写供应商测试，覆盖连接错误重试、Retry-After 不小于响应值、403 单次尝试、随机抖动；所有 sleep 使用 monkeypatch。

- [ ] Step 5：实现供应商最小修复。429 不重复请求但记录明确 retry_after 长退避告警；连接/超时退避使用配置值和随机抖动；403 直接熔断当前调用，不新增重试。

- [ ] Step 6：运行 E2/E3 测试。

~~~powershell
venv\Scripts\python.exe -m pytest tests/test_handoff_fixes.py tests/test_data_reliability.py -q
~~~

---

## Task 3：补齐 A6 run-scoped 注入防御和 RAG 绕过

文件：
- 修改 tradingagents/agents/utils/untrusted_wrap.py
- 修改 tradingagents/dataflows/interface.py
- 修改 tradingagents/agents/utils/rag_news_tools.py
- 修改 tradingagents/application/service.py、events.py
- 测试 tests/test_handoff_fixes.py、tests/test_phase3.py、tests/test_tool_contracts.py

- [ ] Step 1：先写 run-scoped salt、RAG 直返和审计失败测试。

测试要求：两个不同 run_id 必须生成不同 salt；过滤一次后 audit 的 filtered_count 为 1；RAG retriever 直接命中时仍有定界符和 injection_filtered。

- [ ] Step 2：运行失败测试。

~~~powershell
venv\Scripts\python.exe -m pytest tests/test_handoff_fixes.py -k "security or rag" -q
~~~

- [ ] Step 3：在 untrusted_wrap.py 增加 ContextVar 安全上下文，提供 start_security_context(run_id)、finish_security_context()、sanitize_untrusted；每个 context 生成新 salt，审计只保存 source、计数和脱敏摘要，不保存完整攻击正文。

- [ ] Step 4：get_rag_news 和 get_rag_sector_news 在 format_for_llm_context 后统一调用 sanitize_untrusted；vendor 路由继续由 interface 包装。

- [ ] Step 5：AnalysisEventStream 在流开始建立 context，在正常结束和异常结束落盘 security_audit.json，包含 run_id、salt、filtered_count、entries；过滤命中转为 TimelineNoted，不泄漏原始攻击文本。

- [ ] Step 6：运行 A6 回归测试。

~~~powershell
venv\Scripts\python.exe -m pytest tests/test_handoff_fixes.py tests/test_phase3.py tests/test_tool_contracts.py -q
~~~

---

## Task 4：将 B3 组合上下文升级为 YAML 和硬约束

文件：
- 修改 tradingagents/agents/utils/portfolio_context.py
- 新建 tradingagents/agents/utils/decision_constraints.py
- 修改 tradingagents/graph/setup.py
- 修改 tradingagents/application/service.py
- 测试 tests/test_handoff_fixes.py、tests/test_phase3.py

- [ ] Step 1：写 YAML loader 和硬钳制失败测试。

测试 YAML 包含 600519、weight 0.08、industry 白酒，以及 max_single 0.10、max_industry 0.30、cash_ratio 0.20；断言 YAML 可加载、总仓位超过 100% 和负仓位被拒绝，单票/行业/现金超限产生修正和审计。

- [ ] Step 2：运行失败测试。

~~~powershell
venv\Scripts\python.exe -m pytest tests/test_handoff_fixes.py -k "portfolio or constraint" -q
~~~

- [ ] Step 3：优先读取 ~/.tradingagents/portfolio.yaml；不存在时兼容旧 portfolio.json 并记录迁移 warning。校验 ticker、weight、industry，拒绝负数和总和超过 1，约束值只接受 0 到 1 之间。

- [ ] Step 4：新增纯函数：

~~~python
def extract_position_proposals(text: str) -> list[dict]: ...
def enforce_portfolio_constraints(text: str, portfolio: dict) -> tuple[str, list[dict]]: ...
~~~

支持现有中文仓位表达、position XML 和 position: 35% 文本。只有能确定原始数字时才修正；修正记录 field、proposed、cap、reason。

- [ ] Step 5：把纯函数接入 ConstraintEnforcer，保留现有 max_single 审计字段和无组合配置时的 no-op。

- [ ] Step 6：运行 B3 测试。

~~~powershell
venv\Scripts\python.exe -m pytest tests/test_handoff_fixes.py tests/test_phase3.py -k "portfolio or constraint" -q
~~~

---

## Task 5：将 B5 A 股规则升级为输出校验

文件：
- 修改 tradingagents/agents/utils/exchange_rules.py
- 修改 tradingagents/agents/utils/decision_constraints.py
- 修改 tradingagents/graph/setup.py
- 测试 tests/test_handoff_fixes.py

- [ ] Step 1：写四个失败测试：卖出缺少 T+1 语义、价格超出涨跌停、建议价偏离收盘锚点超过 2%、盈亏平衡未使用 trade_date_close。

测试输入固定 trade_date_close=100.0，建议价 103.0/115.0，断言返回结构化 warning 和必要修正。

- [ ] Step 2：运行失败测试。

~~~powershell
venv\Scripts\python.exe -m pytest tests/test_handoff_fixes.py -k execution -q
~~~

- [ ] Step 3：优先读取 ~/.tradingagents/exchange_rules.yaml，兼容旧 JSON；新增纯函数 validate_execution_decision(decision, trade_date_close, segment, trade_date)，校验 T+1、涨跌停、收盘锚点、2% warning 和摩擦成本说明。anchor 缺失时输出 unverified warning，不猜价格。

- [ ] Step 4：从 state 的显式 trade_date_close 或 execution_context 读取锚定价；在 ConstraintEnforcer 中写入 orchestration.execution_rule_warnings，不能静默改写无法确定的价格。

- [ ] Step 5：运行 B5 测试。

~~~powershell
venv\Scripts\python.exe -m pytest tests/test_handoff_fixes.py -k execution -q
~~~

---

## Task 6：补 A4/B2 的时间证据和请求日期边界

文件：
- 修改 tradingagents/agents/utils/evidence_verifier.py
- 修改 tradingagents/application/contracts.py
- 修改 tradingagents/application/service.py
- 修改 tradingagents/dataflows/interface.py
- 测试 tests/test_handoff_fixes.py、tests/test_evidence_verifier.py

- [ ] Step 1：写时间错配、derived 和 future-date 失败测试。

ToolMessage metadata 使用 as_of=2026-08-19、source=vendor_a；请求 trade_date 使用未来日期；断言时间不匹配不得 verified，derived 必须单独标记，工具请求日期不得超过分析日期。

- [ ] Step 2：运行失败测试。

~~~powershell
venv\Scripts\python.exe -m pytest tests/test_handoff_fixes.py tests/test_evidence_verifier.py -k "time or derived or date" -q
~~~

- [ ] Step 3：扩展 Claim 和 VerificationResult，增加 derived 等级和 summary 计数；只有明确声明的确定性算术才可 derived，数值相等不能自动升级。

- [ ] Step 4：证据有 as_of 时要求 as_of 不晚于 request trade_date；缺少来源日期保持 unverified 并追加 warning，不删除或伪造工具正文。

- [ ] Step 5：在 AnalysisRequest/service 入口规范日期，未来日期钳制到当前日期并写 warning；数据工具路由使用 request trade_date 作为上界；B2 lint 增加未来数据和未声明来源时间措辞。

- [ ] Step 6：运行 A4/B2 测试。

~~~powershell
venv\Scripts\python.exe -m pytest tests/test_handoff_fixes.py tests/test_evidence_verifier.py -q
~~~

---

## Task 7：复核 A2/A3/E2/E7，全量验证并更新审查报告

文件：
- 读取 tradingagents/graph/setup.py、application/service.py、ui/summary.py
- 修改 docx/开发文件/审查报告-8-AI-Agent工程深化一周计划-GLM完成情况.md
- 测试 all tests

- [ ] Step 1：运行 convergence tests，确认强分歧加轮、弱分歧提前收敛、截断分数下限和 convergence_log；不改动已通过的 A2 逻辑。

- [ ] Step 2：统一 context_stats.json 阶段字段为 estimated_chars，同时保留 context_estimate 兼容读取；补离线 P75 计算测试，不用单次真实运行宣称已校准。

- [ ] Step 3：全量测试和静态检查。

~~~powershell
venv\Scripts\python.exe -m pytest tests -q
venv\Scripts\python.exe -m compileall -q tradingagents cli tests
git diff --check
~~~

- [ ] Step 4：运行 GitNexus detect_changes，核对受影响符号只涉及 Application、Graph、Dataflows、Agents Utils 和 Tests；出现意外文件或新的 HIGH/CRITICAL 影响时停止声称完成。

- [ ] Step 5：只有 API key、模型名、dotenv 加载和网络可用性明确时才做真实 API。先做 no-interactive headless run，再单独用 hitl 验证暂停。必须检查最终 reports 文件、message_tool.log、context_stats.json、security_audit.json、verification summary、run_id 一致性和非空最终决策。

- [ ] Step 6：在审查报告新增接力修复结果，逐项列出已修复、仍延期、测试命令、真实产物路径和未解决风险。只有证据齐全的项目才标记完成。
