"""
模块文档: events.py - 钩子事件类型定义

================================================================================
特殊Python语法说明:
1. from enum import Enum:
   枚举类型，用于定义一组命名的常量值。
   
2. class HookEvent(str, Enum):
   让枚举成员既是Enum又是str，可以直接比较和序列化。
   如 event == HookEvent.PRE_TOOL_USE 或 event == "pre_tool_use" 都可以。
================================================================================

功能说明:
    定义了OpenHarness支持的钩子事件类型。
    钩子是在引擎执行过程中的特定时刻调用的回调函数，
    允许外部代码注入自定义逻辑。
"""

from __future__ import annotations

from enum import Enum


class HookEvent(str, Enum):
    """
    =============================================================================
    类文档: HookEvent - 钩子事件枚举

    作用说明:
        定义了AI引擎执行过程中可以触发钩子的关键时刻。
        开发者可以注册回调函数，在这些时刻执行自定义逻辑。

    为什么需要钩子系统:
        1. 扩展性：无需修改核心代码即可添加功能
        2. 审计追踪：记录操作历史
        3. 自定义行为：修改或阻止操作执行
        4. 集成：与其他系统（如通知、日志、监控）集成

    事件说明:

        SESSION_START - 会话开始
            时机：用户开始新的对话会话时
            用途：初始化会话级资源、发送欢迎消息、记录会话开始
            
        SESSION_END - 会话结束
            时机：用户结束会话或会话超时时
            用途：清理资源、发送会话摘要、保存状态
            
        PRE_COMPACT - 压缩前
            时机：对话历史即将被压缩（总结）之前
            用途：在压缩前记录快照、发送通知
            
        POST_COMPACT - 压缩后
            时机：对话历史压缩完成之后
            用途：验证压缩结果、发送完成通知
            
        PRE_TOOL_USE - 工具执行前
            时机：工具即将执行之前
            用途：验证参数、阻止危险操作、发送通知
            特殊：可以通过返回blocked=True阻止工具执行
            
        POST_TOOL_USE - 工具执行后
            时机：工具执行完成之后（无论成功或失败）
            用途：记录执行结果、发送通知、清理资源
            
        USER_PROMPT_SUBMIT - 用户消息提交
            时机：用户发送消息后，AI处理之前
            用途：预处理用户输入、验证输入、发送通知
            
        NOTIFICATION - 通知事件
            时机：系统需要向用户显示通知时
            用途：转发通知到外部系统（如Slack、邮件）
            
        STOP - 停止事件
            时机：AI决定停止当前操作时
            用途：执行清理操作、发送停止通知
            
        SUBAGENT_STOP - 子代理停止
            时机：子代理（异步任务）完成或被停止时
            用途：协调器收到子代理完成通知后触发
    =============================================================================
    """

    SESSION_START = "session_start"
    SESSION_END = "session_end"
    PRE_COMPACT = "pre_compact"
    POST_COMPACT = "post_compact"
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    USER_PROMPT_SUBMIT = "user_prompt_submit"
    NOTIFICATION = "notification"
    STOP = "stop"
    SUBAGENT_STOP = "subagent_stop"
