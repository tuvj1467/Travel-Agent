# 旅行规划助手

基于 LangChain 和 LangGraph 的智能旅行规划助手，支持多智能体协作生成预算感知的旅行方案，涵盖景点搜索、航班查询、酒店搜索、行程规划和预算校验。

## 技术栈

- **框架**: LangChain 0.3.x、LangGraph 0.2.x
- **LLM**: 百度千帆 ernie-4.5-turbo-32k（通过 ChatOpenAI 兼容层调用）
- **地图**: 高德 MCP（POI搜索、天气查询、景点详情、路线规划）
- **航班**: 聚合数据 MCP（航班搜索、价格查询）
- **数据模型**: Pydantic v2 结构化校验
- **配置**: python-dotenv 环境变量管理

## 项目架构

```
Travel/
├── main.py                     # 主程序入口（CLI）
├── config/
│   └── config.py               # LLM 配置（千帆/ChatOpenAI）
├── models/
│   ├── models.py               # Pydantic 模型定义 + TravelState
│   └── status.py               # 流程状态枚举
├── agent/                      # LangGraph 节点和图构建
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
│   ├── ARCHITECTURE.md         # 架构说明
│   └── TASKS.md                # 任务拆分
├── requirements.txt            # 依赖管理
├── .env / .env.example         # 环境变量
└── README.md                   # 项目说明
```

## 工作流程

```
collect_preferences → search_pois → search_weather → search_flights → search_hotels
       ↓                                                              ↓
  (interrupt 缺字段暂停)                                      generate_itinerary
                                                                     ↓
                                                              budget_analysis
                                                                     ↓
                                                              budget_check
                                                                     ↓
                                                          present_and_feedback
                                                                     ↓
                                                      ┌───────┬───────┐
                                                      ↓       ↓       ↓
                                                  finalize  refine  collect_preferences
                                                   (满意)   (修改)    (调整预算)
```

### 节点说明

| 节点 | 职责 | 输入 | 输出 |
|------|------|------|------|
| `collect_preferences` | 收集用户偏好，缺字段时中断询问 | query | preferences |
| `search_pois` | 搜索目的地景点（骨架+详情） | destination, interests | selected_scenic_detail |
| `search_weather` | 查询目的地天气 | destination | weather |
| `search_flights` | 搜索前往目的地的航班 | destination, departure_city | flights |
| `search_hotels` | 搜索目的地酒店（占位） | destination, budget, days | hotels |
| `generate_itinerary` | 生成结构化每日行程 | preferences, 所有搜索结果 | itinerary |
| `budget_analysis` | 核算各项费用 | itinerary, budget | budget_allocation |
| `budget_check` | 预算校验，超支判断 | budget_allocation, budget | budget_analysis, need_adjust |
| `present_and_feedback` | 呈现行程，获取用户反馈 | itinerary, budget_allocation | feedback, user_choice |
| `refine_itinerary` | 根据反馈优化行程 | itinerary, feedback | itinerary |
| `finalize` | 确认最终行程，输出结果 | itinerary, budget_allocation | final_result |

## 环境配置

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 配置环境变量（创建 `.env` 文件）：

```bash
# 千帆 API 配置
QIANFANG_API_KEY=your_qianfan_api_key
QIANFANG_BASE_URL=https://qianfan.baidubce.com/v2
QIANFANG_MODEL=ernie-4.5-turbo-32k

# 高德地图 MCP 配置
AMAP_MAPS_API_KEY=your_gaode_api_key

# 聚合数据航班 API 配置
JUHEFLIGHT_API_KEY=your_juheflight_api_key
```

## 运行方式

### CLI 模式

```bash
# 基础用法
python main.py --destination "厦门" --days 3 --budget 2000 --interests "自然风光,美食"

# 输出 JSON 格式
python main.py --destination "厦门" --days 3 --budget 2000 --interests "文化" --output json
```

### API 集成模式

`graph_builder.py` 返回结构化数据，可直接用于前端集成：

```python
from models.models import TravelDemand
from agent.graph_builder import build_travel_graph

demand = TravelDemand(
    destination="厦门",
    days=3,
    budget=2000,
    interests="自然风光"
)
result = await build_travel_graph(demand)
# 返回字典：{destination, days, budget, interests, itinerary, budget_allocation, budget_analysis, ...}
```

## 特性

- **多智能体协作**: 11 个节点解耦，调研、规划、预算、校验、反馈各司其职
- **轻量化采集**: 分层数据架构，只采集路线涉及的景点详情，减少 token 消耗
- **预算约束**: 正向计算预算分配，10% 容忍度自动调整，最多 3 次迭代
- **实时数据**: 通过高德 MCP 获取实时景点/天气，通过聚合数据获取航班价格
- **用户反馈闭环**: 支持 interrupt 暂停等待用户选择（满意/修改/调整预算）
- **防幻觉**: 强化提示词约束，禁止编造价格、地理信息
- **模块化设计**: 清晰的职责分离，易于维护和扩展
- **前端友好**: 返回结构化数据，支持 JSON 格式输出

## 待优化

- [ ] 实现 search_hotels 节点（当前为占位实现）
- [ ] 实现 collect_preferences 的 interrupt 交互收集
- [ ] 增加交通规划节点
- [ ] 增加就餐规划节点
- [ ] 支持多目的地规划
- [ ] 增加行程可视化（静态地图、时间线）
- [ ] 添加单元测试覆盖
- [ ] 提供 FastAPI REST API 接口
