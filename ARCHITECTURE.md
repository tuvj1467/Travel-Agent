# 旅行规划助手 - 项目架构说明

## 项目概述

基于 LangGraph 的智能旅行规划助手，通过对话收集用户需求，使用多节点协作生成预算感知的旅行方案。系统采用结构化状态管理，支持条件分支和循环调整，确保行程在预算约束内生成。

## 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     用户交互层                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   CLI 终端   │    │  REST API   │    │  Web 前端    │     │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘     │
└─────────┼──────────────────┼──────────────────┼─────────────┘
          │                  │                  │
┌─────────▼──────────────────▼──────────────────▼─────────────┐
│                   需求收集层                                │
│          DemandChatConsultant (LangChain LCEL)             │
│  - 自然语言解析 → 结构化参数提取 → 用户确认                  │
└────────────────────────────┬──────────────────────────────┘
                             │ TravelDemand
┌────────────────────────────▼──────────────────────────────┐
│                   旅行规划层 (LangGraph)                   │
│  ┌──────────┐   ┌──────────────┐   ┌──────────┐          │
│  │researcher│ → │budget_analyst│ → │  planner │          │
│  └──────────┘   └──────────────┘   └────┬─────┘          │
│                                         │                  │
│                                         ▼                  │
│                                   ┌────────────┐          │
│                                   │budget_check│          │
│                                   └──────┬─────┘          │
│                                         │                  │
│                          ┌───────────────┴───────────────┐ │
│                          ▼                               ▼ │
│                       (超支?)                         END  │
│                          │                               │
│                          ▼                               │
│                       planner ← 循环最多3次              │
└───────────────────────────────────────────────────────────┘
                             │
┌────────────────────────────▼──────────────────────────────┐
│                   输出展示层                                │
│  - 格式化 CLI 输出                                         │
│  - JSON API 响应                                           │
│  - 行程可视化                                              │
└───────────────────────────────────────────────────────────┘
```

## 技术栈

| 类别 | 技术 | 版本 | 说明 |
|------|------|------|------|
| LLM | 百度千帆 | ernie-4.5-turbo-32k | 主模型 |
| 对话框架 | LangChain | 0.3.x | LCEL 链式调用 |
| 多节点框架 | LangGraph | 0.2.x | StateGraph 状态机 |
| 搜索工具 | Tavily Search | - | 实时价格和地理信息 |
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
    "research_result": Optional[ResearchResult],    # 调研结果（结构化）
    "budget_allocation": Optional[BudgetAllocation], # 预算分配（结构化）
    "itinerary": Optional[Itinerary],                # 行程规划（结构化）
    "budget_analysis": Optional[BudgetAnalysis],     # 预算分析（结构化）
    "iteration_count": int,                    # 迭代次数
    "needs_adjustment": bool,                  # 是否需要调整
    "error": Optional[str],                    # 错误信息
    "status": str                              # 当前状态
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

ResearchResult (调研结果) → BudgetAllocation (预算分配) → Itinerary (行程) → BudgetAnalysis (预算分析)
```

### 字段说明

| 字段 | 类型 | 说明 | 填充节点 | 状态 |
|------|------|------|----------|------|
| destination | str | 目的地名称 | 输入 | ✅ |
| days | int | 出行天数 | 输入 | ✅ |
| budget | float | 总预算 | 输入 | ✅ |
| interests | str | 兴趣偏好 | 输入 | ✅ |
| research_result | ResearchResult | 调研结果 | researcher | ⏳ |
| budget_allocation | BudgetAllocation | 预算分配方案 | budget_analyst | ⏳ |
| itinerary | Itinerary | 行程规划 | planner | ⏳ |
| budget_analysis | BudgetAnalysis | 预算分析结果 | budget_check | ⏳ |
| iteration_count | int | 迭代次数 | budget_check | ✅ |
| needs_adjustment | bool | 是否需要调整 | budget_check | ✅ |
| error | str | 错误信息 | 任意节点 | ✅ |
| status | str | 当前状态 | 任意节点 | ✅ |

> **说明**: ✅ 表示已在 models.py 中定义，⏳ 表示待在 graph_nodes.py 中实现

## 详细流程

### 第一阶段：需求收集 (DemandChatConsultant)

**目的**: 通过对话收集旅行需求的4个核心参数

**核心参数**:
- `destination`: 目的地城市
- `days`: 出行天数
- `budget`: 总预算（人民币）
- `interests`: 兴趣偏好

**流程**:
1. 用户输入自然语言需求
2. LLM 分析输入，识别缺失信息
3. 主动提问引导用户补充信息
4. 必要时调用 Tavily 搜索推荐目的地
5. 使用 PydanticOutputParser 从响应中提取结构化参数
6. 参数完整后请求用户确认

**工具调用**:
- `tavily_search`: 联网搜索热门目的地、消费水平等信息

**状态管理**:
- `InMemoryChatMessageHistory`: 保存对话历史
- `TravelDemand`: 结构化参数模型（Pydantic）

### 第二阶段：旅行规划 (LangGraph)

**目的**: 在预算约束下生成详细的旅行方案

#### 节点设计

##### 1. researcher_node（目的地调研）

- **输入**: destination, days, interests
- **输出**: research_result (ResearchResult) ⏳
- **功能**: 调研目的地信息，特别关注消费水平
- **解析器**: `research_parser` (PydanticOutputParser)

**目标输出结构**:
```python
ResearchResult(
    destination="莆田",
    best_season="春季",
    cost_items=[
        CostItem(name="经济型住宿", amount=150, category="accommodation"),
        CostItem(name="餐饮人均", amount=50, category="food"),
        ...
    ],
    notes="妈祖文化发源地"
)
```

##### 2. budget_analyst_node（预算分配）

- **输入**: destination, days, budget, research_result
- **输出**: budget_allocation (BudgetAllocation) ⏳
- **功能**: 在总预算范围内制定各项预算分配方案
- **解析器**: `budget_allocation_parser`

**目标输出结构**:
```python
BudgetAllocation(
    total_budget=900,
    categories=[
        CostItem(name="住宿", amount=450, category="accommodation"),
        CostItem(name="餐饮", amount=150, category="food"),
        ...
    ],
    remaining=100,
    assessment="充足"
)
```

##### 3. planner_node（行程规划）

- **输入**: destination, days, interests, budget_allocation, research_result
- **输出**: itinerary (Itinerary) ⏳
- **功能**: 在预算约束下规划详细行程
- **解析器**: `itinerary_parser`

**目标输出结构**:
```python
Itinerary(
    destination="莆田",
    days=3,
    day_plans=[
        DayPlan(
            day=1,
            activities=[
                Activity(name="湄洲岛", time_slot="morning", cost=65),
                ...
            ],
            estimated_cost=150
        ),
        ...
    ],
    total_estimated_cost=850
)
```

##### 4. budget_check_node（预算检查）

- **输入**: budget, itinerary, budget_allocation
- **输出**: budget_analysis (BudgetAnalysis), needs_adjustment ⏳
- **功能**: 验证行程是否超预算，判断是否需要调整
- **解析器**: `budget_analysis_parser`

**目标输出结构**:
```python
BudgetAnalysis(
    total_estimated=850,
    is_over_budget=False,
    over_amount=0,
    suggestions=[]
)
```

#### 流程图

```
researcher → budget_analyst → planner → budget_check
                                              ↓
                                         (超支?)
                                        /      \
                                   (是)        (否)
                                     ↓            ↓
                                  planner        END
                                     ↑
                                 (最多3次循环)
```

#### 条件边 (should_adjust)

- 如果 `budget_analysis.is_over_budget == True` 且 `iteration_count < 3`: 返回 planner 重新规划
- 否则: 结束流程

#### 状态流转

```
researching → budgeting → planning → checking
                                    ↓
                        ┌──────────┴──────────┐
                        ▼                     ▼
                   planning(循环)          completed
                        │
                   iteration >= 3
                        ▼
                    failed
```

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
调研 → 预算分配 → 规划 → 预算检查
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

### 4. 为什么对话层不用 LangGraph?

**考虑因素**:
- 当前对话流程较简单（单轮循环）
- LangChain 的 LCEL 已能满足需求
- 避免过度设计

**未来可扩展**:
- 如需复杂对话流程（如条件分支、多轮对话），可迁移到 LangGraph

## 文件结构

### 当前结构

```
travel-planner-agent/
├── agent.py                 # CLI 入口 ✅
├── config.py                # 配置文件 ✅
├── models.py                # 数据模型（已优化为结构化） ✅
├── chat_consultant.py       # 对话顾问（需求收集） ✅
├── graph_nodes.py           # LangGraph 节点函数 ⏳
├── graph_builder.py         # LangGraph 图构建 ⏳
├── requirements.txt         # 依赖管理 ✅
├── .env                     # 环境变量 ✅
├── .env.example             # 环境变量模板 ✅
├── ARCHITECTURE.md          # 架构说明（本文件） ✅
└── README.md                # 项目说明 ✅
```

### 目标结构（架构升级后）

```
travel-planner-agent/
├── agent.py                 # CLI 入口
├── config.py                # 配置管理 (Pydantic Settings)
├── models.py                # 数据模型
├── chat_consultant.py       # 对话顾问
├── graph_nodes.py           # LangGraph 节点函数
├── graph_builder.py         # LangGraph 图构建
├── api/                     # API 接口层（待实现）
│   ├── __init__.py
│   └── app.py               # FastAPI 服务
├── utils/                   # 公共工具（待实现）
│   ├── __init__.py
│   ├── retry.py             # 重试装饰器
│   └── logging.py           # 日志配置
├── tests/                   # 测试模块（待实现）
│   ├── __init__.py
│   ├── test_models.py       # 模型解析测试
│   ├── test_nodes.py        # 节点函数测试
│   └── test_graph.py        # 流程图测试
├── requirements.txt
├── .env
├── .env.example
├── ARCHITECTURE.md
└── README.md
```

## 架构升级路线图

### 阶段 1：节点函数适配结构化模型（进行中）

**目标**: 让所有节点函数使用新的 Pydantic 模型输出

**改动文件**:
- `graph_nodes.py` — 四个节点函数改为输出结构化对象
- `graph_builder.py` — 条件边逻辑改为读取结构化字段

**预期产出**:
- 节点函数使用 `PydanticOutputParser` 解析 LLM 输出
- `budget_check_node` 直接读取 `is_over_budget` 字段

### 阶段 2：错误处理与公共工具抽取

**目标**: 统一错误处理机制，消除重复代码

**改动文件**:
- `utils/__init__.py` — 新建工具模块
- `utils/retry.py` — 抽取 `retry_on_rate_limit` 装饰器
- `utils/logging.py` — 统一日志配置

**预期产出**:
- 统一的重试机制
- 结构化日志输出

### 阶段 3：API 接口层

**目标**: 提供 REST API，支持前端集成

**改动文件**:
- `api/__init__.py`
- `api/app.py` — FastAPI 应用

**预期产出**:
- POST `/api/plan` — 行程规划接口
- POST `/api/chat` — 对话接口

### 阶段 4：配置管理优化

**目标**: 完善配置校验和多环境支持

**改动文件**:
- `config.py` — 改为 Pydantic Settings 类

**预期产出**:
- 启动时配置校验
- 支持开发/测试/生产多环境

### 阶段 5：测试覆盖

**目标**: 添加单元测试，保证代码质量

**改动文件**:
- `tests/test_models.py`
- `tests/test_nodes.py`
- `tests/test_graph.py`

**预期产出**:
- 至少 10 个测试用例

## 运行方式

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量（.env文件）
QIANFANG_API_KEY=your_api_key
QIANFANG_BASE_URL=https://qianfan.baidubce.com/v2
QIANFANG_MODEL=ernie-4.5-turbo-32k
TAVILY_API_KEY=your_tavily_api_key

# CLI 运行
python agent.py

# API 运行（阶段3完成后）
python -m api.app
```

## 扩展方向

1. **增加更多节点**: 天气查询、签证顾问、汇率转换
2. **优化循环逻辑**: 根据超支程度动态调整策略
3. **增加工具集成**: 机票预订、酒店查询、高德地图API
4. **对话层迁移**: 将 DemandChatConsultant 改为 LangGraph
5. **持久化存储**: 保存历史规划方案供参考
6. **行程可视化**: 集成地图展示、时间线视图