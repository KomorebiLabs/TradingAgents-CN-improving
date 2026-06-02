"""
模块文档: cost_tracker.py - 使用量追踪模块

================================================================================
特殊Python语法说明:
1. from __future__ import annotations: 这是Python 3.7+的特性，
   用于启用PEP 563延迟注解评估，解决循环导入问题
2. @dataclass 或普通类中省略的构造函数参数类型注解
================================================================================

功能说明:
    CostTracker 是一个轻量级的使用量追踪器，用于在AI对话会话的整个生命周期内
    累积和统计API使用量（输入/输出token数）。它不负责API调用，只负责聚合统计。
"""

from __future__ import annotations

from openharness.api.usage import UsageSnapshot


class CostTracker:
    """
    =============================================================================
    类文档: CostTracker - 使用量累积器

    作用说明:
        在整个会话期间累积AI模型的token使用量。当用户与AI进行多轮对话时，
        每次API调用都会消耗一定数量的输入token（用户的提问+历史对话）和
        输出token（AI的回复）。这个类用于追踪所有这些消耗的总和。

    为什么需要这个类:
        1. 计费目的：大多数AI API按token计费，需要追踪总使用量来计算费用
        2. 预算控制：可以设置token使用上限，防止超额消耗
        3. 监控分析：了解会话的复杂度和资源消耗情况
    =============================================================================
    """

    def __init__(self) -> None:
        """
        构造函数说明:
            初始化追踪器，创建一个空的UsageSnapshot实例作为初始状态。

        初始化逻辑:
            self._usage = UsageSnapshot()  # 初始时没有任何使用量，所有计数为0
        """
        self._usage = UsageSnapshot()

    def add(self, usage: UsageSnapshot) -> None:
        """
        =============================================================================
        方法文档: add - 累加使用量

        参数说明:
            usage: UsageSnapshot - 一次API调用产生的使用量快照

        作用说明:
            将单次API调用的token使用量添加到运行总量中。这是一种"累加"模式，
            每次调用后，total属性返回的都会是所有历史调用的总和。

        实现逻辑:
            通过创建新的UsageSnapshot对象来更新状态，而不是直接修改现有对象。
            这是为了保持数据的不可变性和线程安全性。

        示例:
            # 假设调用1消耗了100输入+50输出tokens
            tracker.add(UsageSnapshot(input_tokens=100, output_tokens=50))
            print(tracker.total)  # input=100, output=50

            # 调用2消耗了200输入+80输出tokens
            tracker.add(UsageSnapshot(input_tokens=200, output_tokens=80))
            print(tracker.total)  # input=300, output=130 (累加结果)
        =============================================================================
        """
        self._usage = UsageSnapshot(
            input_tokens=self._usage.input_tokens + usage.input_tokens,
            output_tokens=self._usage.output_tokens + usage.output_tokens,
        )

    @property
    def total(self) -> UsageSnapshot:
        """
        =============================================================================
        属性文档: total - 获取累积总量

        返回值:
            UsageSnapshot - 包含所有历史API调用累计token数的快照对象

        作用说明:
            提供只读访问当前累积的使用量。这是一个只读属性，
            返回的是_usage的副本，防止外部代码直接修改内部状态。

        为什么返回副本而不是原对象:
            1. 封装性保护：防止外部意外修改内部状态
            2. 线程安全：在多线程环境下避免竞态条件
            3. 数据一致性：确保每次调用返回的都是一致的数据快照
        =============================================================================
        """
        return self._usage
