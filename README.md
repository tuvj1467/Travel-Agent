# 旅行规划助手

基于 LangChain 和 LangGraph 的智能旅行规划助手，支持结构化行程生成和预算感知的迭代优化。

## 技术栈

- **框架**: LangChain、LangGraph
- **LLM**: 百度千帆 ernie-4.5-turbo-32k（通过环境变量配置）
- **搜索**: 高德地图 MCP（实时景点搜索、天气查询、路线规划）
- **地图**: 高德 MCP（POI搜索、天气查询、景点详情）
- **架构**: 模块化设计（config、models、agent、tools、utils）

## 项目架构

```
Travel/
├── main.py                  # 主程序入口（CLI）
├── config/                  # 配置管理
│   └── config.py            # LLM 配置（千帆/ChatOpenAI）
├── models/                  # 数据模型
│   └── models.py            # Pydantic 模型定义 + TravelState
├── agent/                   # LangGraph 节点和图构建
│   ├── researcher.py        # 调研节点（轻量化素材采集）
│   ├── planner.py           # 行程规划节点（两段式规划）
│   ├── budget_analyst.py    # 预算分析节点（成本核算）
│   ├── budget_check.py      # 预算检查节点（超支判断）
│   ├── tool_node.py         # 工具执行节点（ToolNode）
│   └── graph_builder.py     # 图构建和条件边定义
├── tools/                   # 外部工具
│   ├── api/                 # API 工具
│   │   └── travily.py       # Tavily 搜索
│   └── mcp/                 # MCP 工具
│       └── gaode_mcp.py     # 高德地图 MCP
├── utils/                   # 公共工具
│   └── utils.py             # 重试装饰器
├── requirements.txt         # 依赖管理
├── .env                     # 环境变量
├── .env.example             # 环境变量模板
├── ARCHITECTURE.md          # 架构说明
└── README.md                # 项目说明
```

## 工作流程

1. **参数收集** - 通过命令行参数获取目的地、天数、预算、兴趣偏好
2. **目的地调研** - 使用高德地图工具采集轻量化景点数据和天气信息
3. **行程规划** - 两段式规划（粗框架搭建 + 精细填充）
4. **预算分配** - 基于真实价格核算各项预算分配
5. **预算校验** - 验证行程是否超预算（10%容忍度），必要时自动调整（最多3次迭代）

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

# Tavily 搜索配置
TAVILY_API_KEY=your_tavily_api_key

# 高德地图 MCP 配置（可选）
AMAP_MAPS_API_KEY=your_gaode_api_key
```

## 运行方式

### CLI 模式
```bash
# 基础用法
python main.py --destination "莆田" --days 3 --budget 2000 --interests "文化,美食"

# 输出 JSON 格式
python main.py --destination "莆田" --days 3 --budget 2000 --interests "文化" --output json
```

### API 集成模式

`graph_builder.py` 返回结构化数据，可直接用于前端集成：

```python
from models.models import TravelDemand
from agent.graph_builder import build_travel_graph

demand = TravelDemand(
    destination="莆田",
    days=3,
    budget=2000,
    interests="自然风光"
)
result = await build_travel_graph(demand)
# 返回字典：{destination, days, budget, interests, research_result, budget_allocation, itinerary, budget_analysis, iteration_count}
```

## 特性

- **轻量化采集**: 分层数据架构，只采集路线涉及的景点详情，减少 token 消耗
- **预算约束**: 正向计算预算分配，10%容忍度自动调整
- **防幻觉**: 强化提示词约束，禁止编造价格、地理信息
- **迭代优化**: 超支时自动调整行程（最多3次迭代）
- **工具调用循环**: 每个节点支持最多5次工具调用循环
- **模块化设计**: 清晰的职责分离，易于维护和扩展
- **前端友好**: 返回结构化数据，支持 JSON 格式输出

## 待优化

- [ ] 集成更多地图 API（路径规划、地理编码）
- [ ] 增加酒店搜索节点
- [ ] 增加交通规划节点
- [ ] 增加就餐规划节点
- [ ] 支持多目的地规划
- [ ] 增加行程可视化（静态地图、时间线）
- [ ] 添加单元测试覆盖
- [ ] 提供 FastAPI REST API 接口