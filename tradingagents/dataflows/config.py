"""
================================================================================
                            CONFIG.PY 详解
                          配置管理模块
================================================================================

┌─────────────────────────────────────────────────────────────────────────────┐
│                           配置架构图                                         │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       default_config.py                                 │   │
│  │                      (默认配置 - 系统预置)                              │   │
│  │                                                                       │   │
│  │  DEFAULT_CONFIG = {                                                   │   │
│  │      "data_vendors": {...},  # 数据源配置                            │   │
│  │      "tool_vendors": {...},  # 工具级配置                           │   │
│  │      ...                                                             │   │
│  │  }                                                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                       │
│                                    │ 复制到                                │
│                                    ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        config.py (当前模块)                            │   │
│  │                      (运行时配置 - 可修改)                            │   │
│  │                                                                       │   │
│  │  _config = DEFAULT_CONFIG.copy()  # 初始化时复制                     │   │
│  │                                                                       │   │
│  │  提供函数：                                                            │   │
│  │    - initialize_config(): 初始化                                      │   │
│  │    - set_config(): 修改配置                                          │   │
│  │    - get_config(): 获取配置                                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                       │
│                                    │ 被使用                                │
│                                    ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       interface.py                                      │   │
│  │                     (路由层 - 使用配置决定数据源)                       │   │
│  │                                                                       │   │
│  │  def route_to_vendor(method, *args, **kwargs):                        │   │
│  │      vendor = get_vendor(category, method)  # ← 读取配置              │   │
│  │      ...                                                             │   │
│  │                                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

================================================================================
一、模块职责
================================================================================

这个模块负责管理整个 TradingAgents 系统的配置：

  1. 配置存储
     - 管理全局配置字典
     - 支持默认值和自定义值

  2. 配置访问
     - 提供 get_config() 函数获取当前配置
     - 配置是只读的副本，不会意外修改原配置

  3. 配置修改
     - 提供 set_config() 函数修改配置
     - 支持部分更新（只更新提供的字段）

  4. 懒加载
     - 配置在第一次访问时才初始化
     - 避免不必要的导入开销

================================================================================
二、配置结构
================================================================================

默认配置通常包含以下内容（具体见 default_config.py）：

┌─────────────────────────────────────────────────────────────────────────────┐
│                          配置字典结构                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  {                                                                       │
│    # =========================================                              │
│    # 数据源配置                                                            │
│    # =========================================                              │
│    "data_vendors": {                                                      │
│        "core_stock_apis": "alpha_vantage,yfinance",  # 优先 AV，备用 YF  │
│        "technical_indicators": "alpha_vantage,yfinance",                 │
│        "fundamental_data": "alpha_vantage,yfinance",                     │
│        "news_data": "yfinance,alpha_vantage",       # 优先 YF，备用 AV  │
│    },                                                                     │
│                                                                             │
│    "tool_vendors": {                                                      │
│        # 可选的工具级别配置，覆盖上面的 data_vendors                        │
│        # "get_stock_data": "yfinance",                                    │
│    },                                                                     │
│                                                                             │
│    # =========================================                              │
│    # LLM 配置                                                              │
│    # =========================================                              │
│    "llm_provider": "openai",        # LLM 提供商                        │
│    "deep_think_llm": "gpt-4o",       # 深度思考模型                      │
│    "quick_think_llm": "gpt-4o-mini", # 快速思考模型                      │
│                                                                             │
│    # =========================================                              │
│    # 其他配置                                                              │
│    # =========================================                              │
│    "data_cache_dir": "./data_cache",  # 数据缓存目录                      │
│    "results_dir": "./reports",        # 结果输出目录                      │
│    "max_debate_rounds": 3,            # 辩论轮次上限                      │
│  }                                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

================================================================================
三、代码解析
================================================================================
"""

import tradingagents.default_config as default_config
from typing import Dict, Optional

# ==============================================================================
# 第一部分：全局配置变量
# ==============================================================================

# _config: 全局配置字典
# 初始值为 None，表示「未初始化」
# 第一次调用 get_config() 时会调用 initialize_config()
#
# 为什么用 None？
#   - 延迟初始化：避免在模块导入时就加载默认配置
#   - 允许外部设置：TradingAgentsGraph 在初始化时可以先 set_config()
#
_config: Optional[Dict] = None


# ==============================================================================
# 第二部分：配置管理函数
# ==============================================================================

def initialize_config():
    """
    初始化配置。

    当 _config 为 None 时，复制默认配置。

    这个函数在模块加载时被调用一次：
        initialize_config()  # 文件底部

    为什么用 copy() 而不是直接引用？
    --------------------------------
    这样可以避免修改配置时影响原始的 DEFAULT_CONFIG：

        config = DEFAULT_CONFIG  # ❌ 错误：共享引用
        config["key"] = "value"  # 会修改 DEFAULT_CONFIG

        config = DEFAULT_CONFIG.copy()  # ✅ 正确：复制副本
        config["key"] = "value"  # 不会影响 DEFAULT_CONFIG
    """
    global _config
    if _config is None:
        # 从 default_config 模块获取默认配置并复制
        _config = default_config.DEFAULT_CONFIG.copy()


def set_config(config: Dict):
    """
    更新全局配置。

    这个函数用于在运行时修改配置：

        from tradingagents.dataflows.config import set_config, get_config

        # 获取当前配置
        config = get_config()

        # 修改配置
        config["data_vendors"]["core_stock_apis"] = "yfinance,alpha_vantage"

        # 写回
        set_config(config)

    也可以传入部分配置（不推荐，但向后兼容）：

        set_config({"max_debate_rounds": 5})

    Args:
        config: 新的配置字典

    注意：
        - 如果 _config 未初始化，会先初始化（复制默认配置）
        - 然后用新配置更新（dict.update()）
        - 这意味着新配置会覆盖同名键
    """
    global _config
    if _config is None:
        # 确保 _config 已初始化
        _config = default_config.DEFAULT_CONFIG.copy()

    # update() 会将 config 中的键值对合并到 _config
    # 如果键已存在，覆盖；否则添加
    _config.update(config)


def get_config() -> Dict:
    """
    获取当前配置的副本。

    返回副本的原因：
    ----------------
    1. 防止意外修改：
       config = get_config()
       config["key"] = "value"  # ❌ 这不会影响全局配置
                              # 因为修改的是副本

    2. 线程安全：
       多线程环境下，返回副本比返回引用更安全

    Returns:
        配置字典的浅拷贝

    为什么是浅拷贝？
    --------------
    返回的是 copy() 而不是 deepcopy()：
    - copy() 是浅拷贝，只复制第一层
    - 如果配置中有嵌套字典（如 data_vendors），内部字典仍是共享引用

    这样做是合理的：
    - 配置结构简单，没有多层嵌套
    - copy() 性能更好

    示例：
        >>> config = get_config()
        >>> print(config["llm_provider"])
        'openai'
    """
    if _config is None:
        # 懒加载：如果还未初始化，先初始化
        initialize_config()

    # 返回副本，防止意外修改全局配置
    return _config.copy()


# ==============================================================================
# 第三部分：模块初始化
# ==============================================================================

# 模块加载时初始化配置
# 这样确保在使用配置前，它已经被正确设置
#
# 初始化顺序：
#   1. import config  →  _config = None
#   2. 到达文件底部   →  调用 initialize_config()
#   3. _config 被设置为 DEFAULT_CONFIG.copy()
#
# 后续流程：
#   - TradingAgentsGraph.__init__() 可以调用 set_config() 覆盖默认配置
#   - 任何模块调用 get_config() 获取当前配置
#
initialize_config()


# ==============================================================================
# 补充说明
# ==============================================================================

"""
================================================================================
【配置优先级】

TradingAgents 中的配置按以下优先级生效（从高到低）：

    1. 代码中调用 set_config()
           TradingAgentsGraph(config={"data_vendors": {...}})

    2. 环境变量
           ALPHA_VANTAGE_API_KEY=xxx

    3. 默认配置 (default_config.DEFAULT_CONFIG)
           系统预置的默认值

================================================================================
【数据源配置详解】

data_vendors 字段控制数据源的优先级：

格式：
    "类别名": "数据源1,数据源2,..."

逗号分隔表示回退顺序：
    "core_stock_apis": "alpha_vantage,yfinance"

含义：
    1. 优先使用 alpha_vantage
    2. 如果 alpha_vantage 失败（频率限制），切换到 yfinance

工具级配置覆盖类别配置：

    config = {
        "data_vendors": {
            "core_stock_apis": "alpha_vantage,yfinance"  # 默认
        },
        "tool_vendors": {
            "get_stock_data": "yfinance"  # 这个工具单独用 yfinance
        }
    }

================================================================================
【使用示例】

示例 1: 在初始化时设置配置

    from tradingagents.graph import TradingAgentsGraph
    from tradingagents.dataflows.config import set_config

    # 设置数据源
    set_config({
        "data_vendors": {
            "core_stock_apis": "yfinance,alpha_vantage"  # 优先 YF
        }
    })

    # 创建图实例
    graph = TradingAgentsGraph()

示例 2: 读取配置

    from tradingagents.dataflows.config import get_config

    config = get_config()
    print(f"当前数据源: {config['data_vendors']}")
    print(f"LLM 提供商: {config['llm_provider']}")

示例 3: 检查 API Key

    from tradingagents.dataflows.config import get_config
    import os

    config = get_config()
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")

    if not api_key:
        print("警告: 未设置 ALPHA_VANTAGE_API_KEY 环境变量")
        print("请从 https://www.alphavantage.co 支持 获取 API Key")

================================================================================
【配置的设计模式】

本模块使用了以下设计模式：

1. 单例模式 (Singleton Pattern)
   - 只有一个全局配置实例
   - 通过 global 变量和函数访问

2. 代理模式 (Proxy Pattern)
   - get_config() 返回副本，而不是直接返回引用
   - 提供对原始配置的间接访问

3. 模板方法模式 (Template Method Pattern)
   - initialize_config() 定义初始化流程
   - 子类或外部代码可以通过 set_config() 自定义

4. 备忘录模式 (Memento Pattern)
   - copy() 返回配置的状态快照
   - 可以保存和恢复配置状态
"""
