"""
模块文档: checker.py - 权限检查器

================================================================================
特殊Python语法说明:
1. @dataclass(frozen=True):
   frozen=True 使数据类实例不可变，创建后字段不能修改。
   这确保权限决策对象在多线程环境中是安全的。

2. fnmatch模块:
   文件名模式匹配模块，支持通配符如 *, ? 等。
   fnmatch.fnmatch(path, pattern) 判断路径是否匹配模式。

3. getattr/setattr动态属性访问:
   getattr(obj, 'attr', default) 安全获取属性，不存在返回默认值
   用于兼容不同格式的配置对象（dict vs 对象属性）

4. * 关键字参数强制:
   def evaluate(self, tool_name, *, is_read_only, ...):
   星号后的参数必须使用关键字传递，防止参数顺序混淆。
================================================================================

功能说明:
    权限检查器负责评估工具调用是否被允许执行。
    这是OpenHarness安全架构的核心组件，防止AI执行恶意操作。
    
安全分层设计:
    1. 内置敏感路径保护 - 始终生效，无法被覆盖
    2. 显式工具黑名单/白名单 - 用户配置
    3. 路径规则 - 基于文件路径的细粒度控制
    4. 命令模式 - bash命令的黑名单
    5. 权限模式 - 运行时行为控制
"""

from __future__ import annotations

import fnmatch
import logging
from dataclasses import dataclass

from openharness.config.settings import PermissionSettings
from openharness.permissions.modes import PermissionMode

log = logging.getLogger(__name__)


# =============================================================================
# 内置敏感路径模式 - 始终被阻止
# =============================================================================

# 这些路径模式用于保护高价值的凭据文件，防止LLM被引导执行恶意操作。
# 这些规则始终生效，不受用户配置或权限模式影响。
# 模式使用fnmatch语法，与query engine生成的绝对路径进行匹配。
SENSITIVE_PATH_PATTERNS: tuple[str, ...] = (
    # SSH相关文件和配置
    "*/.ssh/*",
    # AWS云服务凭据
    "*/.aws/credentials",
    "*/.aws/config",
    # GCP (Google Cloud Platform) 凭据
    "*/.config/gcloud/*",
    # Azure云凭据
    "*/.azure/*",
    # GPG加密密钥
    "*/.gnupg/*",
    # Docker容器凭据存储
    "*/.docker/config.json",
    # Kubernetes集群配置
    "*/.kube/config",
    # OpenHarness自身的凭据存储
    "*/.openharness/credentials.json",
    "*/.openharness/copilot_auth.json",
)


# =============================================================================
# 权限决策数据类
# =============================================================================

@dataclass(frozen=True)
class PermissionDecision:
    """
    =============================================================================
    类文档: PermissionDecision - 权限决策结果

    为什么需要这个类:
        当检查一个工具调用是否允许时，需要返回多个信息：
        - 是否允许执行 (allowed)
        - 是否需要用户确认 (requires_confirmation)
        - 拒绝/允许的原因 (reason)
        
        将这些封装成一个不可变对象，确保决策结果不会被意外修改。

    字段说明:
        allowed: 工具调用是否被允许
        requires_confirmation: 是否需要用户手动确认才能执行
        reason: 决策的原因说明，用于向用户展示或记录日志
    =============================================================================
    """
    allowed: bool
    requires_confirmation: bool = False
    reason: str = ""


@dataclass(frozen=True)
class PathRule:
    """
    =============================================================================
    类文档: PathRule - 路径权限规则

    用途:
        定义基于文件路径的权限规则。
        使用glob模式匹配，支持通配符。

    字段说明:
        pattern: glob模式字符串，如 "src/**/*.py" 或 "*.md"
        allow: True=允许访问，False=拒绝访问
    =============================================================================
    """
    pattern: str
    allow: bool  # True = allow, False = deny


# =============================================================================
# 权限检查器类
# =============================================================================

class PermissionChecker:
    """
    =============================================================================
    类文档: PermissionChecker - 权限检查器

    作用说明:
        根据配置的权限模式和规则，评估工具调用是否应该被执行。
        这是工具执行前的最后一道安全检查。

    为什么需要这个类:
        AI可以调用各种工具来操作系统资源。
        没有权限控制，AI可能意外或被引导执行危险操作（如删除文件、运行恶意命令）。
        权限检查器提供可控的安全边界。

    检查流程（按优先级从高到低）:
        1. 内置敏感路径保护 - 始终阻止
        2. 显式工具黑名单 - 用户配置的禁止工具列表
        3. 显式工具白名单 - 用户配置的允许工具列表
        4. 路径级别规则 - 基于文件路径的规则
        5. 命令模式 - bash命令黑名单
        6. 权限模式 - 运行时模式控制
        
    使用方式:
        decision = checker.evaluate(
            tool_name="bash",
            is_read_only=False,
            file_path="/home/user/project/src/main.py",
            command="rm -rf /",
        )
        if not decision.allowed:
            print(f"拒绝: {decision.reason}")
        elif decision.requires_confirmation:
            confirmed = await ask_user("是否允许执行?")
            if not confirmed:
                deny()
    =============================================================================
    """

    def __init__(self, settings: PermissionSettings) -> None:
        """
        =============================================================================
        构造函数文档: __init__ - 初始化权限检查器

        参数说明:
            settings: PermissionSettings - 权限配置对象

        实现说明:
            从settings中解析路径规则列表。
            支持两种格式的配置:
            - 对象属性格式: rule.pattern, rule.allow
            - 字典格式: {"pattern": "...", "allow": True}
        """
        self._settings = settings
        # 解析路径规则
        self._path_rules: list[PathRule] = []
        for rule in getattr(settings, "path_rules", []):
            # 兼容对象属性和字典两种格式
            pattern = getattr(rule, "pattern", None) or (rule.get("pattern") if isinstance(rule, dict) else None)
            allow = getattr(rule, "allow", True) if not isinstance(rule, dict) else rule.get("allow", True)
            if isinstance(pattern, str) and pattern.strip():
                self._path_rules.append(PathRule(pattern=pattern.strip(), allow=allow))
            else:
                log.warning(
                    "Skipping path rule with missing, empty, or non-string 'pattern' field: %r",
                    rule,
                )

    def evaluate(
        self,
        tool_name: str,
        *,
        is_read_only: bool,
        file_path: str | None = None,
        command: str | None = None,
    ) -> PermissionDecision:
        """
        =============================================================================
        核心方法文档: evaluate - 评估工具调用权限

        参数说明:
            tool_name: 工具名称，如 "read_file", "bash", "glob"
            is_read_only: 工具是否为只读操作
            file_path: 工具操作的文件路径（如果有）
            command: bash工具执行的命令（如果有）

        返回值:
            PermissionDecision - 权限决策结果

        作用说明:
            这是权限检查的入口方法，按顺序执行多层检查，
            直到做出最终决策。

        检查步骤详解:

        步骤1: 内置敏感路径保护
            检查file_path是否匹配SENSITIVE_PATH_PATTERNS中的任何模式。
            这是最高优先级，始终生效，即使FULL_AUTO模式也无法绕过。
            用于保护SSH密钥、云凭据等高价值资源。

        步骤2: 显式工具黑名单
            检查tool_name是否在settings.denied_tools列表中。
            如果是，直接拒绝并说明原因。

        步骤3: 显式工具白名单
            检查tool_name是否在settings.allowed_tools列表中。
            如果是，且不在黑名单中，直接允许。
            白名单优先于黑名单（如果同时配置）。

        步骤4: 路径级别规则
            如果配置了路径规则，检查file_path是否匹配。
            匹配deny规则 -> 拒绝
            匹配allow规则 -> 允许（但不会覆盖更上层的拒绝）

        步骤5: 命令模式检查
            对于bash工具，检查command是否匹配命令黑名单模式。
            如 "rm -rf /" 这样的危险命令会被阻止。

        步骤6: 权限模式决策
            - FULL_AUTO: 所有操作都允许
            - 只读工具: 所有模式都允许
            - PLAN模式: 阻止所有修改操作
            - DEFAULT模式: 修改操作需要确认
        =============================================================================
        """
        # 步骤1: 内置敏感路径保护
        if file_path:
            for candidate_path in _policy_match_paths(file_path):
                for pattern in SENSITIVE_PATH_PATTERNS:
                    if fnmatch.fnmatch(candidate_path, pattern):
                        return PermissionDecision(
                            allowed=False,
                            reason=(
                                f"Access denied: {file_path} is a sensitive credential path "
                                f"(matched built-in pattern '{pattern}')"
                            ),
                        )

        # 步骤2: 显式工具黑名单
        if tool_name in self._settings.denied_tools:
            return PermissionDecision(allowed=False, reason=f"{tool_name} is explicitly denied")

        # 步骤3: 显式工具白名单
        if tool_name in self._settings.allowed_tools:
            return PermissionDecision(allowed=True, reason=f"{tool_name} is explicitly allowed")

        # 步骤4: 检查路径级别规则
        if file_path and self._path_rules:
            for candidate_path in _policy_match_paths(file_path):
                for rule in self._path_rules:
                    if fnmatch.fnmatch(candidate_path, rule.pattern):
                        if not rule.allow:
                            return PermissionDecision(
                                allowed=False,
                                reason=f"Path {file_path} matches deny rule: {rule.pattern}",
                            )

        # 步骤5: 检查命令黑名单模式
        if command:
            for pattern in getattr(self._settings, "denied_commands", []):
                if isinstance(pattern, str) and fnmatch.fnmatch(command, pattern):
                    return PermissionDecision(
                        allowed=False,
                        reason=f"Command matches deny pattern: {pattern}",
                    )

        # 步骤6: 权限模式决策
        # FULL_AUTO模式: 允许所有操作
        if self._settings.mode == PermissionMode.FULL_AUTO:
            return PermissionDecision(allowed=True, reason="Auto mode allows all tools")

        # 只读工具: 所有模式都允许
        if is_read_only:
            return PermissionDecision(allowed=True, reason="read-only tools are allowed")

        # PLAN模式: 阻止修改操作
        if self._settings.mode == PermissionMode.PLAN:
            return PermissionDecision(
                allowed=False,
                reason="Plan mode blocks mutating tools until the user exits plan mode",
            )

        # DEFAULT模式: 需要用户确认
        bash_hint = _bash_permission_hint(command)
        reason = (
            "Mutating tools require user confirmation in default mode. "
            "Approve the prompt when asked, or run /permissions full_auto "
            "if you want to allow them for this session."
        )
        if bash_hint:
            reason = f"{reason} {bash_hint}"
        return PermissionDecision(
            allowed=False,
            requires_confirmation=True,
            reason=reason,
        )


# =============================================================================
# 辅助函数
# =============================================================================

def _policy_match_paths(file_path: str) -> tuple[str, ...]:
    """
    =============================================================================
    函数文档: _policy_match_paths - 获取用于策略匹配的路径形式

    参数说明:
        file_path: 文件路径

    返回值:
        tuple[str, ...] - 需要检查的路径列表

    作用说明:
        目录级别的工具（如grep和glob）可能在根目录上操作，
        如 /home/user/.ssh。添加尾随斜杠允许glob风格的
        模式如 */.ssh/* 和 /etc/* 匹配目录本身。

    实现逻辑:
        1. 去除尾随斜杠得到基础路径
        2. 返回两个形式: 原始路径 和 带斜杠版本
        这样模式既能匹配文件，也能匹配目录
    =============================================================================
    """
    normalized = file_path.rstrip("/")
    if not normalized:
        return (file_path,)
    return (normalized, normalized + "/")


def _bash_permission_hint(command: str | None) -> str:
    """
    =============================================================================
    函数文档: _bash_permission_hint - 生成bash权限提示

    参数说明:
        command: bash命令字符串

    返回值:
        str - 额外的提示信息，如果不需要提示则返回空字符串

    作用说明:
        对于包管理安装和脚手架命令，这些会修改工作区，
        在DEFAULT模式下不会自动执行。提供友好的提示信息。

    为什么需要这个函数:
        npm install、pip install等命令会修改系统状态，
        需要特别提醒用户这些操作需要手动确认。
    """
    if not command:
        return ""
    lowered = command.lower()
    # 包管理器和脚手架工具的标记
    install_markers = (
        "npm install",
        "pnpm install",
        "yarn install",
        "bun install",
        "pip install",
        "uv pip install",
        "poetry install",
        "cargo install",
        "create-next-app",
        "npm create ",
        "pnpm create ",
        "yarn create ",
        "bun create ",
        "npx create-",
        "npm init ",
        "pnpm init ",
        "yarn init ",
    )
    if any(marker in lowered for marker in install_markers):
        return (
            "Package installation and scaffolding commands change the workspace, "
            "so they will not run automatically in default mode."
        )
    return ""
