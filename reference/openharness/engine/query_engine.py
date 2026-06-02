"""
模块文档: query_engine.py - 查询引擎核心类

================================================================================
特殊Python语法说明:
1. AsyncIterator[StreamEvent]:
   异步迭代器类型，表示一个可以异步产生StreamEvent序列的对象。
   使用 async for event in engine.submit_message(...) 来消费事件。

2. kwarg-only参数 (*, 参数名):
   在__init__中使用 (*, ...) 强制所有后续参数必须使用关键字参数调用。
   这是Python 3的强制关键字参数语法，提高代码可读性。

3. typing.TypeAlias:
   类型别名定义，提供更清晰的类型名称。

4. self._xxx 私有属性命名:
   单下划线前缀是Python的约定，表示"内部使用"，
   外部代码不应直接访问双下划线(__)会触发名称修饰。

5. property装饰器:
   将方法转换为"属性"，访问时不需要括号，如 obj.name 而非 obj.name()
================================================================================

功能说明:
    QueryEngine是整个对话引擎的核心类，负责：
    1. 维护对话历史(messages)
    2. 管理与AI API的交互
    3. 处理工具调用的生命周期
    4. 追踪API使用量和成本

这是一个状态机，管理着用户与AI之间的多轮对话循环。
"""

from __future__ import annotations

from pathlib import Path
from src.openharness.engine.messages import ConversationMessage
from typing import AsyncIterator

from openharness.api.client import SupportsStreamingMessages
from openharness.engine.cost_tracker import CostTracker
from openharness.coordinator.coordinator_mode import get_coordinator_user_context
from openharness.engine.messages import ConversationMessage, TextBlock, ToolResultBlock
from openharness.engine.query import AskUserPrompt, PermissionPrompt, QueryContext, remember_user_goal, run_query
from openharness.engine.stream_events import AssistantTurnComplete, StreamEvent
from openharness.hooks import HookEvent, HookExecutor
from openharness.permissions.checker import PermissionChecker
from openharness.tools.base import ToolRegistry


class QueryEngine:
    """
    =============================================================================
    类文档: QueryEngine - 对话查询引擎

    核心职责:
        QueryEngine是整个OpenHarness的核心引擎，负责协调用户输入、AI推理、
        工具执行和对话历史管理。它封装了复杂的异步逻辑，提供简洁的接口。

    为什么需要这个类:
        1. 复杂性封装：将多轮对话、工具调用、错误处理等复杂逻辑封装在一起
        2. 状态管理：维护对话状态（历史消息、配置参数）
        3. 事件驱动：通过AsyncIterator提供实时事件流
        4. 资源追踪：记录token使用量和成本

    生命周期:
        1. 创建实例（配置API客户端、工具注册表、权限检查器等）
        2. 多次调用submit_message进行多轮对话
        3. 调用clear()重置状态或销毁实例

    架构图示:
        User Input -> QueryEngine -> API Client -> AI Model
                                              |
                    +-------------------------+-------------------------+
                    |                         |                         |
              Tool Calls               Text Deltas                 Usage Stats
                    |                         |                         |
              Tool Registry                   |                    CostTracker
                    |                         |                         |
           Tool Execution                     v                         v
                    |              UI Updates (实时显示)             Billing
                    |
              Tool Results
                    |
                    v
              AI Model (下一轮)
    =============================================================================
    """

    def __init__(
        self,
        *,
        api_client: SupportsStreamingMessages,
        tool_registry: ToolRegistry,
        permission_checker: PermissionChecker,
        cwd: str | Path,
        model: str,
        system_prompt: str,
        max_tokens: int = 4096,
        context_window_tokens: int | None = None,
        auto_compact_threshold_tokens: int | None = None,
        max_turns: int | None = 8,
        permission_prompt: PermissionPrompt | None = None,
        ask_user_prompt: AskUserPrompt | None = None,
        hook_executor: HookExecutor | None = None,
        tool_metadata: dict[str, object] | None = None,
    ) -> None:
        """
        =============================================================================
        构造函数文档: __init__ - 初始化查询引擎

        参数说明:
            api_client: 支持流式消息的API客户端，负责与AI模型通信
            tool_registry: 工具注册表，管理和提供可用的工具
            permission_checker: 权限检查器，控制哪些操作被允许
            cwd: 当前工作目录，用于解析相对文件路径
            model: AI模型标识符，如"claude-3-opus-20240229"
            system_prompt: 系统提示词，定义AI的行为和角色
            max_tokens: 单次回复的最大token数限制
            context_window_tokens: 模型上下文窗口大小，用于计算压缩时机
            auto_compact_threshold_tokens: 自动压缩的token阈值
            max_turns: 单次用户输入允许的最大AI推理轮数
            permission_prompt: 权限请求回调函数
            ask_user_prompt: 向用户提问的回调函数
            hook_executor: 钩子执行器，用于扩展点
            tool_metadata: 工具元数据存储（跨调用持久化数据）

        为什么参数使用关键字:
            使用 * 强制关键字参数是为了：
            1. 提高可读性：调用时明确每个参数的意义
            2. 避免顺序错误：参数多时不至于混淆
            3. 便于扩展：新增可选参数不影响现有调用
        =============================================================================
        """
        self._api_client = api_client
        self._tool_registry = tool_registry
        self._permission_checker = permission_checker
        self._cwd = Path(cwd).resolve()
        self._model = model
        self._system_prompt = system_prompt
        self._max_tokens = max_tokens
        self._context_window_tokens = context_window_tokens
        self._auto_compact_threshold_tokens = auto_compact_threshold_tokens
        self._max_turns = max_turns
        self._permission_prompt = permission_prompt
        self._ask_user_prompt = ask_user_prompt
        self._hook_executor = hook_executor
        self._tool_metadata = tool_metadata or {}
        self._messages: list[ConversationMessage] = []
        self._cost_tracker = CostTracker()

    # =========================================================================
    # 属性访问器 - 提供只读访问内部状态
    # =========================================================================

    @property
    def messages(self) -> list[ConversationMessage]:
        """
        =============================================================================
        属性文档: messages - 获取对话历史

        返回值:
            list[ConversationMessage] - 对话消息列表的副本

        作用说明:
            提供对外的对话历史访问，返回列表的副本而非原列表，
            防止外部代码意外修改内部状态。

        为什么返回副本:
            类似于CostTracker的total属性，这是防御性编程，
            保证内部状态不会被外部污染。
        =============================================================================
        """
        return list(self._messages)

    @property
    def max_turns(self) -> int | None:
        """
        =============================================================================
        属性文档: max_turns - 获取最大轮数限制
        """
        return self._max_turns

    @property
    def api_client(self) -> SupportsStreamingMessages:
        """
        =============================================================================
        属性文档: api_client - 获取API客户端
        """
        return self._api_client

    @property
    def model(self) -> str:
        """
        =============================================================================
        属性文档: model - 获取当前模型标识
        """
        return self._model

    @property
    def system_prompt(self) -> str:
        """
        =============================================================================
        属性文档: system_prompt - 获取系统提示词
        """
        return self._system_prompt

    @property
    def tool_metadata(self) -> dict[str, object]:
        """
        =============================================================================
        属性文档: tool_metadata - 获取工具元数据

        返回值:
            dict[str, object] - 可变字典，外部代码可以修改

        为什么返回可变引用:
            tool_metadata被设计为跨调用持久化的状态存储，
            允许外部代码存储和读取需要保持的数据。
            如记住用户的目标、最近打开的文件等。
        =============================================================================
        """
        return self._tool_metadata

    @property
    def total_usage(self):
        """
        =============================================================================
        属性文档: total_usage - 获取总使用量

        返回值:
            UsageSnapshot - 累积的token使用量统计

        用途:
            用于显示给用户、计费、或设置使用上限。
        =============================================================================
        """
        return self._cost_tracker.total

    # =========================================================================
    # 状态修改方法
    # =========================================================================

    def clear(self) -> None:
        """
        =============================================================================
        方法文档: clear - 清空会话状态

        作用说明:
            重置引擎到初始状态，清空对话历史和累积的使用量。
            用于开始新的对话会话。

        为什么需要这个方法:
            用户可能想开始新的对话而不是继续之前的，
            需要一种方式清空所有状态。
        =============================================================================
        """
        self._messages.clear()
        self._cost_tracker = CostTracker()

    def set_system_prompt(self, prompt: str) -> None:
        """
        =============================================================================
        方法文档: set_system_prompt - 更新系统提示词

        参数说明:
            prompt: 新的系统提示词内容

        作用说明:
            动态修改AI的系统角色设定，影响后续所有对话。

        使用场景:
            - 切换AI的工作模式
            - 加载不同的系统指令
        =============================================================================
        """
        self._system_prompt = prompt

    def set_model(self, model: str) -> None:
        """
        =============================================================================
        方法文档: set_model - 切换AI模型

        使用场景:
            - 用户想用不同的模型
            - 根据任务复杂度选择不同模型
        =============================================================================
        """
        self._model = model

    def set_api_client(self, api_client: SupportsStreamingMessages) -> None:
        """
        =============================================================================
        方法文档: set_api_client - 更换API客户端

        使用场景:
            - 切换到不同的API提供商
            - 使用本地模型替代云端API
        =============================================================================
        """
        self._api_client = api_client

    def set_max_turns(self, max_turns: int | None) -> None:
        """
        =============================================================================
        方法文档: set_max_turns - 设置最大轮数

        参数说明:
            max_turns: 最大轮数，None表示不限制

        特殊处理:
            如果传入的值小于1，会被调整为1，防止无效配置。
        =============================================================================
        """
        self._max_turns = None if max_turns is None else max(1, int(max_turns))

    def set_permission_checker(self, checker: PermissionChecker) -> None:
        """
        =============================================================================
        方法文档: set_permission_checker - 更换权限检查器
        """
        self._permission_checker = checker

    # =========================================================================
    # 内部辅助方法
    # =========================================================================

    def _build_coordinator_context_message(self) -> ConversationMessage | None:
        """
        =============================================================================
        方法文档: _build_coordinator_context_message - 构建协调器上下文消息

        返回值:
            ConversationMessage | None - 包含协调器上下文的用户消息

        作用说明:
            当QueryEngine被用作协调器(Coordinator)模式时，
            需要将协调器的运行时上下文注入到查询中。

        为什么需要这个方法:
            协调器模式是一种多Agent协作架构，一个协调器负责管理多个工作器。
            上下文消息包含工作器状态、待处理任务等信息。

        返回None的情况:
            如果没有workerToolsContext（工作器工具上下文），返回None，
            表示不是协调器模式或没有需要传递的上下文。
        =============================================================================
        """
        context = get_coordinator_user_context()
        worker_tools_context = context.get("workerToolsContext")
        if not worker_tools_context:
            return None
        return ConversationMessage(
            role="user",
            content=[TextBlock(text=f"# Coordinator User Context\n\n{worker_tools_context}")],
        )

    def load_messages(self, messages: list[ConversationMessage]) -> None:
        """
        =============================================================================
        方法文档: load_messages - 加载对话历史

        参数说明:
            messages: 对话消息列表

        作用说明:
            用外部提供的消息列表替换内部对话历史。
            用于恢复之前保存的会话或加载会话模板。

        为什么复制列表:
            list(messages)创建副本，防止外部列表的后续修改影响内部状态。
        =============================================================================
        """
        self._messages = list[ConversationMessage](messages)

    def has_pending_continuation(self) -> bool:
        """
        =============================================================================
        方法文档: has_pending_continuation - 检查是否有待处理的继续

        返回值:
            bool - True表示有悬空的工具调用等待处理

        作用说明:
            检查对话是否处于"不完整"状态：
            1. 最后一条消息是用户消息
            2. 用户消息包含工具结果
            3. 之前的助手消息有工具调用但可能未完成

        为什么需要这个方法:
            检测会话是否被异常中断（如连接断开、保存了不完整状态），
            以便决定是否需要调用continue_pending()继续执行。
        =============================================================================
        """
        if not self._messages:
            return False
        last = self._messages[-1]
        if last.role != "user":
            return False
        if not any(isinstance(block, ToolResultBlock) for block in last.content):
            return False
        for msg in reversed(self._messages[:-1]):
            if msg.role != "assistant":
                continue
            return bool(msg.tool_uses)
        return False

    # =========================================================================
    # 核心异步交互方法
    # =========================================================================

    async def submit_message(self, prompt: str | ConversationMessage) -> AsyncIterator[StreamEvent]:
        """
        =============================================================================
        核心方法文档: submit_message - 提交用户消息并执行查询循环

        参数说明:
            prompt: 用户输入，可以是字符串或已构造的消息对象

        返回值:
            AsyncIterator[StreamEvent] - 异步事件迭代器，产生各种类型的事件

        作用说明:
            这是QueryEngine的核心方法，用户通过调用此方法提交消息，
            引擎会启动完整的查询循环：
            1. 创建用户消息
            2. 追加到对话历史
            3. 执行Hook（USER_PROMPT_SUBMIT）
            4. 调用run_query进行AI推理和工具执行
            5. 逐事件yield返回

        事件流:
            submit_message产生的典型事件序列：
            1. StatusEvent (如果auto-compact触发)
            2. AssistantTextDelta (AI逐字输出)
            3. ToolExecutionStarted (AI请求工具)
            4. ToolExecutionCompleted (工具执行完成)
            5. ... (可能多轮工具调用)
            6. AssistantTurnComplete (本轮结束)

        为什么使用AsyncIterator:
            1. 实时性：事件立即产生立即可见
            2. 内存效率：不需要等待完整结果
            3. 流式处理：支持大输出的逐步显示

        使用示例:
            async for event in engine.submit_message("帮我写一个排序算法"):
                if isinstance(event, AssistantTextDelta):
                    print(event.text, end="")
                elif isinstance(event, ToolExecutionStarted):
                    print(f"\n正在执行: {event.tool_name}")


        执行流程:

                用户发送 "帮我写排序算法"
                            │
                            ▼
        ┌─────────────────────────────────────────────────────┐
        │  submit_message() 做了什么：                          │
        │                                                     │
        │  1. 创建用户消息                                     │
        │     user_message = ConversationMessage(role="user")  │
        │                                                     │
        │  2. 记住用户目标                                      │
        │     remember_user_goal(prompt)                      │
        │                                                     │
        │  3. 追加到历史                                       │
        │     self._messages.append(user_message)              │
        │                                                     │
        │  4. 执行Hook                                        │
        │     hook_executor.execute(USER_PROMPT_SUBMIT)      │
        │                                                     │
        │  5. 构建QueryContext                                 │
        │     (封装所有配置：API客户端、工具注册表等)            │
        │                                                     │
        │  6. 调用 run_query() 开始AI推理                      │
        │     ┌─────────────────────────────────────────┐    │
        │     │  run_query 内部：                       │    │
        │     │  - 调用AI API                           │    │
        │     │  - 解析工具调用                          │    │
        │     │  - 执行工具                              │    │
        │     │  - 可能多轮循环                         │    │
        │     │  - yield 各种事件                       │    │
        │     └─────────────────────────────────────────┘    │
        │                                                     │
        │  7. 事件流输出 (yield)                              │
        └─────────────────────────────────────────────────────┘

        =============================================================================
        """
        # 处理输入：统一转换为ConversationMessage
        user_message = (
            prompt
            if isinstance(prompt, ConversationMessage)
            else ConversationMessage.from_user_text(prompt)
        )
        # 记住用户目标到元数据，供后续工具使用
        if user_message.text.strip():
            remember_user_goal(self._tool_metadata, user_message.text)
        self._messages.append(user_message)

        # 执行用户消息提交前的Hook
        if self._hook_executor is not None:
            await self._hook_executor.execute(
                HookEvent.USER_PROMPT_SUBMIT,
                {
                    "event": HookEvent.USER_PROMPT_SUBMIT.value,
                    "prompt": user_message.text,
                },
            )

        # 构建查询上下文
        context = QueryContext(
            api_client=self._api_client,
            tool_registry=self._tool_registry,
            permission_checker=self._permission_checker,
            cwd=self._cwd,
            model=self._model,
            system_prompt=self._system_prompt,
            max_tokens=self._max_tokens,
            context_window_tokens=self._context_window_tokens,
            auto_compact_threshold_tokens=self._auto_compact_threshold_tokens,
            max_turns=self._max_turns,
            permission_prompt=self._permission_prompt,
            ask_user_prompt=self._ask_user_prompt,
            hook_executor=self._hook_executor,
            tool_metadata=self._tool_metadata,
        )

        # 准备消息列表（可能需要添加协调器上下文）
        query_messages = list(self._messages)
        coordinator_context = self._build_coordinator_context_message()
        if coordinator_context is not None:
            query_messages.append(coordinator_context)

        # 执行查询循环，产出事件
        async for event, usage in run_query(context, query_messages):
            if isinstance(event, AssistantTurnComplete):
                self._messages = list(query_messages)
            if usage is not None:
                self._cost_tracker.add(usage)
            yield event

    """
    submit_message 产生的事件典型序列：

        [1] StatusEvent           ← "Auto-compacting..." (如果对话太长)
            │
            ▼
        [2] AssistantTextDelta  ← AI逐字输出 "我来帮你写..."
            │                       (可能有多个)
            ▼
        [3] ToolExecutionStarted ← "AI想调用 bash 工具"
            │
            ▼
        [4] ToolExecutionCompleted ← "工具执行完成，输出: ..."
            │
            ▼
        [5] (可能回到[2]，多轮工具调用)
            │
            ▼
        [6] AssistantTurnComplete ← "本轮AI回复完成"
    """




    async def continue_pending(self, *, max_turns: int | None = None) -> AsyncIterator[StreamEvent]:
        """
        =============================================================================
        核心方法文档: continue_pending - 继续未完成的工具循环

        参数说明:
            max_turns: 可选，覆盖默认的最大轮数限制

        返回值:
            AsyncIterator[StreamEvent] - 事件流

        作用说明:
            当会话有悬空(pending)的工具调用需要继续处理时，
            使用此方法继续执行，而不是提交新的用户消息。

        为什么需要这个方法:
            某些情况下，会话可能处于"等待继续"的状态：
            1. 网络中断后重连
            2. 用户保存了不完整状态
            3. Coordinator模式下的工作器回复

            这时候不应该再添加用户消息，而是继续执行悬空的逻辑。

        与submit_message的区别:
            - submit_message: 添加新的用户消息到历史
            - continue_pending: 不添加消息，继续处理现有状态


                        场景1: 网络中断
            ┌──────────────────────────────────────────┐
            │  用户: "写一个排序算法"                    │
            │  AI:  开始写代码...                        │
            │  ✗ 网络断开                               │
            │  (用户重新连接)                            │
            │  用户: 不发新消息，而是"继续上次的"          │
            │        ↓                                  │
            │  continue_pending()  ← 不添加新消息        │
            │  AI:  继续写代码...                        │
            └──────────────────────────────────────────┘

            场景2: Coordinator 模式
            ┌──────────────────────────────────────────┐
            │  Coordinator: "worker，去实现排序算法"      │
            │  Worker AI:  开始写...                    │
            │  Worker完成: 发送 <task-notification>      │
            │  Coordinator: 收到通知，调用              │
            │        ↓                                  │
            │  continue_pending()  ← Worker继续回复      │
            └──────────────────────────────────────────┘

            场景3: 保存/恢复会话
            ┌──────────────────────────────────────────┐
            │  用户正在进行复杂任务...                    │
            │  突然需要关闭程序                         │
            │  (状态被保存，包括对话历史)                │
            │  用户重新打开程序                         │
            │  用户: "继续之前的工作"                    │
            │        ↓                                  │
            │  continue_pending()  ← 继续执行          │
            └──────────────────────────────────────────┘
        =============================================================================
        """
        context = QueryContext(
            api_client=self._api_client,
            tool_registry=self._tool_registry,
            permission_checker=self._permission_checker,
            cwd=self._cwd,
            model=self._model,
            system_prompt=self._system_prompt,
            max_tokens=self._max_tokens,
            context_window_tokens=self._context_window_tokens,
            auto_compact_threshold_tokens=self._auto_compact_threshold_tokens,
            max_turns=max_turns if max_turns is not None else self._max_turns,
            permission_prompt=self._permission_prompt,
            ask_user_prompt=self._ask_user_prompt,
            hook_executor=self._hook_executor,
            tool_metadata=self._tool_metadata,
        )
        async for event, usage in run_query(context, self._messages):
            if usage is not None:
                self._cost_tracker.add(usage)
            yield event
