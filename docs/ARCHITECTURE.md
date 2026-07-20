# 旅行规划助手 - 项目架构说明

## 项目概述

基于 LangGraph 的智能旅行规划助手，采用 11 节点多智能体协作架构，通过条件循环图实现偏好收集 → 数据搜索 → 行程生成 → 预算校验 → 用户反馈的完整闭环。

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
│  collect_preferences ──→ search_pois ──→ search_weather                  │
│       │                                                         │        │
│       │                                                         ▼        │
│  (条件循环)                                              search_flights   │
│                                                               │          │
│                                                               ▼          │
│                                                         search_hotels     │
│                                                               │          │
│                                                               ▼          │
│                                                     generate_itinerary   │
│                                                          │    │          │
│                                                     ┌────┘    └────┐     │
│                                                     ▼              ▼     │
│                                                tool_node    budget_analysis│
│                                                     │         │    │     │
│                                                     └────┬────┘    ▼     │
│                                                          │    tool_node  │
│                                                          ▼              │
│                                                    budget_check          │
│                                                          │              │
│                                                 ┌───────┴───────┐       │
│                                                 ▼               ▼       │
│                                          (超支→refine)    present_and_   │
│                                                 │          feedback     │
│                                                 │        ┌──┼──┐        │
│                                                 │        ▼  ▼  ▼        │
│                                                 └──generate  │  │       │
│                                                        finalize  │      │
│                                                          refine  collect│
└───────────────────────────────────────────────────────────────────────────┘
                             │
┌────────────────────────────▼──────────────────────────────────────────────┐
│                   输出展示层                                              │
│  - 格式化 CLI 输出 (main.py → format_itinerary)                           │
│  - JSON API 响应                                                          │
└───────────────────────────────────────────────────────────────────────────┘
```

## 技术栈

| 类别 | 技术 | 说明 |
|------|------|------|
| LLM | 百度千帆 ernie-4.5-turbo-32k | 主模型，ChatOpenAI 兼容层调用 |
| 框架 | LangChain 0.3.x + LangGraph 0.2.x | 多智能体协作 + 条件循环图 |
| 地图工具 | 高德 MCP | POI搜索、天气查询、景点详情、路线规划 |
| 航班工具 | 聚合数据 MCP | 航班搜索、价格查询（juhe_mcp） |
| 数据模型 | Pydantic v2 | 结构化数据校验与解析 |
| 配置 | python-dotenv | 环境变量管理 |

## 核心数据模型

### TravelState（状态定义）

```python
{
    # === 用户输入 ===
    "query": str,                              # 用户原始查询
    "preferences": Optional[dict],             # 用户旅行偏好
    # 旧版兼容字段
    "destination": str,                        # 目的地
    "days": int,                               # 出行天数
    "budget": float,                           # 总预算
    "interests": str,                          # 兴趣偏好

    # === 消息与结果 ===
    "messages": list,                          # ToolNode 消息循环
    "simple_city_poi": Optional[List[dict]],   # 全城轻量化景点列表
    "selected_scenic_detail": Optional[List[dict]],  # 选中景点详情
    "weather": Optional[dict],                 # 天气数据
    "flights": Optional[List[dict]],           # 航班信息列表
    "hotels": Optional[List[dict]],            # 酒店信息列表
    "itinerary": Optional[Itinerary],          # 行程规划
    "budget_allocation": Optional[BudgetAllocation],  # 预算分配
    "budget_analysis": Optional[BudgetAnalysis],      # 预算分析

    # === 用户交互 ===
    "feedback": str,                           # 用户反馈
    "user_choice": str,                        # 用户选择
    "final_result": Optional[dict],            # 最终结果

    # === 流程控制 ===
    "need_adjust": bool,                       # 是否需要调整
    "needs_adjustment": bool,                  # 是否需要调整（旧字段）
    "has_airport": bool,                       # 目的地是否有机场
    "iteration_count": int,                    # 迭代次数（最大3次）
    "error": Optional[str],                    # 错误信息
    "status": str,                             # 当前状态
}
```

### 字段填充节点映射

| 字段 | 填充节点 | 来源 |
|------|----------|------|
| simple_city_poi | search_pois（代码层） | 高德 maps_text_search |
| selected_scenic_detail | generate_itinerary（工具调用） | 高德 maps_search_detail |
| weather | search_weather（代码层） | 高德 maps_weather |
| flights | search_flights（代码层） | 聚合 get_flight_info |
| hotels | search_hotels（占位） | 酒店 API（待实现） |
| itinerary | generate_itinerary（LLM） | Planner 两段式规划 |
| budget_allocation | budget_analysis（LLM） | 基于行程核算 |
| budget_analysis | budget_check（代码层） | itinerary.total_estimated_cost vs budget |
| user_choice | present_and_feedback（interrupt） | 用户输入 |

## 详细流程

### 第一阶段：偏好收集

**节点**: `collect_preferences`

检查 preferences 中是否包含必要字段（destination、days、budget），缺失时生成提问并利用 LangGraph interrupt 暂停等待用户输入。

- **状态**: `collecting`
- **路由**: 信息齐全 → `search_pois`；否则自循环

### 第二阶段：数据采集（串行流水线）

#### search_pois（景点调研 → researcher_node）

- **文件**: [agent/researcher.py](file:///d:/Travel/agent/researcher.py)
- **工具**: 高德 `maps_text_search`（骨架）+ `maps_search_detail`（详情）
- **输出**: `simple_city_poi`、`selected_scenic_detail`
- **设计**: 代码层直接调用工具，不经过 LLM，分两阶段采集

#### search_weather（天气查询）

- **文件**: [agent/search_weather.py](file:///d:/Travel/agent/search_weather.py)
- **工具**: 高德 `maps_weather`
- **输出**: `weather`（包含每日天气、温度、风力）

#### search_flights（航班搜索）

- **文件**: [agent/search_flights.py](file:///d:/Travel/agent/search_flights.py)
- **工具**: 聚合 `get_flight_info`（通过 juhe_mcp）
- **输出**: `flights`（List[FlightInfo]，含航司、航班号、时间、价格）
- **解析**: 使用 `FlightResponse(**data)` 直接 Pydantic 实例化
- **无机场处理**: 设置 `has_airport=False`，前端提示"建议高铁出行"

#### search_hotels（酒店搜索 → 占位）

- **文件**: [agent/search_hotels.py](file:///d:/Travel/agent/search_hotels.py)
- **状态**: 当前为占位节点，直接跳过
- **输出**: `hotels` = []

### 第三阶段：行程生成 + 预算校验

#### generate_itinerary（行程规划 → planner_node）

- **文件**: [agent/planner.py](file:///d:/Travel/agent/planner.py)
- **设计**: 两段式规划
  - **阶段1**（粗框架）: 基于 simple_city_poi 坐标/片区搭框架，调用工具获取选中景点详情
  - **阶段2**（精细填充）: 基于详情生成完整 DayPlan，含航班、酒店、天气信息
- **解析器**: `itinerary_parser`
- **路由**: 工具调用 → `tool_node`；完成 → `budget_analysis`；回退 → `search_pois`

#### budget_analysis（预算分析 → budget_analyst_node）

- **文件**: [agent/budget_analyst.py](file:///d:/Travel/agent/budget_analyst.py)
- **功能**: 核算各项费用（门票、住宿、餐饮、交通、机票），生成 BudgetAllocation
- **解析器**: `budget_allocation_parser`
- **路由**: 工具调用 → `tool_node`；完成 → `budget_check`

#### budget_check（预算校验 → budget_check_node）

- **文件**: [agent/budget_check.py](file:///d:/Travel/agent/budget_check.py)
- **逻辑**: 代码层直接比较 `itinerary.total_estimated_cost` vs `budget`
- **容忍度**: 10%，超支在此范围内不触发调整
- **迭代**: 超支时增加 `iteration_count`，最多 3 次
- **解析器**: `budget_analysis_parser`
- **路由**: 超支 → `refine_itinerary`；未超支 → `present_and_feedback`

### 第四阶段：用户交互

#### present_and_feedback（呈现与反馈）

- **文件**: [agent/present_and_feedback.py](file:///d:/Travel/agent/present_and_feedback.py)
- **功能**: 格式化输出行程方案，interrupt 暂停等待用户选择
- **用户选择**: 满意 / 修改 / 调整预算

#### refine_itinerary（行程优化）

- **文件**: [agent/refine_itinerary.py](file:///d:/Travel/agent/refine_itinerary.py)
- **功能**: 结合用户反馈和原行程重新生成
- **路由**: 完成后回到 `generate_itinerary`

#### finalize（最终确认）

- **文件**: [agent/finalize.py](file:///d:/Travel/agent/finalize.py)
- **功能**: 汇总行程方案和费用明细，标记状态为 `completed`

#### tool_node（工具执行节点）

- **文件**: [agent/tool_node.py](file:///d:/Travel/agent/tool_node.py)
- **功能**: LangGraph ToolNode + 日志输出 + ToolMessage 截断（2000字符）
- **注册工具**: 高德 MCP（maps_* 系列）+ 聚合 MCP（get_flight_info）

### 条件路由汇总

| 路由函数 | 源节点 | 目标 |
|----------|--------|------|
| `route_after_collect` | collect_preferences | search_pois / collect_preferences |
| `route_after_generate` | generate_itinerary | tool_node / budget_analysis / search_pois / generate_itinerary |
| `route_after_budget_analysis` | budget_analysis | tool_node / budget_check |
| `route_after_budget_check` | budget_check | present_and_feedback / refine_itinerary |
| `route_after_feedback` | present_and_feedback | finalize / refine_itinerary / collect_preferences |
| `after_tool` | tool_node | generate_itinerary / budget_analysis / search_pois |

### 状态流转

```
collecting → searching_pois → searching_weather → searching_flights → searching_hotels
    ↓
generating → [planning_tool → tool_node → generating] → budgeting
    ↓
budgeting → [budgeting_tool → tool_node → budgeting] → checking
    ↓
checking → [超支 → refining → generating] → presenting
    ↓
presenting → [satisfied → finalized] / [modify → refining] / [adjust_budget → collecting]
```

## 工具系统

### 工具列表

| 工具 | 来源 | 用途 | 调用方式 |
|------|------|------|----------|
| maps_text_search | 高德 MCP | POI 景点搜索 | 代码层 / LLM |
| maps_weather | 高德 MCP | 天气查询 | 代码层 |
| maps_search_detail | 高德 MCP | 景点详情查询 | 代码层 / 工具调用 |
| maps_direction | 高德 MCP | 路线规划 | 工具调用 |
| get_flight_info | 聚合 MCP | 航班搜索 | 代码层 |

### 工具初始化

```python
# 工具在 build_travel_graph 执行前异步初始化
await init_tools()          # 加载高德 MCP + 聚合 MCP
current_tool_node = get_tool_node()  # 动态获取 ToolNode 实例
```

### MCP 工具返回格式说明

- **高德 MCP**: `[{"type": "text", "text": "{...}"}]`，直接用 Pydantic 实例化解析
- **聚合 MCP**: `[{"type": "text", "text": "{...}"}]`，直接用 `FlightResponse(**data)` 解析
- **LLM 工具调用**: 返回 ToolMessage，通过 PydanticOutputParser 解析

## 关键设计决策

### 1. 为什么将单一节点拆分为 11 个独立节点？

**原架构问题**（4 节点）:
- researcher 职责模糊（同时负责景点+天气）
- planner 负载过重（生成行程 + 工具调用 + 回退）
- 无用户反馈机制

**新架构优势**（11 节点）:
- 每个节点单一职责，易于维护和测试
- 串行流水线式数据采集，数据依赖清晰
- 用户反馈闭环，支持交互式修正

### 2. 为什么使用代码层工具调用而非 LLM 决策？

- 精确控制工具选择逻辑，避免 LLM 选错工具
- 零 token 消耗（不调用 LLM）
- 响应速度快（1-2秒 vs 5-10秒）
- 直接使用 Pydantic 实例化解析 MCP 返回数据

### 3. 为什么 MCP 工具返回用 Pydantic 实例化而非解析器？

```
MCP 工具 → list[dict] → json.loads(text) → Pydantic(**dict)   ← 直接实例化
LLM 输出 → raw string → parser.parse(text)                       ← 用解析器
```

规律：**MCP 返回的是已结构化的 JSON（dict），LLM 返回的是文本字符串**。

### 4. 为什么采用分层数据架构？

- **骨架层**: simple_city_poi 仅含名称/ID/坐标/片区/分类
- **详情层**: selected_scenic_detail 仅加载路线选中景点
- 按需加载，减少 token 消耗，提高响应速度

## 文件结构

```
Travel/
├── main.py                     # 主程序入口（CLI + 格式化输出）
├── config/
│   └── config.py               # LLM 配置（千帆/ChatOpenAI）
├── models/
│   ├── models.py               # Pydantic 模型 + TravelState + 解析器
│   └── status.py               # 流程状态枚举
├── agent/
│   ├── collect_preferences.py  # 偏好收集节点
│   ├── researcher.py           # 景点调研节点（search_pois）
│   ├── search_weather.py       # 天气查询节点
│   ├── search_flights.py       # 航班搜索节点
│   ├── search_hotels.py        # 酒店搜索节点（占位）
│   ├── planner.py              # 行程规划节点（generate_itinerary）
│   ├── budget_analyst.py       # 预算分析节点
│   ├── budget_check.py         # 预算校验节点
│   ├── present_and_feedback.py # 呈现与反馈节点
│   ├── refine_itinerary.py     # 行程优化节点
│   ├── finalize.py             # 最终确认节点
│   ├── route_adjuster.py       # 路由调整器
│   ├── tool_node.py            # 工具执行节点（ToolNode）
│   └── graph_builder.py        # 图构建和条件边定义
├── tools/
│   ├── api/
│   │   └── travily.py          # Tavily 搜索
│   └── mcp/
│       ├── gaode_mcp.py        # 高德地图 MCP
│       └── juhe_mcp.py         # 聚合数据 MCP（航班搜索）
├── utils/
│   └── utils.py                # 重试装饰器
├── docs/
│   ├── REQUIREMENTS.md         # 需求文档
│   ├── ARCHITECTURE.md         # 架构说明（本文件）
│   └── TASKS.md                # 任务拆分
├── unuse/
│   └── chat_consultant.py      # 废弃代码（旧对话顾问）
└── requirements.txt            # 依赖管理
```

## 错误处理策略

### 降级策略

| 场景 | 处理方式 |
|------|----------|
| 高德 MCP 加载失败 | 跳过工具，使用 LLM 知识估算 |
| 聚合 MCP 加载失败 | 跳过航班搜索，`flights = []` |
| 景点搜索失败 | 使用空列表，行程生成使用默认景点 |
| 天气查询失败 | 使用空字典，不影响主流程 |
| 目的地无机场 | 设置 `has_airport=False`，前端提示"建议高铁出行" |
| LLM 输出解析失败 | 重试 2 次，仍失败则返回默认值 |
| 速率限制 | 指数退避重试（retry_on_rate_limit 装饰器） |

### 循环保护

- 工具调用循环：最多 5 次
- 预算调整迭代：最多 3 次
- 偏好收集循环：最多 5 次（防止死循环）

### Token 管理

- 节点完成后清空 messages
- ToolMessage 内容截断为 2000 字符
- 避免每次迭代重新构建 System/Human 消息

## 运行方式

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量（.env）
QIANFANG_API_KEY=your_api_key
QIANFANG_BASE_URL=https://qianfan.baidubce.com/v2
AMAP_MAPS_API_KEY=your_gaode_api_key
JUHEFLIGHT_API_KEY=your_juheflight_api_key

# CLI 运行
python main.py --destination "厦门" --days 3 --budget 2000 --interests "自然风光,美食"
```
