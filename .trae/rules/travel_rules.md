# 旅行规划助手 - 项目规则说明

## 项目概述

基于 LangGraph 的智能旅行规划助手，通过命令行参数收集用户需求，使用多节点协作生成预算感知的旅行方案。详细架构请参考 [ARCHITECTURE.md](file:///d:/Travel/ARCHITECTURE.md)。

## 项目框架

- **LangGraph**: 用于构建和管理节点图，支持节点之间的协作和状态管理。
- **LangChain**: LCEL 链式调用，提供 LLM 集成和输出解析能力。
- **Python**: 作为主要开发语言，利用丰富的库和工具。
- **Pydantic**: 结构化数据校验，确保类型安全。

## 命名规则

1. **类名**: PascalCase 大驼峰
   - 正确: UserOrderService
   - 错误: user_order / userOrderService
2. **函数、方法、变量、模块文件名**: snake_case 下划线小写，**禁止 camelCase**
   - 正确: get_user_info、user_id、user_service.py
   - 错误: getUserInfo、userId
3. **全局常量**: UPPER_SNAKE_CASE 全大写下划线
   - 示例: MAX_TIMEOUT、DEFAULT_PAGE_SIZE
4. **类内部私有成员**: 单下划线开头 _data
   - 示例: self._token
5. **名称改写属性**: 双下划线 __secret_key
6. **特殊豁免**: 仅对接第三方 API/外部 JSON 字段时允许驼峰，自研业务代码一律不用

## 注释规则

1. 全部注释使用中文；语句完整通顺
2. `#` 符号后**必须跟1个空格**再写注释内容；禁止 `#无空格`、`#  多空格`。
3. 注释缩进层级与对应代码保持一致，禁止顶格注释低层级代码。
4. 代码修改后同步更新注释，禁止注释与代码逻辑冲突。
5. 注释放在函数名或类目的上面。



## 核心规则

### LLM 输出规则
- 所有 LLM 输出必须使用 Pydantic 模型进行结构化解析
- 禁止使用正则表达式解析文本输出

### 节点函数规则
- 所有节点函数必须是异步函数（async def）
- 节点函数必须返回 `TravelState` 对象
- 节点函数必须使用 `retry_on_rate_limit` 装饰器处理速率限制

### 工具调用规则
- 工具必须通过 LangGraph 的 ToolNode 执行
- 工具列表集中在 `agent/tool_node.py` 管理
- 工具调用循环最多 5 次，防止无限循环
- ToolMessage 内容截断为 2000 字符，防止 token 超限

### 调研节点规则
- **严禁使用 tavily_search**，只能使用高德地图工具（maps_text_search、maps_weather）
- 只采集骨架数据（名称、ID、经纬度、片区、分类），不拉取详情
- 代码层做数据自检，确定缺少哪些数据后再调用工具

### 预算规则
- 预算容忍度为 10%，超支在预算 10% 以内不触发调整
- 超支时最多循环调整 3 次
- 正向计算：门票→住宿→餐饮→交通→备用金

### Token 管理规则
- 节点完成后必须清空 `messages` 为后续节点腾出空间
- Tavily 搜索结果限制为 3 条
- 避免每次迭代重新构建 System/Human 消息

### 错误处理规则
- Pydantic 解析失败时记录错误并继续流程
- 高德 MCP 加载失败时跳过，不影响主流程

### 导入路径规则
- 模型从 `models.models` 导入
- 配置从 `config.config` 导入
- 工具从 `tools.api` 和 `tools.mcp` 导入
- 公共工具从 `utils.utils` 导入

## 数据模型规则

### 状态定义 (TravelState)
- 使用 TypedDict 定义，兼容 LangGraph 状态管理
- `messages` 字段使用 `Annotated[list, add_messages]` 支持消息累积
- 分层数据字段：`simple_city_poi`、`selected_scenic_detail`、`route_related_price`、`weather`

### 输出解析器
- 每个模型对应一个 PydanticOutputParser，定义在 `models/models.py` 中：
  - `research_parser`
  - `budget_allocation_parser`
  - `itinerary_parser`
  - `budget_analysis_parser`

## 图流程规则

### 节点流转顺序
1. `researcher` → 调研目的地信息
2. `planner` → 规划行程（两段式）
3. `budget_analyst` → 预算分配
4. `budget_check` → 预算检查

### 条件边规则
- `should_call_tool_researcher/planner/budget`: 判断是否需要工具调用
- `after_tool`: 工具执行后根据 status 返回对应节点
- `should_adjust`: 判断是否需要调整行程（最多 3 次循环）

### 状态值定义
- `researching`: 调研中
- `tool_calling`: 工具调用中
- `planning`: 规划中
- `planning_tool`: 规划阶段工具调用
- `budgeting`: 预算分配中
- `budgeting_tool`: 预算阶段工具调用
- `checking`: 预算检查中
- `completed`: 完成
- `failed`: 失败