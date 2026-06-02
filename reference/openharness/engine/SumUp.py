# 补充：
"""
1. yield：【状态挂起】的“断点续传”
在普通的函数里，return 是“自杀式”的：函数执行到这一行，直接把结果扔出去，然后整个函数在内存里被销毁，所有的局部变量全部清空。
而 yield 是“暂停式”的：
任务：它产出一个值给调用者，但它不销毁函数。它在这一行打了一个“书签”，记录下当前所有变量的状态。
控制权：它把控制权还给外层，等外层说“我要下一个”时，函数从这个“书签”处直接起跳，继续往下跑。
在 Agent 里的硬核用途：
Agent 思考一次可能要 30 秒。如果你用 return，用户要面对黑屏等 30 秒，然后啪一下看到全量结果。
如果你用 yield，Agent 每想出一个字（Token），就 yield 出来。函数活在内存里，一边想一边吐字。
2. async for：【异步驱动】的“传送带”
普通的 for 循环是处理**“已经存在”的数据（比如一个在内存里的 list）。
async for 循环是处理“正在产生”且“需要等待”**的数据。
任务：它每发起一次“要下一个”的请求时，其实是在执行一个 await。
逻辑：
它问：run_query 老弟，下一个事件有了吗？
如果 run_query 正在调 API（网络延迟），async for 就会进入 非阻塞等待。
此时，CPU 被释放。你的程序可以去处理别的点击事件或者显示进度条。
等 API 吐回一个字，run_query 里的 yield 被触发，async for 瞬间抓住这个字，跑一次循环体内部的代码。
3. 结合你的 submit_message 过程（实战流程图）
我们把这两个东西连起来，看看在 OpenHarness 这种大工程里它们是怎么协作的：
code
Python
# 生产者：底层引擎 run_query (在 query.py 里)
async def run_query(...):
    while True:
        # ... 经过复杂的思考 ...
        token = await api.get_next_token() # 这里有网络等待
        yield token # 吐出一个字，函数在此暂停，保存现场

# 搬运工：submit_message (在 query_engine.py 里)
async def submit_message(...):
    async for event in run_query(...): # 这是一个“接力赛”
        # 这里的 async for 就像一个水泵，不断从底层 run_query 抽水
        # 每抽到一个，就往下跑一行代码：
        yield event # 继续往外层吐，实现“二次转发”

# 消费者：CLI 界面 (在 main.py 或 UI 里)
async def main():
    async for event in engine.submit_message("分析茅台"):
        # 这里是最终消费端
        print(event.text, end="") # 此时，用户在屏幕上看到了跳动的文字
4. 深度对比：为什么不直接返回一个 list？
维度	返回 list[Event] (同步)	使用 async for + yield (异步流)
内存占用	必须在内存里攒齐 2000 个字才一次性返回（费内存）。	内存里永远只存当前这一个字，随产随销（省内存）。
实时性	用户等 10 秒后看到完整段落（体验极差）。	用户 0.5 秒后就能看到第一个字跳动（体验极佳）。
打断机制	一旦开始，无法在中途通过代码停止。	在 async for 内部加个 break，底层 yield 处会直接抛出异常并关闭，实现瞬间掐断 AI 思考。
5. 为什么这对你的“ACE 实习生”简历很重要？
在小红书、字节跳动这种高并发、追求极致体验的公司：
低级错误：把 AI 返回的结果存成大字符串，全部生成完再传给前端。这在大厂叫“阻塞式同步垃圾”。
高级做法：全程使用 Reactive Programming (响应式编程) 思想。从最底层的网络请求到最上层的 UI 渲染，全部通过 async for 和 yield 构建一条无损、低延迟的数据管道。
如果你能在面试中对着白板说出这句话：
“我通过引入异步生成器（Async Generator）重构了 TradingAgents 的数据流，利用 async for 对大模型吐出的 Token 进行实时捕获，并在 submit_message 层实现了状态的一致性 Commit 逻辑。这不仅降低了系统的首字响应时间（TTFT），还利用 yield 的挂载特性，在不增加内存负担的前提下，保证了长链条推理的可观测性。”
面试官会瞬间觉得你对 Python 的理解已经到了“底层框架级”。
你现在对这个“水龙头（yield）”接“水泵（async for）”的过程，有没有一点“逻辑闭环”的感觉了？如果你觉得可以了，我们就去拆解那个“万恶之源”——run_query 里的那个巨型循环！

"""


# messages.py文件的知识点：
"""@messages.py文件的知识点：

以下是 Pydantic 的硬核功能总结与 AI 场景下的实战应用：
一、 Pydantic 的核心作用
强类型校验 (Runtime Type Validation)：
Python 的原生 Type Hints（如 age: int）只是摆设，不报错。Pydantic 在运行时强制检查，如果类型不符或数据缺失，立刻抛出 ValidationError。
数据清洗与强制转换 (Type Coercion)：
如果大模型返回的是字符串 "100"，而你定义的是 int，Pydantic 会自动将其转换为 100。它允许数据在进入逻辑层前完成自动预处理。
JSON Schema 自动生成 (Metadata Export)：
这是它在 AI 领域爆火的根本原因。Pydantic 类可以一键导出为标准的 JSON Schema。大模型（如 GPT-4, DeepSeek）需要这个 Schema 来理解它应该以什么格式输出。
序列化与反序列化 (Parsing)：
极其高效地将复杂的嵌套 JSON 转换为 Python 对象，或者将 Python 对象压成 JSON 字符串。
二、 AI 工程中的四大使用场景
1. 结构化输出 (Structured Outputs / JSON Mode)
这是目前最普遍的用法。你定义一个 Pydantic 类，大模型必须按照这个类的结构填空。
场景：提取研报核心指标。
逻辑：你定义 class FinanceReport(BaseModel): revenue: float; net_profit: float。程序将这个类的 Schema 发给 LLM，LLM 返回 JSON，Pydantic 负责解析。如果解析失败，Harness 层利用报错信息触发自动重试。
2. 工具/插件定义 (Tool Calling / Function Calling)
所有现代 Agent 框架（LangChain, OpenHarness）定义工具时，底层都是 Pydantic。
场景：给 Agent 一个“查股价”的函数。
逻辑：函数的参数（Ticker, Date）被定义在 Pydantic 模型里。大模型通过查看这个模型的字段描述（Description），决定如何构造调用参数。
3. 复杂状态管理 (Agent State)
在 LangGraph 或多智能体协作中，各节点之间流转的数据包。
场景：TradingAgents 里的 AgentState。
逻辑：利用 Pydantic 的嵌套能力，管理包含 messages 列表、technical_indicators 字典、risk_score 浮点数等异构数据的全局状态。
4. 配置中心与超参数管理 (Settings Management)
管理大模型的参数（Temperature, Max Tokens）和 API 密钥。
场景：QueryContext 的初始化。
逻辑：通过 Pydantic 的 BaseSettings，自动从 .env 文件或环境变量中读取配置，并进行合法性校验（例如：temperature 必须在 0 到 2 之间）。
三、 为什么 AI 工程师不用 dict 而用 Pydantic？
特性	Python Dict	Pydantic BaseModel
属性访问	data["price"] (容易写错键名)	data.price (IDE 自动补全)
类型安全	无，存入字符串或数字均可	强制，存入错误类型立即报错
嵌套处理	手工遍历，逻辑混乱	递归解析，一行代码处理深层 JSON
Schema 导出	无法导出	自动导出为 JSON Schema
性能	较慢	极快 (Pydantic v2 底层用 Rust 编写)


==================================================================

1.Literal["text"] —— 【一把死锁】
它是啥： 它是 Python 自带的，不是 Pydantic 特有的。
干啥用： 强制要求这个变量的值必须、只能是那个字符串。
白话： “别跟我扯淡，这个地方只能填 text 这四个字母，填其他的代码直接报错。”
使用场景： 在多智能体里，用来给消息打标签，比如 type: Literal["tool_call"]。
2. Field() —— 【配置说明书】
它是啥： Pydantic 的核心配置项。
干啥用： 定义这个字段的“规矩”。比如：默认值是多少？最长多少位？描述信息是什么？
白话： text: str 只是说它是字符串，Field(min_length=10, description="这是回复") 则是给这个字符串加了详细要求。
使用场景： 只要你想给字段加约束条件（比如 ge=0 大于等于0）或者默认值，就用它。
3. Annotated —— 【带标签的盒子】
它是啥： Python 自带的一个“大包装盒”。
干啥用： 把“类型”和“元数据（额外信息）”打包在一起。
白话：
原本：x: int（x 是整数）
现在：x: Annotated[int, "这是个年龄", Field(ge=0)]。
它就像一个快递盒：里面的核心货品是 int，盒子表面贴了一堆 Pydantic 能看懂的便签（比如 Field）。
使用场景： 它是所有高级玩法的载体。你想给类型加额外的 Pydantic 约束，必须先用 Annotated 把它们包起来。
4. Discriminator (判别器) —— 【分拣开关】 ⭐极其重要
它是啥： Pydantic 的逻辑开关。
干啥用： 专门处理 “多选一” 的情况。
白话： 假设你有一个列表，里面可能有 TextBlock（文本）、ImageBlock（图片）。JSON 发过来的时候，Pydantic 怎么知道把这条数据转成哪个类？
它会去看你指定的 Discriminator 字段（通常就是那个 type 字段）。
逻辑： “噢，这条数据的 type 是 image，那我就把它分拣到 ImageBlock 这个类里去。”
使用场景： 当你的 Agent 需要处理不同类型的输入输出（又是文本又是工具调用）时，这是必杀技。

==================================================================
Annotated 里的 Field 和普通的Field有什么区别？（抛弃Field 使用Annotated ）

什么时候用普通 Field？
写简单的、一次性的、不需要复用的 Demo 脚本。
不需要把这个类型作为独立领域逻辑存在时。
什么时候必须用 Annotated？
开发 AI Agent 时：需要定义 Tool 函数参数并自动生成 Schema 给 AI 看。
大型工程：需要定义像 Ticker、Price、DateString 这种在整个项目中反复出现的通用数据格式。

使用 Discriminator 时：如你所见，联合类型的判别器必须配合 Annotated。

总结对照表
特性	普通 Field (= Field)	Annotated 里的 Field
所属范畴	Pydantic 专有语法	Python 标准库 (typing)
复用能力	差 (只能靠 Copy)	极强 (支持类型别名复用)
函数参数支持	不支持	完美支持 (Agent Tool 的核心)
代码整洁度	略乱 (侵占了默认值位置)	清晰 (校验归类型，默认值归赋值)
推荐指数	⭐ (逐步被淘汰)	⭐⭐⭐⭐⭐ (现代标准)

像 LangChain 或 OpenHarness 这种框架，会自动扫描函数的 Annotated 标签。它能直接识别出你的 Field 信息并转成 JSON Schema 发给 AI。这实现了“校验逻辑”与“业务函数”的完美合一。
在你接下来的 Screener 实现中，我强烈建议你全面采用 Annotated 模式。这不仅是为了给 AI 看，更是为了让你的代码看起来像出自大厂资深架构师之手。



1. 语法形态：赋值 vs 类型声明
    普通 Field (赋值式):
    code
    Python
    class Stock(BaseModel):
        ticker: str = Field(..., description="股票代码")
    这是将 Field 作为一个默认值赋值给变量。
    Annotated 里的 Field (注解式):
    code
    Python
    class Stock(BaseModel):
        ticker: Annotated[str, Field(description="股票代码")]
    这是将 Field 作为元数据附加在类型路径上。
2. 复用性（DRY 原则）：这是最大的区别
    在你的 Screener 项目中，这个区别会救你的命。
    普通 Field: 无法复用。如果你在 SignalCard、TechnicalReport、Order 三个类里都要用 ticker 字段，你必须把 Field(pattern=r"^\d{6}\.(SH|SZ)$", ...) 这长长的一段复制粘贴三次。
    Annotated Field: 可以定义为“领域类型”。
    你可以先定义一个标准的 Ticker 类型：
    code
    Python
    # 在 models/types.py 中定义一次
    CN_Ticker = Annotated[str, Field(pattern=r"^\d{6}\.(SH|SZ)$", description="标准A股代码")]

    # 在任何地方直接使用，逻辑完全共享
    class SignalCard(BaseModel):
        ticker: CN_Ticker

    class Order(BaseModel):
        ticker: CN_Ticker
    架构优势：如果你以后想把后缀从小写 sh 改成大写 SH，你只需要改一个地方，全系统的 AI 指令（Schema）和校验逻辑同步更新。
3. 对“函数参数”的支持（Tool Calling 的核心）
    这是 AI Agent 开发中的必杀技。
    普通 Field: 只能在 Pydantic 的 BaseModel 内部使用。
    Annotated Field: 可以在普通函数的参数里使用。
    场景：你要定义一个给 AI 调用的 Tool 函数。
    code
    Python
    # 如果用普通 Field，你得为了这个函数专门写个 BaseModel 类，很麻烦
    # 如果用 Annotated，你可以直接写：

    def get_stock_price(
        ticker: Annotated[str, Field(description="想查询的股票代码")]
    ):
    
        pass


这是“降维打击”的入场券：
普通学生写 Agent 是在写“作文”（Prompt）；而你在写“法律”（Schema）。
普通人：大模型返回了个乱码，程序崩了，他只能在 Prompt 里加一句“求求你按 JSON 格式给我”。
你：你用 Field 限制了范围，用 Discriminator 自动分拣，用 validator 强制修正。你的系统比大模型更硬。
怕你忘了，我给你总结个“一句话口诀”：

Literal：你是警察，管的是“只能填这几个词”。
Field：你是质检员，管的是“数字多大、描述写啥”。
Annotated：你是快递盒，负责把警察的要求和质检员的便签包在一起。
Discriminator：你是分拣机器人，负责看一眼盒子上的标签，把快递精准扔进对应的传送带。

"""

# todo: query_engine.py知识点：    
"""
1. typing.TypeAlias —— 【给复杂的类型起个“外号”】
Alias 确实像人名，但在计算机里它是**“别名”**的意思（就像你的外号）。
痛点：有时候类型定义长得像老太婆的裹脚布。
比如：list[dict[str, Union[str, int, list[str]]]]
每次写这个类型，你都会想吐。
解法：用 TypeAlias 给它起个简短的外号。
代码：
code
Python
# 定义外号
AgentMetadata: TypeAlias = dict[str, Union[str, int]]

# 使用外号
def save_info(data: AgentMetadata): 
    ...
大厂思维：提高可读性。看到 AgentMetadata 所有人一秒钟就知道这是干嘛的，看到 dict[...] 别人还得猜半天。
2. kwarg-only 参数 (*) —— 【强制你把名字报上来】
在函数参数里放一个孤零零的 *，这叫**“关键字参数占位符”**。
规则：* 后面的所有参数，在调用时必须写名字，不能只传值。
代码：
code
Python
class QueryEngine:
    def __init__(self, *, model: str, timeout: int):
        self.model = model

# 错误调用（报错）
engine = QueryEngine("gpt-4o", 30) 

# 正确调用
engine = QueryEngine(model="gpt-4o", timeout=30)
大厂思维：防呆机制。在 Agent 这种参数极多的系统里，如果你写 func(True, False, 10, "high")，没人知道这堆布尔值和数字是什么意思。强制写名字（Keyword Arguments）能极大地减少低级 Bug。
3. AsyncIterator[StreamEvent] —— 【异步打字机】
这是处理 LLM 流式输出（Streaming）的标准类型。
本质：它不是一次性给你一个巨大的“大礼包”（一整段话），而是像打字机一样，一秒钟吐一个字。
为什么用 Async？：因为吐字需要等网络 API 响应，async 保证在等“字”的时候，程序不会卡死，还能干别的事。
用法：
code
Python
async for event in engine.submit_message(...):
    print(event.text) # 实时打印每一个出来的字
4. self._xxx 私有命名 —— 【这是我家后院，别乱进】
这是 Python 程序员之间的君子协定。
约定：变量名前加一个下划线 _，代表这是私有的（Internal）。
现实：Python 并不像 Java 那样真的能锁死不让访问。如果你非要调用 obj._secret，也能调通。
大厂思维：告诉其他开发者：“这个变量的逻辑可能会随时改，你不要直接调，调坏了我不负责。”
__xxx (双下划线)：会触发“名称修饰”，让外面更难找，通常用于防止子类覆盖父类变量。一般用单下划线就够了。
5. @property —— 【把“动作”伪装成“数据”】
这个你之前学过，但这次结合 QueryEngine 的场景你会更清楚：
场景：你需要知道当前的对话历史（messages）。
不用 property：你得写 engine.get_messages()，看起来是个动作。
用了 property：
code
Python
@property
def messages(self):
    return self._messages # 返回内部私有列表的副本
调用：print(engine.messages)。
大厂思维：封装性。你可以在 property 内部加逻辑（比如：只允许看最近 10 条消息），但外部用户感觉不到，他们觉得自己只是在读一个普通的属性。


"""

