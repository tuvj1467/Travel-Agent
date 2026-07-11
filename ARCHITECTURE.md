# 旅行规划助手 - 项目架构说明

## 项目概述

基于 LangGraph 的智能旅行规划助手，通过对话收集用户需求，使用多节点协作生成预算感知的旅行方案。系统采用结构化状态管理，支持条件分支和循环调整，确保行程在预算约束内生成。

## 整体架构

```
┌───────────────────────────────────────────────────────────────────────────┐
│                     用户交互层                                            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                   │
│  │   CLI 终端   │    │  REST API   │    │  Web 前端    │                   │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                   │
└─────────┼──────────────────┼──────────────────┼───────────────────────────┘
          │                  │                  │
┌─────────▼──────────────────▼──────────────────▼───────────────────────────┐
│                   需求收集层                                              │
│          TravelDemand (Pydantic)                                         │
│  - 命令行参数解析 → 结构化参数提取 → 图执行入口                              │
└────────────────────────────┬──────────────────────────────────────────────┘
                             │ TravelDemand
┌────────────────────────────▼──────────────────────────────────────────────┐
│                   旅行规划层 (LangGraph)                                   │
│                                                                          │
│  ┌──────────┐    ┌──────────┐                                            │
│  │researcher│───→│tool_node │───→ researcher (条件循环)                   │
│  └──────┬───┘    └──────────┘                                            │
│         │                                                                │
│         ▼                                                                │
│  ┌──────────┐    ┌──────────┐                                            │
│  │ planner  │───→│tool_node │───→ planner (条件循环)                      │
│  └──────┬───┘    └──────────┘                                            │
│         │                                                                │
│         ▼                                                                │
│  ┌──────────────┐    ┌──────────┐                                        │
│  │budget_analyst│───→│tool_node │───→ budget_analyst (条件循环)          │
│  └──────┬───────┘    └──────────┘                                        │
│         │                                                                │
│         ▼                                                                │
│  ┌────────────┐                                                          │
│  │budget_check│                                                          │
│  └──────┬─────┘                                                          │
│         │                                                                │
│    ┌────┴────┐                                                           │
│    ▼         ▼                                                           │
│  (超支?)    END                                                          │
│    │                                                                     │
│    ▼                                                                     │
│  planner ← 循环最多3次                                                    │
└───────────────────────────────────────────────────────────────────────────┘
                             │
┌────────────────────────────▼──────────────────────────────────────────────┐
│                   输出展示层                                              │
│  - 格式化 CLI 输出 (main.py → format_itinerary)                           │
│  - JSON API 响应                                                          │
│  - 行程可视化                                                              │
└───────────────────────────────────────────────────────────────────────────┘
```

## 技术栈

| 类别 | 技术 | 版本 | 说明 |
|------|------|------|------|
| LLM | 百度千帆 | 环境配置 | 主模型，通过 QIANFANG_MODEL 环境变量配置（默认 ernie-4.5-turbo-32k），通过 ChatOpenAI 兼容层调用 |
| 对话框架 | LangChain | 0.3.x | LCEL 链式调用 |
| 多节点框架 | LangGraph | 0.2.x | StateGraph 状态机 + ToolNode |
| 搜索工具 | Tavily Search | - | 实时价格和地理信息（限制3条结果） |
| 地图工具 | 高德 MCP | - | POI搜索、天气查询、景点详情（MCP Server） |
| 数据模型 | Pydantic | v2 | 结构化数据校验 |
| API 框架 | FastAPI | 0.115.x | REST API（待实现） |
| 配置管理 | python-dotenv | 1.0.x | 环境变量加载 |

## 核心数据模型

### 状态定义 (TravelState)

```python
{
    "destination": str,                        # 目的地
    "days": int,                               # 出行天数
    "budget": float,                           # 总预算（元）
    "interests": str,                          # 兴趣偏好
    "messages": Annotated[list, add_messages], # ToolNode 消息循环（AIMessage/ToolMessage）
    "research_result": Optional[ResearchResult],    # 调研结果
    "budget_allocation": Optional[BudgetAllocation], # 预算分配
    "itinerary": Optional[Itinerary],                # 行程规划
    "budget_analysis": Optional[BudgetAnalysis],     # 预算分析
    "iteration_count": int,                    # 迭代次数（最大3次）
    "needs_adjustment": bool,                  # 是否需要调整
    "error": Optional[str],                    # 错误信息
    "status": str,                             # 当前状态
    "tool_call_count": int,                    # 工具调用计数
    # 分层数据字段（轻量化采集）
    "simple_city_poi": Optional[List[dict]],   # 全城轻量化景点列表
    "selected_scenic_detail": Optional[List[dict]], # 选中景点详情
    "raw_route": Optional[dict],               # 粗路线骨架
    "route_related_price": Optional[List[dict]],    # 路线片区价格
    "weather": Optional[dict],                 # 天气数据
}
```

### 子模型层次结构

```
CostItem (费用明细项)
    ├── ResearchResult.cost_items        # 调研结果中的消费水平
    └── BudgetAllocation.categories      # 预算分配中的各项预算

Activity (单项活动)
    └── DayPlan.activities              # 每日活动列表

DayPlan (每日行程)
    └── Itinerary.day_plans             # 完整行程的每日计划

ResearchResult → BudgetAllocation → Itinerary → BudgetAnalysis

# 分层数据模型（新架构）
SimplePOI → ScenicDetail → RoutePOI → RoughRoute
WeatherData (独立)
RoutePrice (独立)
```

### 字段说明

| 字段 | 类型 | 说明 | 填充节点 | 状态 |
|------|------|------|----------|------|
| destination | str | 目的地名称 | 输入 | ✅ |
| days | int | 出行天数 | 输入 | ✅ |
| budget | float | 总预算 | 输入 | ✅ |
| interests | str | 兴趣偏好 | 输入 | ✅ |
| messages | list | ToolNode 消息循环 | ToolNode | ✅ |
| research_result | ResearchResult | 调研结果 | researcher | ✅ |
| budget_allocation | BudgetAllocation | 预算分配方案 | budget_analyst | ✅ |
| itinerary | Itinerary | 行程规划 | planner | ✅ |
| budget_analysis | BudgetAnalysis | 预算分析结果 | budget_check | ✅ |
| iteration_count | int | 迭代次数 | budget_check | ✅ |
| needs_adjustment | bool | 是否需要调整 | budget_check | ✅ |
| error | str | 错误信息 | 任意节点 | ✅ |
| status | str | 当前状态 | 任意节点 | ✅ |
| tool_call_count | int | 工具调用计数 | researcher/planner/budget_analyst | ✅ |
| simple_city_poi | List[dict] | 轻量化景点列表 | researcher(工具调用) | ✅ |
| selected_scenic_detail | List[dict] | 选中景点详情 | planner(工具调用) | ✅ |
| raw_route | dict | 粗路线骨架 | planner | ⏳ |
| route_related_price | List[dict] | 路线片区价格 | budget_analyst(工具调用) | ✅ |
| weather | dict | 天气数据 | researcher(工具调用) | ✅ |

> **说明**: ✅ 表示已实现，⏳ 表示部分实现或待完善

## 详细流程

### 第一阶段：需求收集 (CLI 参数解析)

**目的**: 通过命令行参数收集旅行需求的4个核心参数

**核心参数**:
- `destination`: 目的地城市
- `days`: 出行天数
- `budget`: 总预算（人民币）
- `interests`: 兴趣偏好

**流程**:
1. 命令行参数解析 (argparse)
2. 构建 TravelDemand 对象
3. 传入 build_travel_graph 执行

### 第二阶段：旅行规划 (LangGraph)

**目的**: 在预算约束下生成详细的旅行方案

#### 节点设计

##### 1. researcher_node（目的地调研）

- **文件**: [researcher.py](file:///d:/Travel/agent/researcher.py)
- **输入**: destination, days, interests, simple_city_poi?, weather?
- **输出**: research_result, simple_city_poi, weather
- **功能**: 轻量化素材采集，代码层数据自检，条件工具调用
- **解析器**: `research_parser` (PydanticOutputParser)

**核心设计**:
- 代码层检查 `simple_city_poi` 和 `weather` 是否存在
- 缺失时引导 LLM 调用高德地图工具（maps_text_search, maps_weather）
- 只采集骨架数据（名称、ID、经纬度、片区、分类），不拉取详情
- 数据齐全后清空 messages 避免 token 积累

**工具调用策略**:
- 优先使用 maps_text_search 获取 POI 数据
- 使用 maps_weather 获取天气数据
- 严禁使用 tavily_search（仅在 budget_analyst 中使用）

##### 2. planner_node（行程规划）

- **文件**: [planner.py](file:///d:/Travel/agent/planner.py)
- **输入**: destination, days, interests, simple_city_poi, selected_scenic_detail?
- **输出**: itinerary, selected_scenic_detail, raw_route?
- **功能**: 两段式规划（粗框架 + 精细填充）
- **解析器**: `itinerary_parser`

**核心设计**:
- **阶段1**: 基于 simple_city_poi 的坐标和片区信息搭粗框架，请求选中景点详情
- **阶段2**: 工具结果返回后，基于详情生成完整行程
- 地理聚类：按片区拆分景点，同片区安排在同一天
- 片区内排序：按坐标就近排列

##### 3. budget_analyst_node（预算分配）

- **文件**: [budget_analyst.py](file:///d:/Travel/agent/budget_analyst.py)
- **输入**: destination, days, budget, itinerary, route_related_price?
- **输出**: budget_allocation, route_related_price
- **功能**: 成本核算 + 价格查询
- **解析器**: `budget_allocation_parser`

**核心设计**:
- 代码层检查 `route_related_price` 是否存在
- 缺失时调用 tavily_search 查询路线涉及片区的住宿、餐饮价格
- 基于真实价格核算总花费
- 正向计算：门票→住宿→餐饮→交通→备用金

##### 4. budget_check_node（预算检查）

- **文件**: [budget_check.py](file:///d:/Travel/agent/budget_check.py)
- **输入**: budget, itinerary, budget_allocation
- **输出**: budget_analysis, needs_adjustment, iteration_count
- **功能**: 验证行程是否超预算，判断是否需要调整
- **解析器**: `budget_analysis_parser`

**核心设计**:
- 基于预算分配中的价格估算实际总花费
- 10% 容忍度：超支在预算10%以内不调整
- 超支时增加迭代计数，返回 planner 重新规划

##### 5. tool_node（工具执行节点）

- **文件**: [tool_node.py](file:///d:/Travel/agent/tool_node.py)
- **功能**: 使用 LangGraph 内置 ToolNode 处理工具调用
- **额外能力**: 日志输出、ToolMessage 截断（2000字符上限）

**注册工具**:
- **基础工具**: tavily_search（限制3条结果）
- **高德 MCP 工具**: maps_text_search, maps_weather, maps_search_detail, maps_geo

#### 流程图

```
researcher → [工具调用?] → tool_node → researcher (循环最多5次)
              ↓
          planner → [工具调用?] → tool_node → planner (循环最多5次)
                     ↓
              budget_analyst → [工具调用?] → tool_node → budget_analyst (循环最多5次)
                               ↓
                          budget_check → [超支?] → planner (循环最多3次)
                                              ↓
                                            END
```

#### 条件边

##### should_call_tool_researcher
- 如果最后一条消息是 AIMessage 且有 tool_calls → tool_node
- 如果工具调用次数 >= 5 → 强制进入 planner
- 否则 → planner

##### should_call_tool_planner
- 如果最后一条消息是 AIMessage 且有 tool_calls → tool_node
- 如果工具调用次数 >= 5 → 强制进入 budget_analyst
- 否则 → budget_analyst

##### should_call_tool_budget
- 如果最后一条消息是 AIMessage 且有 tool_calls → tool_node
- 如果工具调用次数 >= 5 → 强制进入 budget_check
- 否则 → budget_check

##### after_tool（工具执行后路由）
- 根据 status 字段决定回到哪个节点：
  - "planning_tool" → planner
  - "budgeting_tool" → budget_analyst
  - 默认 → researcher

##### should_adjust
- 如果 budget_analysis.is_over_budget == True 且 iteration_count < 3 → planner
- 否则 → END

#### 状态流转

```
researching → [tool_calling → tool_node → researching] → budgeting
    ↓
planning → [planning_tool → tool_node → planning] → budgeting
    ↓
budgeting → [budgeting_tool → tool_node → budgeting] → checking
    ↓
checking → [needs_adjustment → planning(循环)] → completed/failed
```

## 工具系统

### 工具注册机制

**文件**: [tool_node.py](file:///d:/Travel/agent/tool_node.py)

```python
# 基础工具（始终可用）
base_tools = [tavily_search]

# 高德 MCP 工具（异步初始化）
gaode_tools = []  # 在 init_gaode_tools() 中动态加载
```

### 工具初始化流程

1. `init_tools()` 在图构建前调用
2. 异步调用 `init_gaode_tools()` 加载高德 MCP 工具
3. 通过 `get_tools()` 获取完整工具列表（base_tools + gaode_tools）
4. 创建 `LoggingToolNode` 实例（带日志和截断功能）

### 工具列表

| 工具 | 来源 | 用途 |
|------|------|------|
| tavily_search | Tavily API | 查询实时价格、消费水平 |
| maps_text_search | 高德 MCP | POI 景点搜索（骨架数据） |
| maps_weather | 高德 MCP | 天气查询 |
| maps_search_detail | 高德 MCP | 景点详情查询 |
| maps_geo | 高德 MCP | 地理编码 |

### 工具调用限制

- 每个节点的工具调用循环最多 5 次（防止无限循环）
- Tavily 搜索结果限制为 3 条（减少 token 消耗）
- ToolMessage 内容截断为 2000 字符（防止 token 超限）

## 关键设计决策

### 1. 为什么选择 LangGraph 而非 CrewAI?

**CrewAI 的问题**:
- 固定顺序执行 (Process.sequential)
- 无法实现动态循环调整
- 厂商识别问题（千帆兼容性）

**LangGraph 的优势**:
- 支持条件分支和循环
- 状态管理更灵活
- 预算感知流程可实现
- 与 LangChain 生态无缝集成

### 2. 为什么预算分析要前置?

**原流程问题**:
```
调研 → 规划 → 预算分析
```
- 规划师只知道预算数字，没有具体限制
- 超支后只能给建议，无法自动调整

**新流程优势**:
```
调研 → 规划 → 预算分配 → 预算检查
```
- 规划师有明确的预算分配方案
- 超支时自动重新规划
- 实现预算感知的闭环

### 3. 为什么使用结构化状态而非纯文本?

**纯文本的问题**:
- 无法保证数据格式一致性
- 预算校验依赖正则解析（脆弱）
- 难以进行程序化的预算调整
- 无法进行类型安全的参数传递

**结构化状态的优势**:
- 强类型校验（Pydantic）
- 直接访问字段属性（`budget_analysis.is_over_budget`）
- 可程序化计算和调整
- 易于单元测试和调试

### 4. 为什么 researcher 使用代码层工具调用而非 LLM 决策?

**LLM 工具选择的问题**:
- LLM 倾向于选择错误的工具（如用 maps_geo 替代 maps_text_search）
- 反复调用错误工具耗尽调用次数
- 导致下游节点因缺少数据而崩溃

**代码层控制的优势**:
- 精确控制工具选择逻辑
- 数据自检确保只采集缺失数据
- 避免无效工具调用

### 5. 为什么采用分层数据架构?

**全量数据采集的问题**:
- 拉取全城景点详情导致 token 超限
- 大量无关数据增加 LLM 处理负担
- 响应速度慢

**分层架构的优势**:
- **骨架层**: simple_city_poi 仅含名称/ID/坐标/片区/分类
- **详情层**: selected_scenic_detail 仅加载路线选中景点
- **价格层**: route_related_price 仅查询涉及片区的价格
- 按需加载，减少 token 消耗，提高响应速度

## 文件结构

### 当前结构

```
Travel/
├── main.py                  # 主程序入口（CLI）✅
├── config/                  # 配置管理 ✅
│   └── config.py            # LLM 配置（千帆/ChatOpenAI）
├── models/                  # 数据模型 ✅
│   └── models.py            # Pydantic 模型定义 + TravelState
├── agent/                   # LangGraph 节点和图构建 ✅
│   ├── researcher.py        # 调研节点
│   ├── planner.py           # 行程规划节点
│   ├── budget_analyst.py    # 预算分析节点
│   ├── budget_check.py      # 预算检查节点
│   ├── tool_node.py         # 工具执行节点（ToolNode）
│   └── graph_builder.py     # 图构建和条件边定义
├── tools/                   # 外部工具 ✅
│   ├── api/                 # API 工具
│   │   └── travily.py       # Tavily 搜索
│   └── mcp/                 # MCP 工具
│       └── gaode_mcp.py     # 高德地图 MCP
├── utils/                   # 公共工具 ✅
│   └── utils.py             # 重试装饰器（支持同步/异步）
├── unuse/                   # 未使用代码
│   └── chat_consultant.py   # 对话顾问（原需求收集层）
├── requirements.txt         # 依赖管理 ✅
├── metadata.yaml            # 项目元数据（用于项目注册/展示）
├── .env                     # 环境变量 ✅
├── .env.example             # 环境变量模板 ✅
├── ARCHITECTURE.md          # 架构说明（本文件） ✅
└── README.md                # 项目说明 ✅
```

### 目标结构（未来扩展）

```
Travel/
├── main.py
├── config/
│   └── config.py            # Pydantic Settings 类（待优化）
├── models/
│   └── models.py
├── agent/
│   ├── researcher.py
│   ├── planner.py
│   ├── budget_analyst.py
│   ├── budget_check.py
│   ├── tool_node.py
│   └── graph_builder.py
├── tools/
│   ├── api/
│   │   └── travily.py
│   └── mcp/
│       └── gaode_mcp.py
├── utils/
│   ├── __init__.py
│   ├── retry.py             # 重试装饰器（抽取）
│   └── logging.py           # 统一日志配置（待实现）
├── api/                     # API 接口层（待实现）
│   ├── __init__.py
│   └── app.py               # FastAPI 服务
├── tests/                   # 测试模块（待实现）
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_nodes.py
│   └── test_graph.py
├── requirements.txt
├── .env
├── .env.example
├── ARCHITECTURE.md
└── README.md
```

## 架构升级路线图

### 阶段 1：节点函数适配结构化模型 ✅

**完成**: 所有节点函数使用 Pydantic 模型输出

**改动文件**:
- `agent/researcher.py` — 代码层数据自检 + 条件工具调用
- `agent/planner.py` — 两段式规划（粗框架 + 精细填充）
- `agent/budget_analyst.py` — 成本核算 + 价格查询
- `agent/budget_check.py` — 预算检查 + 10% 容忍度判断
- `agent/graph_builder.py` — 条件边逻辑改为读取结构化字段
- `agent/tool_node.py` — LangGraph ToolNode + 日志 + 截断

### 阶段 2：工具系统升级 ✅

**完成**: 集成高德 MCP 工具，支持异步初始化

**改动文件**:
- `tools/mcp/gaode_mcp.py` — 高德 MCP 工具加载（带降级处理）
- `tools/api/travily.py` — Tavily 搜索（限制3条结果）
- `agent/tool_node.py` — 动态工具注册 + LoggingToolNode

### 阶段 3：分层数据架构 ✅

**完成**: 轻量化采集策略，按需加载数据

**改动文件**:
- `models/models.py` — 添加 SimplePOI, ScenicDetail, WeatherData, RoughRoute, RoutePrice
- `agent/researcher.py` — 只采集骨架数据
- `agent/planner.py` — 两段式规划，按需获取详情

### 阶段 4：错误处理与公共工具抽取 ⏳

**目标**: 统一错误处理机制，消除重复代码

**改动文件**:
- `utils/retry.py` — 抽取 `retry_on_rate_limit` 装饰器（当前在 utils.py）
- `utils/logging.py` — 统一日志配置（待实现）

### 阶段 5：API 接口层 ⏳

**目标**: 提供 REST API，支持前端集成

**改动文件**:
- `api/__init__.py`
- `api/app.py` — FastAPI 应用

### 阶段 6：配置管理优化 ⏳

**目标**: 完善配置校验和多环境支持

**改动文件**:
- `config/config.py` — 改为 Pydantic Settings 类

### 阶段 7：测试覆盖 ⏳

**目标**: 添加单元测试，保证代码质量

**改动文件**:
- `tests/test_models.py`
- `tests/test_nodes.py`
- `tests/test_graph.py`

## 运行方式

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量（.env文件）
QIANFANG_API_KEY=your_api_key
QIANFANG_BASE_URL=https://qianfan.baidubce.com/v2
QIANFANG_MODEL=ernie-4.5-turbo-32k
TAVILY_API_KEY=your_tavily_api_key
AMAP_MAPS_API_KEY=your_gaode_api_key

# CLI 运行
python main.py --destination "莆田" --days 3 --budget 2000 --interests "文化,美食"

# 输出格式选项
python main.py --destination "莆田" --days 3 --budget 2000 --interests "文化" --output json
```

## 扩展方向

1. **增加更多节点**: 天气查询、签证顾问、汇率转换
2. **优化循环逻辑**: 根据超支程度动态调整策略
3. **增加工具集成**: 机票预订、酒店查询、高德地图 API 直接调用
4. **对话层迁移**: 将需求收集改为 LangGraph
5. **持久化存储**: 保存历史规划方案供参考
6. **行程可视化**: 集成地图展示、时间线视图
7. **多语言支持**: 支持英文等多语言输出
8. **用户偏好学习**: 基于历史记录优化推荐

## 关键工程实践

### Token 管理策略

1. **消息复用**: 避免每次迭代重新构建 System/Human 消息
2. **消息清空**: 节点完成后清空 messages 为后续节点腾出空间
3. **结果截断**: ToolMessage 内容限制为 2000 字符
4. **搜索限制**: Tavily 搜索结果限制为 3 条

### 错误处理策略

1. **速率限制重试**: 所有节点使用 `retry_on_rate_limit` 装饰器
2. **解析失败容错**: Pydantic 解析失败时记录错误并继续流程
3. **工具降级**: 高德 MCP 加载失败时跳过，不影响主流程
4. **循环保护**: 工具调用循环最多 5 次，预算调整最多 3 次

### 日志调试

1. **节点入口/出口日志**: 每个节点打印执行状态
2. **工具调用日志**: ToolNode 打印调用详情和结果预览
3. **状态流转日志**: 条件边打印路由决策
4. **数据自检日志**: researcher/budget_analyst 打印数据缺失情况