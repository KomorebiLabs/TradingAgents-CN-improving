"""
模块文档: executor.py - 钩子执行器

================================================================================
特殊Python语法说明:
1. async/await 异步语法:
   - async def: 定义协程函数
   - await: 等待协程完成
   - asyncio.wait_for: 带超时的等待
   - asyncio.gather: 并发执行多个协程

2. httpx.AsyncClient:
   异步HTTP客户端库，用于发送HTTP请求。

3. shlex.quote/shlex:
   用于安全地转义Shell命令参数，防止注入攻击。

4. subprocess.PIPE:
   异步子进程的标准输入/输出/错误管道。

5. json.dumps with ensure_ascii:
   将Python对象序列化为JSON字符串，ensure_ascii=False保留Unicode字符。
================================================================================

功能说明:
    钩子执行器负责实际运行各种类型的钩子：
    - CommandHook: 执行Shell命令
    - HttpHook: 发送HTTP请求
    - PromptHook: 使用AI模型验证
    - AgentHook: 使用AI模型深度分析
    
    执行器接收事件和上下文，协调各种钩子的运行。
"""

from __future__ import annotations

import asyncio
import fnmatch
import json
import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from openharness.api.client import ApiMessageCompleteEvent, ApiMessageRequest, SupportsStreamingMessages
from openharness.engine.messages import ConversationMessage
from openharness.hooks.events import HookEvent
from openharness.hooks.loader import HookRegistry
from openharness.hooks.schemas import (
    AgentHookDefinition,
    CommandHookDefinition,
    HookDefinition,
    HttpHookDefinition,
    PromptHookDefinition,
)
from openharness.hooks.types import AggregatedHookResult, HookResult
from openharness.sandbox import SandboxUnavailableError
from openharness.utils.shell import create_shell_subprocess


# =============================================================================
# 钩子执行上下文
# =============================================================================

@dataclass
class HookExecutionContext:
    """
    =============================================================================
    类文档: HookExecutionContext - 钩子执行上下文

    作用说明:
        传递给钩子执行的全局上下文信息。
        钩子可能需要访问当前工作目录、API客户端等信息。

    字段说明:
        cwd: 当前工作目录
        api_client: API客户端（用于Prompt/Agent钩子调用AI）
        default_model: 默认使用的AI模型
    =============================================================================
    """
    cwd: Path
    api_client: SupportsStreamingMessages
    default_model: str


# =============================================================================
# 钩子执行器类
# =============================================================================

class HookExecutor:
    """
    =============================================================================
    类文档: HookExecutor - 钩子执行器

    作用说明:
        协调和管理钩子的执行。当引擎触发一个事件时，
        执行器负责找出所有注册的钩子，逐一执行，并聚合结果。

    为什么需要执行器:
        1. 统一入口：所有钩子类型都通过同一个接口执行
        2. 结果聚合：多个钩子的结果需要统一处理
        3. 错误处理：单个钩子失败不应影响其他钩子

    使用流程:
        1. 创建HookRegistry和HookExecutionContext
        2. 创建HookExecutor实例
        3. 调用executor.execute(event, payload)执行钩子
        4. 检查返回的AggregatedHookResult
    =============================================================================
    """

    def __init__(self, registry: HookRegistry, context: HookExecutionContext) -> None:
        """
        初始化说明:
            绑定注册表和执行上下文。
        """
        self._registry = registry
        self._context = context

    def update_registry(self, registry: HookRegistry) -> None:
        """
        =============================================================================
        方法文档: update_registry - 替换钩子注册表

        用途:
            当配置更新时，替换活跃的钩子注册表。
            支持热重载钩子配置。
        =============================================================================
        """
        self._registry = registry

    def update_context(
        self,
        *,
        api_client: SupportsStreamingMessages | None = None,
        default_model: str | None = None,
    ) -> None:
        """
        =============================================================================
        方法文档: update_context - 更新执行上下文

        用途:
            更新API客户端或默认模型（如切换AI模型时）。
        =============================================================================
        """
        if api_client is not None:
            self._context.api_client = api_client
        if default_model is not None:
            self._context.default_model = default_model

    async def execute(self, event: HookEvent, payload: dict[str, Any]) -> AggregatedHookResult:
        """
        =============================================================================
        核心方法文档: execute - 执行事件的所有匹配钩子

        参数说明:
            event: 触发的事件类型
            payload: 事件携带的数据（tool_name, tool_input等）

        返回值:
            AggregatedHookResult - 聚合所有钩子的执行结果

        执行流程:
            1. 从注册表获取该事件的所有钩子
            2. 过滤不匹配的钩子（检查matcher）
            3. 根据钩子类型分发给对应的执行方法
            4. 聚合所有结果并返回

        为什么需要聚合:
            多个钩子可能对同一事件响应，需要统一判断是否阻止操作。
        =============================================================================
        """
        results: list[HookResult] = []
        for hook in self._registry.get(event):
            # 检查matcher过滤条件
            if not _matches_hook(hook, payload):
                continue
            # 分发到对应的执行方法
            if isinstance(hook, CommandHookDefinition):
                results.append(await self._run_command_hook(hook, event, payload))
            elif isinstance(hook, HttpHookDefinition):
                results.append(await self._run_http_hook(hook, event, payload))
            elif isinstance(hook, PromptHookDefinition):
                results.append(await self._run_prompt_like_hook(hook, event, payload, agent_mode=False))
            elif isinstance(hook, AgentHookDefinition):
                results.append(await self._run_prompt_like_hook(hook, event, payload, agent_mode=True))
        return AggregatedHookResult(results=results)

    async def _run_command_hook(
        self,
        hook: CommandHookDefinition,
        event: HookEvent,
        payload: dict[str, Any],
    ) -> HookResult:
        """
        =============================================================================
        方法文档: _run_command_hook - 执行Shell命令钩子

        实现说明:
            1. 将$ARGUMENTS替换为payload的JSON序列化
            2. 创建子进程执行命令
            3. 设置环境变量传递事件信息
            4. 等待命令完成或超时
            5. 返回执行结果

        环境变量:
            OPENHARNESS_HOOK_EVENT: 事件名称
            OPENHARNESS_HOOK_PAYLOAD: payload的JSON序列化
        =============================================================================
        """
        command = _inject_arguments(hook.command, payload, shell_escape=True)
        try:
            process = await create_shell_subprocess(
                command,
                cwd=self._context.cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={
                    **os.environ,  # 继承当前环境变量
                    "OPENHARNESS_HOOK_EVENT": event.value,
                    "OPENHARNESS_HOOK_PAYLOAD": json.dumps(payload),
                },
            )
        except SandboxUnavailableError as exc:
            return HookResult(
                hook_type=hook.type,
                success=False,
                blocked=hook.block_on_failure,
                reason=str(exc),
            )

        try:
            # 等待命令完成，设置超时
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=hook.timeout_seconds,
            )
        except asyncio.TimeoutError:
            # 超时杀死进程
            process.kill()
            await process.wait()
            return HookResult(
                hook_type=hook.type,
                success=False,
                blocked=hook.block_on_failure,
                reason=f"command hook timed out after {hook.timeout_seconds}s",
            )

        # 合并stdout和stderr
        output = "\n".join(
            part for part in (
                stdout.decode("utf-8", errors="replace").strip(),
                stderr.decode("utf-8", errors="replace").strip(),
            ) if part
        )
        success = process.returncode == 0
        return HookResult(
            hook_type=hook.type,
            success=success,
            output=output,
            blocked=hook.block_on_failure and not success,
            reason=output or f"command hook failed with exit code {process.returncode}",
            metadata={"returncode": process.returncode},
        )

    async def _run_http_hook(
        self,
        hook: HttpHookDefinition,
        event: HookEvent,
        payload: dict[str, Any],
    ) -> HookResult:
        """
        =============================================================================
        方法文档: _run_http_hook - 执行HTTP钩子

        实现说明:
            使用httpx发送异步POST请求到配置的URL。
            请求体包含事件名和payload。
        """
        try:
            async with httpx.AsyncClient(timeout=hook.timeout_seconds) as client:
                response = await client.post(
                    hook.url,
                    json={"event": event.value, "payload": payload},
                    headers=hook.headers,
                )
            success = response.is_success
            output = response.text
            return HookResult(
                hook_type=hook.type,
                success=success,
                output=output,
                blocked=hook.block_on_failure and not success,
                reason=output or f"http hook returned {response.status_code}",
                metadata={"status_code": response.status_code},
            )
        except Exception as exc:
            return HookResult(
                hook_type=hook.type,
                success=False,
                blocked=hook.block_on_failure,
                reason=str(exc),
            )

    async def _run_prompt_like_hook(
        self,
        hook: PromptHookDefinition | AgentHookDefinition,
        event: HookEvent,
        payload: dict[str, Any],
        *,
        agent_mode: bool,
    ) -> HookResult:
        """
        =============================================================================
        方法文档: _run_prompt_like_hook - 执行AI验证钩子

        实现说明:
            1. 构建验证提示，将payload注入
            2. 调用AI模型执行验证
            3. 解析AI返回的JSON结果
            4. 根据结果返回HookResult

        提示构建:
            前缀包含验证指令和JSON格式要求。
            agent_mode提供更详细的分析提示。
        """
        prompt = _inject_arguments(hook.prompt, payload)
        # 构建验证前缀
        prefix = (
            "You are validating whether a hook condition passes in OpenHarness. "
            "Return strict JSON: {\"ok\": true} or {\"ok\": false, \"reason\": \"...\"}."
        )
        if agent_mode:
            prefix += " Be more thorough and reason over the payload before deciding."
        
        # 构建API请求
        request = ApiMessageRequest(
            model=hook.model or self._context.default_model,
            messages=[ConversationMessage.from_user_text(prompt)],
            system_prompt=prefix,
            max_tokens=512,
        )

        # 执行API调用
        text_chunks: list[str] = []
        final_event: ApiMessageCompleteEvent | None = None
        async for event_item in self._context.api_client.stream_message(request):
            if isinstance(event_item, ApiMessageCompleteEvent):
                final_event = event_item
            else:
                text_chunks.append(event_item.text)

        # 获取最终文本
        text = "".join(text_chunks)
        if final_event is not None and final_event.message.text:
            text = final_event.message.text

        # 解析JSON结果
        parsed = _parse_hook_json(text)
        if parsed["ok"]:
            return HookResult(hook_type=hook.type, success=True, output=text)
        return HookResult(
            hook_type=hook.type,
            success=False,
            output=text,
            blocked=hook.block_on_failure,
            reason=parsed.get("reason", "hook rejected the event"),
        )


# =============================================================================
# 辅助函数
# =============================================================================

def _matches_hook(hook: HookDefinition, payload: dict[str, Any]) -> bool:
    """
    =============================================================================
    函数文档: _matches_hook - 检查钩子是否匹配payload

    实现说明:
        如果钩子没有matcher，始终匹配。
        否则根据matcher模式匹配payload中的相关字段。
        
        匹配字段优先级: tool_name > prompt > event
    """
    matcher = getattr(hook, "matcher", None)
    if not matcher:
        return True
    # 尝试从payload中提取匹配目标
    subject = str(payload.get("tool_name") or payload.get("prompt") or payload.get("event") or "")
    return fnmatch.fnmatch(subject, matcher)


def _inject_arguments(
    template: str, payload: dict[str, Any], *, shell_escape: bool = False
) -> str:
    """
    =============================================================================
    函数文档: _inject_arguments - 注入参数到模板

    参数说明:
        template: 包含$ARGUMENTS占位符的模板字符串
        payload: 要注入的数据
        shell_escape: 是否对JSON进行Shell转义

    作用说明:
        将payload序列化为JSON后替换模板中的$ARGUMENTS。
        shell_escape=True时使用shlex.quote转义，
        防止Shell注入攻击。
    """
    serialized = json.dumps(payload, ensure_ascii=True)
    if shell_escape:
        serialized = shlex.quote(serialized)
    return template.replace("$ARGUMENTS", serialized)


def _parse_hook_json(text: str) -> dict[str, Any]:
    """
    =============================================================================
    函数文档: _parse_hook_json - 解析钩子返回的JSON

    实现逻辑:
        1. 尝试解析标准JSON格式 {"ok": true/false}
        2. 如果失败，尝试简单值 "ok", "true", "yes"
        3. 如果都失败，返回失败结果
    """
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and isinstance(parsed.get("ok"), bool):
            return parsed
    except json.JSONDecodeError:
        pass
    lowered = text.strip().lower()
    if lowered in {"ok", "true", "yes"}:
        return {"ok": True}
    return {"ok": False, "reason": text.strip() or "hook returned invalid JSON"}
