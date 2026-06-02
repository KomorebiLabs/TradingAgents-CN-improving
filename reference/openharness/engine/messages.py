"""
√

模块文档: messages.py - 对话消息模型

================================================================================
特殊Python语法说明:
1. from __future__ import annotations:
   启用延迟注解，使类型注解作为字符串存在，避免循环导入问题

2. Pydantic相关语法:
   - BaseModel: Pydantic的基类，自动进行数据验证和类型转换
   - Field(): 用于定义字段的元数据和默认值
   - field_validator(): 自定义字段验证器，mode="before"表示在验证前执行
   - Annotated[..., Field(discriminator="type")]: 联合类型的判别器模式，
     用于在运行时根据type字段区分不同的子类型

3. typing.Annotated:
   用于给类型添加元数据标签，这里用于定义discriminator（判别器），
   让Pydantic能够识别JSON中的type字段来决定使用哪个具体的数据模型

4. Literal["text"]: Python 3.8+的类型字面量，
   限制变量只能是指定的字面量值，用于表示枚举式的字符串常量

5. uuid4(): 生成唯一的UUID（通用唯一标识符），用于生成唯一的工具调用ID

6. Annotated：是协议输出层。它把 Python 约束打包成 JSON Schema 给 AI 看，让 AI “守规矩”。

7. Discriminator：是协议输入层。它让程序在接收 AI 返回的杂乱数据时，能够靠一个“标签字段”实现精准、快速的自动化分类。
================================================================================

功能说明:
    这个模块定义了与AI对话引擎相关的各种消息内容块和数据模型。
    消息被组织为"内容块"(ContentBlock)的列表，每个内容块可以是：
    - 纯文本 (TextBlock)
    - 图片数据 (ImageBlock)  
    - 工具调用请求 (ToolUseBlock)
    - 工具执行结果 (ToolResultBlock)
    
    这些模型用于标准化API调用和对话历史的格式。
"""

import base64
import mimetypes
from pathlib import Path
from typing import Any, Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# 内容块类型定义
# =============================================================================

class TextBlock(BaseModel):
    """
    =============================================================================
    类文档: TextBlock - 纯文本内容块

    数据结构说明:
        包含纯文本内容的最基本内容块类型。没有额外的元数据或格式信息。

    字段说明:
        - type: 固定为"text"，用于API序列化时标识类型
        - text: 实际的文本内容，可以是任意字符串

    为什么需要这个类:
        AI回复的主要内容通常都是文本，这个类提供了标准化的文本表示方式，
        便于在对话中传递和处理文本内容。
    =============================================================================
    """
    type: Literal["text"] = "text"
    text: str


class ImageBlock(BaseModel):
    """
    =============================================================================
    类文档: ImageBlock - 图片内容块

    数据结构说明:
        用于在多模态AI模型中传输图片数据。图片被转换为base64编码的字符串，
        可以直接嵌入到API请求中发送。

    字段说明:
        - type: 固定为"image"
        - media_type: 图片的MIME类型，如"image/png"、"image/jpeg"
        - data: base64编码后的图片数据（ASCII字符串格式）
        - source_path: 可选，原始图片文件的路径，用于追踪来源

    为什么需要这个类:
        1. 多模态支持：现代AI模型如Claude/GPT-4V能理解图片内容
        2. 离线处理：图片base64编码后可离线传输，不需要URL
        3. 隐私保护：图片数据直接嵌入请求，不依赖外部URL
    =============================================================================
    """

    type: Literal["image"] = "image"
    media_type: str
    data: str
    source_path: str = ""

    @classmethod
    def from_path(cls, path: str | Path) -> "ImageBlock":
        """
        =============================================================================
        方法文档: from_path - 从文件路径创建图片块

        参数说明:
            path: 文件路径，可以是字符串或Path对象，支持~扩展用户目录

        返回值:
            ImageBlock - 包含完整图片数据的新实例

        作用说明:
            读取本地图片文件，将其转换为可发送的ImageBlock格式。
            这是将本地图片加载到对话中的标准入口方法。

        实现逻辑:
            1. 解析并展开路径（支持~表示用户目录）
            2. 使用mimetypes.guess_type猜测MIME类型，验证是否为图片
            3. 读取文件二进制内容
            4. base64编码为ASCII字符串
            5. 创建包含所有数据的ImageBlock

        异常处理:
            ValueError: 当文件类型不是图片格式时抛出
        =============================================================================
        """
        resolved = Path(path).expanduser().resolve()
        media_type, _ = mimetypes.guess_type(str(resolved))
        if not media_type or not media_type.startswith("image/"):
            raise ValueError(f"Unsupported image attachment: {resolved}")
        payload = base64.b64encode(resolved.read_bytes()).decode("ascii")
        return cls(media_type=media_type, data=payload, source_path=str(resolved))


class ToolUseBlock(BaseModel):
    """
    =============================================================================
    类文档: ToolUseBlock - 工具调用请求块

    数据结构说明:
        表示AI模型请求执行某个工具的指令。AI通过这个结构告诉系统：
        "我需要执行某个工具，工具名是什么，需要什么参数"。

    字段说明:
        - type: 固定为"tool_use"
        - id: 唯一的工具调用ID，用于匹配后续的工具结果（格式: toolu_xxxx）
        - name: 要执行的工具名称，如"read_file"、"bash"等
        - input: 工具执行所需的参数字典

    为什么需要这个类:
        这是实现"函数调用"(Function Calling/Tool Use)功能的核心数据结构。
        AI不能直接执行代码，而是通过发送ToolUseBlock告诉系统需要什么操作，
        由系统负责实际执行工具并将结果返回给AI。
    =============================================================================
    """

    type: Literal["tool_use"] = "tool_use"
    id: str = Field(default_factory=lambda: f"toolu_{uuid4().hex}")
    name: str
    input: dict[str, Any] = Field(default_factory=dict)


class ToolResultBlock(BaseModel):
    """
    =============================================================================
    类文档: ToolResultBlock - 工具执行结果块

    数据结构说明:
        包含工具执行后的返回结果。当系统执行完AI请求的工具后，
        将结果包装成这个格式返回给AI，以便AI理解工具的执行情况。

    字段说明:
        - type: 固定为"tool_result"
        - tool_use_id: 对应的ToolUseBlock的ID，用于建立因果关系
        - content: 工具执行的实际输出内容（字符串格式）
        - is_error: 标记工具执行是否出错

    为什么需要这个类:
        1. 结果传递：让AI能够看到工具执行后的输出
        2. 错误处理：is_error标志让AI知道执行是否成功
        3. 关联追踪：通过tool_use_id关联到原始的调用请求
    =============================================================================
    """

    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str
    is_error: bool = False


# =============================================================================
# 联合类型定义 - 使用Annotated和discriminator实现类型安全的类型区分
# =============================================================================

# 特殊语法解释:
# ContentBlock = Annotated[TextBlock | ImageBlock | ToolUseBlock | ToolResultBlock, Field(discriminator="type")]
#
# 这创建了一个"Tagged Union"（标记联合类型）:
# - Annotated: 给类型添加元数据
# - Field(discriminator="type"): 告诉Pydantic根据JSON中的"type"字段
#   来确定应该解析为哪个具体的Block类型
# - 当收到 {"type": "text", "text": "..."} 时自动解析为TextBlock
# - 当收到 {"type": "image", ...} 时自动解析为ImageBlock
# 以此类推

ContentBlock = Annotated[
    TextBlock | ImageBlock | ToolUseBlock | ToolResultBlock,
    Field(discriminator="type"),
]


# =============================================================================
# 对话消息类
# =============================================================================

class ConversationMessage(BaseModel):
    """
    =============================================================================
    类文档: ConversationMessage - 对话消息

    数据结构说明:
        代表对话中的单条消息，可以是用户消息(role="user")或AI助手消息(role="assistant")。
        每条消息包含一个或多个内容块(ContentBlock)。

    字段说明:
        - role: 消息发送者角色，"user"或"assistant"
        - content: 内容块列表，可以包含文本、图片、工具调用、工具结果等

    为什么需要这个类:
        1. 统一接口：无论是用户输入还是AI回复，都用同样的数据结构表示
        2. 多模态支持：消息可以包含多种类型的内容
        3. API兼容：结构设计符合Anthropic/OpenAI等主流AI API的格式要求
    =============================================================================
    """

    role: Literal["user", "assistant"]
    content: list[ContentBlock] = Field(default_factory=list)

    @field_validator("content", mode="before")
    @classmethod
    def _normalize_content(cls, value: Any) -> list[Any]:
        """
        =============================================================================
        方法文档: _normalize_content - 内容规范化验证器

        特殊语法说明:
            @field_validator装饰器:
            - mode="before": 表示验证器在Pydantic的标准验证之前运行
            - @classmethod: 验证器是类方法，第一个参数是类本身

        参数说明:
            value: 原始输入值，可能是None、空列表或其他类型

        作用说明:
            处理历史兼容性和边界情况。当从外部恢复会话或接收异常数据时，
            确保content字段总是有效的列表格式，避免后续处理中的空指针异常。

        为什么需要这个验证器:
            某些旧版API或手动序列化的数据可能传入None作为content，
            直接赋值会导致后续代码需要额外的None检查。统一转换为空列表
            可以简化调用方的处理逻辑。
        =============================================================================
        """
        if value is None:
            return []
        return value

    @classmethod
    def from_user_text(cls, text: str) -> "ConversationMessage":
        """
        =============================================================================
        工厂方法文档: from_user_text - 从纯文本创建用户消息

        参数说明:
            text: 用户输入的纯文本字符串

        返回值:
            ConversationMessage - 包装好的用户消息对象

        作用说明:
            提供便捷的工厂方法，将简单的文本字符串快速转换为标准的消息格式。
            这是创建用户消息的常用快捷方式。

        等效代码:
            ConversationMessage(role="user", content=[TextBlock(text=text)])
        =============================================================================
        """
        return cls(role="user", content=[TextBlock(text=text)])

    @classmethod
    def from_user_content(cls, content: list[ContentBlock]) -> "ConversationMessage":
        """
        =============================================================================
        工厂方法文档: from_user_content - 从内容块创建用户消息

        参数说明:
            content: 已构造好的内容块列表

        返回值:
            ConversationMessage - 用户消息对象

        作用说明:
            当需要传递包含多种内容类型的消息时使用此方法，
            例如用户既发送文字又附带了图片。
        =============================================================================
        """
        return cls(role="user", content=list(content))


    @property
    #  @property —— 【属性伪装者】
    # 它的作用：
    # 它把一个方法（函数）变成一个只读属性。
    # 你在调用它时，不需要加括号 ()。直接属性调用
    def text(self) -> str:
        """
        =============================================================================
        属性文档: text - 获取消息中的纯文本内容

        返回值:
            str - 消息中所有文本块的拼接结果

        作用说明:
            提取消息中所有TextBlock的内容并拼接成一个大字符串。
            如果消息中有其他类型的内容块（图片、工具调用等），它们会被忽略。

        为什么需要这个属性:
            很多场景下只需要消息的文本部分（如日志记录、搜索匹配等），
            这个属性提供了便捷的访问方式。
        =============================================================================
        """
        return "".join(
            block.text for block in self.content if isinstance(block, TextBlock)
        )

    @property
    def tool_uses(self) -> list[ToolUseBlock]:
        """
        =============================================================================
        属性文档: tool_uses - 获取消息中的工具调用列表

        返回值:
            list[ToolUseBlock] - 消息中包含的所有工具调用块

        作用说明:
            筛选并返回消息中所有ToolUseBlock类型的块。
            通常用于AI助手的回复，检查AI请求执行哪些工具。

        典型使用场景:
            # 检查AI是否请求了文件读取操作
            if any(tool.name == "read_file" for tool in message.tool_uses):
                ...
        =============================================================================
        """
        return [block for block in self.content if isinstance(block, ToolUseBlock)]

    def to_api_param(self) -> dict[str, Any]:
        """
        =============================================================================
        方法文档: to_api_param - 转换为API参数字典

        返回值:
            dict[str, Any] - 符合AI API格式的消息参数字典

        作用说明:
            将内部的消息格式转换为API提供商（如Anthropic/OpenAI）期望的格式。
            不同API对消息格式有特定要求，这个方法负责做格式转换。

        为什么需要这个方法:
            - 内部使用的数据模型和外部API的格式可能不同：
            - 内部使用Pydantic模型，便于类型检查和验证
            - API期望dict格式，包含特定的字段名和结构
        =============================================================================
        """
        return {
            "role": self.role,
            "content": [serialize_content_block(block) for block in self.content],
        }

    def is_effectively_empty(self) -> bool:
        """
        =============================================================================
        方法文档: is_effectively_empty - 判断消息是否实质为空

        返回值:
            bool - True表示消息没有有效内容，False表示有实质内容

        作用说明:
            某些情况下消息可能包含内容块但实际上没有有用信息（如空文本、纯空白）。
            这个方法检查消息是否包含任何可用的实际内容。

        判断逻辑:
            - 如果content为空 -> 空
            - 如果包含文本块，但文本全是空白 -> 空
            - 如果包含图片、工具调用、工具结果 -> 非空
        =============================================================================
        """
        if self.content:
            for block in self.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    return False
                if isinstance(block, (ImageBlock, ToolUseBlock, ToolResultBlock)):
                    return False
        return True


# =============================================================================
# 对话历史处理函数
# =============================================================================

def sanitize_conversation_messages(messages: list[ConversationMessage]) -> list[ConversationMessage]:
    """
    =============================================================================
    函数文档: sanitize_conversation_messages - 清理和规范化对话历史

    参数说明:
        messages: 原始的对话历史列表

    返回值:
        list[ConversationMessage] - 清理后的安全对话历史

    作用说明:
        当从外部恢复对话历史或加载保存的会话时，可能存在格式不规范的数据。
        这个函数负责"消毒"处理，移除可能导致API调用失败的问题消息。

    为什么需要这个函数:
        对话历史在以下情况可能损坏：
        1. 会话中断：AI发送了tool_use但还没收到结果，会话就被保存了
        2. 空消息：某些情况下可能产生空的assistant消息
        3. 格式错误：从旧版本或手动编辑的会话文件加载时

        这些问题如果直接发送给API，可能导致：
        - OpenAI兼容API拒绝请求（tool_use必须有对应结果）
        - 模型产生不一致的响应
        - 会话状态混乱

    实现逻辑:
        1. 跳过空的assistant消息
        2. 检测不完整的tool调用链（tool_use没有对应的tool_result）
        3. 移除这些"悬空"的tool调用
        4. 返回干净的消息列表
    =============================================================================
    """
    sanitized: list[ConversationMessage] = []
    pending_tool_use_ids: set[str] = set()
    pending_tool_use_index: int | None = None

    for message in messages:
        if message.role == "assistant" and message.is_effectively_empty():
            continue

        tool_uses = message.tool_uses if message.role == "assistant" else []
        tool_results = [
            block for block in message.content if isinstance(block, ToolResultBlock)
        ] if message.role == "user" else []

        matched_pending_tool_results = False
        if pending_tool_use_ids:
            result_ids = {block.tool_use_id for block in tool_results}
            if message.role != "user" or not pending_tool_use_ids.issubset(result_ids):
                if pending_tool_use_index is not None and pending_tool_use_index < len(sanitized):
                    sanitized.pop(pending_tool_use_index)
                pending_tool_use_ids = set()
                pending_tool_use_index = None
            else:
                matched_pending_tool_results = True
                pending_tool_use_ids = set()
                pending_tool_use_index = None

        if message.role == "user" and tool_results and not matched_pending_tool_results:
            content = [
                block for block in message.content if not isinstance(block, ToolResultBlock)
            ]
            if not content:
                continue
            message = ConversationMessage(role="user", content=content)

        sanitized.append(message)

        if tool_uses:
            pending_tool_use_ids = {block.id for block in tool_uses}
            pending_tool_use_index = len(sanitized) - 1

    if pending_tool_use_ids and pending_tool_use_index is not None and pending_tool_use_index < len(sanitized):
        sanitized.pop(pending_tool_use_index)

    return sanitized


# =============================================================================
# 内容块序列化函数
# =============================================================================

def serialize_content_block(block: ContentBlock) -> dict[str, Any]:
    """
    =============================================================================
    函数文档: serialize_content_block - 序列化内容块为字典

    参数说明:
        block: ContentBlock - 任意类型的内容块

    返回值:
        dict[str, Any] - 符合API规范的字典格式

    作用说明:
        将Pydantic模型实例转换为API提供商期望的字典格式。
        每个内容块类型在API中有特定的序列化方式。

    序列化格式说明:
        TextBlock -> {"type": "text", "text": "..."}
        ImageBlock -> {"type": "image", "source": {"type": "base64", "media_type": "...", "data": "..."}}
        ToolUseBlock -> {"type": "tool_use", "id": "...", "name": "...", "input": {...}}
        ToolResultBlock -> {"type": "tool_result", "tool_use_id": "...", "content": "...", "is_error": bool}

    为什么需要这个函数:
        Pydantic模型的内部表示和API的wire format不同。
        例如ImageBlock存储为block.media_type，但API期望嵌套在source对象中。
    =============================================================================
    """
    if isinstance(block, TextBlock):
        return {"type": "text", "text": block.text}

    if isinstance(block, ImageBlock):
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": block.media_type,
                "data": block.data,
            },
        }

    if isinstance(block, ToolUseBlock):
        return {
            "type": "tool_use",
            "id": block.id,
            "name": block.name,
            "input": block.input,
        }

    return {
        "type": "tool_result",
        "tool_use_id": block.tool_use_id,
        "content": block.content,
        "is_error": block.is_error,
    }


# =============================================================================
# API响应转换函数
# =============================================================================

def assistant_message_from_api(raw_message: Any) -> ConversationMessage:
    """
    =============================================================================
    函数文档: assistant_message_from_api - 从API响应创建消息对象

    参数说明:
        raw_message: Any - API返回的原始消息对象（通常是SDK的类实例）

    返回值:
        ConversationMessage - 转换后的内部消息对象

    作用说明:
        将AI API SDK返回的原生消息对象转换为我们内部使用的ConversationMessage格式。
        处理API响应的兼容性问题，提取需要的数据字段。

    为什么需要这个函数:
        不同AI API SDK的返回格式不同：
        - Anthropic SDK: 消息是特定类的实例
        - OpenAI SDK: 可能是dict或对象
        
        这个函数提供一个统一的转换入口，屏蔽底层SDK的差异。

    字段访问模式说明:
        getattr(raw_message, "content", []) 的用法:
        - 安全地获取属性，如果不存在返回默认值
        - 避免AttributeError
        - 这是处理外部API响应的标准防御性编程模式
    =============================================================================
    """
    content: list[ContentBlock] = []

    for raw_block in getattr(raw_message, "content", []):
        block_type = getattr(raw_block, "type", None)
        if block_type == "text":
            content.append(TextBlock(text=getattr(raw_block, "text", "")))
        elif block_type == "tool_use":
            content.append(
                ToolUseBlock(
                    id=getattr(raw_block, "id", f"toolu_{uuid4().hex}"),
                    name=getattr(raw_block, "name", ""),
                    input=dict(getattr(raw_block, "input", {}) or {}),
                )
            )

    return ConversationMessage(role="assistant", content=content)
