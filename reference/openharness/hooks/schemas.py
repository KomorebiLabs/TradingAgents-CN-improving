"""
模块文档: schemas.py - 钩子配置Schema定义

================================================================================
特殊Python语法说明:
1. Pydantic BaseModel:
   数据验证和设置管理库，提供自动类型转换、验证和默认值。

2. Literal["command"] = "command":
   类型字面量，固定字段值。
   type字段必须是字面量"command"，用于API区分不同类型。

3. Field(default=30, ge=1, le=600):
   Pydantic字段元数据：
   - default: 默认值
   - ge: 最小值 (greater than or equal)
   - le: 最大值 (less than or equal)
================================================================================

功能说明:
    定义了四种钩子类型的配置模型。每种钩子类型有不同的执行方式：
    - CommandHookDefinition: 执行Shell命令
    - PromptHookDefinition: 让AI模型验证条件
    - HttpHookDefinition: 发送HTTP POST请求
    - AgentHookDefinition: 使用AI模型进行深度验证
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CommandHookDefinition(BaseModel):
    """
    =============================================================================
    类文档: CommandHookDefinition - Shell命令钩子

    作用说明:
        配置一个在事件触发时执行的Shell命令。
        命令会接收事件相关信息作为环境变量或参数。

    字段说明:
        type: 固定为"command"
        command: 要执行的Shell命令模板，支持$ARGUMENTS占位符
        timeout_seconds: 命令超时时间，默认30秒
        matcher: 可选的过滤器模式，只有payload匹配时才执行
        block_on_failure: 命令失败时是否阻止后续操作，默认False

    为什么需要Shell命令钩子:
        1. 集成现有脚本和工具
        2. 执行系统级操作
        3. 调用外部服务

    示例配置:
        type: command
        command: /usr/local/bin/my-hook.sh $ARGUMENTS
        timeout_seconds: 60
        matcher: "bash"
        block_on_failure: true
    =============================================================================
    """
    type: Literal["command"] = "command"
    command: str
    timeout_seconds: int = Field(default=30, ge=1, le=600)
    matcher: str | None = None
    block_on_failure: bool = False


class PromptHookDefinition(BaseModel):
    """
    =============================================================================
    类文档: PromptHookDefinition - 提示验证钩子

    作用说明:
        使用AI模型来验证事件条件是否满足。
        模型会收到一个提示，返回JSON格式的验证结果。

    字段说明:
        type: 固定为"prompt"
        prompt: 验证提示模板，支持$ARGUMENTS占位符
        model: 可选的模型名称，默认使用全局模型
        timeout_seconds: 超时时间，默认30秒
        matcher: 可选的过滤器模式
        block_on_failure: 验证失败时是否阻止，默认True

    为什么需要提示验证钩子:
        1. AI可以理解语义，做出复杂的决策
        2. 可以检查内容安全性、适当性
        3. 可以根据上下文灵活判断

    返回格式:
        {"ok": true} 或 {"ok": false, "reason": "..."}
    =============================================================================
    """
    type: Literal["prompt"] = "prompt"
    prompt: str
    model: str | None = None
    timeout_seconds: int = Field(default=30, ge=1, le=600)
    matcher: str | None = None
    block_on_failure: bool = True


class HttpHookDefinition(BaseModel):
    """
    =============================================================================
    类文档: HttpHookDefinition - HTTP钩子

    作用说明:
        向指定的HTTP端点发送POST请求，传递事件信息。
        适用于与外部Webhook服务或API集成。

    字段说明:
        type: 固定为"http"
        url: HTTP端点URL
        headers: 额外的HTTP请求头
        timeout_seconds: 请求超时时间，默认30秒
        matcher: 可选的过滤器模式
        block_on_failure: 请求失败时是否阻止，默认False

    请求体格式:
        {
            "event": "事件名",
            "payload": {事件数据}
        }

    为什么需要HTTP钩子:
        1. 与外部服务集成（Slack通知、GitHub Webhook）
        2. 发送到监控和告警系统
        3. 触发远程自动化流程
    =============================================================================
    """
    type: Literal["http"] = "http"
    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=30, ge=1, le=600)
    matcher: str | None = None
    block_on_failure: bool = False


class AgentHookDefinition(BaseModel):
    """
    =============================================================================
    类文档: AgentHookDefinition - Agent深度验证钩子

    作用说明:
        使用AI模型进行更深入的分析和验证。
        与PromptHookDefinition类似，但提供更长的执行时间和更详细的分析。

    字段说明:
        type: 固定为"agent"
        prompt: 验证提示模板
        model: 可选的模型名称
        timeout_seconds: 超时时间，默认60秒（比PromptHook更长）
        matcher: 可选的过滤器模式
        block_on_failure: 验证失败时是否阻止，默认True

    Agent vs Prompt钩子的区别:
        - Prompt: 快速、轻量级验证
        - Agent: 深度分析，可以进行多步推理

    使用场景:
        - 复杂的代码安全审计
        - 多步骤的合规性检查
        - 需要参考外部知识的验证
    =============================================================================
    """
    type: Literal["agent"] = "agent"
    prompt: str
    model: str | None = None
    timeout_seconds: int = Field(default=60, ge=1, le=1200)
    matcher: str | None = None
    block_on_failure: bool = True


# 联合类型别名 - 支持任意钩子类型
HookDefinition = (
    CommandHookDefinition
    | PromptHookDefinition
    | HttpHookDefinition
    | AgentHookDefinition
)
