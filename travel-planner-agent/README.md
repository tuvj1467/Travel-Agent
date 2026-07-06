# 旅行规划Agent

基于LangChain和LangGraph的智能旅行规划助手，支持交互式对话和结构化行程生成。

## 技术栈

- **框架**: LangChain、LangGraph
- **LLM**: 千帆 ernie-4.5-turbo-32k
- **搜索**: Tavily Search（实时价格和地理信息）
- **架构**: 模块化设计（models、chat_consultant、graph_nodes、graph_builder）

## 项目架构

```
travel-planner-agent/
├── agent.py              # 主程序入口（CLI交互）
├── config.py             # 配置文件（LLM、Tavily初始化）
├── models.py             # 数据模型（TravelState、TravelDemand）
├── chat_consultant.py     # 对话顾问（需求收集）
├── graph_nodes.py        # LangGraph节点函数
├── graph_builder.py      # LangGraph图构建
└── requirements.txt      # 依赖包
```

## 工作流程

1. **对话收集需求** - 通过交互式对话收集目的地、天数、预算、兴趣偏好
2. **目的地调研** - 使用Tavily搜索实时价格和地理信息
3. **预算分配** - 正向计算预算分配（刚性成本→必需成本→弹性成本）
4. **行程规划** - 在预算约束下规划详细行程
5. **预算校验** - 验证行程是否超支，必要时调整

## 环境配置

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 配置环境变量（创建 `.env` 文件）：
```bash
# 千帆API配置
QIANFAN_API_KEY=your_qianfan_api_key
QIANFAN_SECRET_KEY=your_qianfan_secret_key
QIANFAN_BASE_URL=https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat

# 智谱AI配置（备用）
ZHIPU_API_KEY=your_zhipu_api_key

# Tavily搜索配置
TAVILY_API_KEY=your_tavily_api_key
```

## 运行方式

### CLI交互模式
```bash
python agent.py
```

然后按照提示输入旅行需求：
```
你: 900去莆田旅游3天，自然风光
助手: 听起来你打算去莆田玩3天，总预算是900元对吗？不过我还想了解一下你的兴趣偏好...
```

### API集成模式

`graph_builder.py` 返回结构化数据，可直接用于前端集成：

```python
from models import TravelDemand
from graph_builder import build_travel_graph

demand = TravelDemand(
    destination="莆田",
    days=3,
    budget=900,
    interests="自然风光"
)
result = build_travel_graph(demand)
# 返回字典：{destination, days, budget, interests, research_result, budget_allocation, itinerary, budget_analysis, iteration_count}
```



## 特性

- **实时搜索**：集成Tavily搜索获取最新价格和地理信息
- **预算约束**：正向计算预算分配，避免负数和倒推凑数
- **防幻觉**：强化提示词约束，禁止编造价格、地理信息
- **迭代优化**：超支时自动调整行程（最多3次迭代）
- **模块化设计**：清晰的职责分离，易于维护和扩展
- **前端友好**：返回结构化数据，支持JSON格式输出

## 待优化

- [ ] 集成高德地图API（路径规划、地理编码）
- [ ] 增加更多验证节点（事实校验、偏好匹配）
- [ ] 支持多目的地规划
- [ ] 增加行程可视化（静态地图）
