# 旅行规划助手 - 项目架构说明

## 项目概述

基于 LangGraph 的智能旅行规划助手，通过对话收集用户需求，使用多 Agent 协作生成预算感知的旅行方案。

## 整体架构

```
用户交互层
    ↓
需求收集层 (DemandChatConsultant)
    ↓
旅行规划层 (LangGraph)
    ↓
输出展示层
```

## 技术栈

- **LLM**: 百度千帆 (ernie-4.5-turbo-32k)
- **对话框架**: LangChain (ChatOpenAI, ChatPromptTemplate)
- **多Agent框架**: LangGraph (StateGraph)
- **搜索工具**: Tavily Search
- **状态管理**: LangGraph TypedDict
- **参数解析**: Pydantic

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
5. 使用正则表达式从对话历史中提取参数
6. 参数完整后请求用户确认

**工具调用**:
- `tavily_search`: 联网搜索热门目的地、消费水平等信息

**状态管理**:
- `InMemoryChatMessageHistory`: 保存对话历史
- `TravelDemand`: 结构化参数模型

### 第二阶段：旅行规划 (LangGraph)

**目的**: 在预算约束下生成详细的旅行方案

**状态定义 (TravelState)**:
```python
{
    "destination": str,           # 目的地
    "days": int,                 # 天数
    "budget": float,              # 预算
    "interests": str,             # 兴趣
    "research_result": str,       # 调研结果
    "budget_allocation": str,     # 预算分配
    "itinerary": str,            # 行程规划
    "budget_analysis": str,       # 预算分析
    "iteration_count": int,       # 迭代次数
    "needs_adjustment": bool      # 是否需要调整
}
```

**节点设计**:

1. **researcher_node** (目的地调研)
   - 输入: destination, days, interests
   - 输出: research_result
   - 功能: 调研目的地信息，特别关注消费水平（住宿、餐饮、交通、门票价格）

2. **budget_analyst_node** (预算分配)
   - 输入: destination, days, budget, research_result
   - 输出: budget_allocation
   - 功能: 在总预算范围内制定各项预算分配方案

3. **planner_node** (行程规划)
   - 输入: destination, days, interests, budget_allocation, research_result
   - 输出: itinerary
   - 功能: 在预算约束下规划详细行程

4. **budget_check_node** (预算检查)
   - 输入: budget, itinerary, budget_allocation
   - 输出: budget_analysis, needs_adjustment
   - 功能: 验证行程是否超预算，判断是否需要调整

**流程图**:
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

**条件边 (should_adjust)**:
- 如果超支且迭代次数 < 3: 返回 planner 重新规划
- 否则: 结束流程

**预算感知特性**:
- 预算分析在规划之前进行（前置预算分配）
- 规划师有明确的预算限制
- 超支时自动循环调整
- 最多3次迭代防止无限循环

### 第三阶段：输出展示

**输出格式**:
```
============================================================
📋 旅行规划报告
============================================================

📍 目的地：XXX
📅 天数：X天
💰 预算：XXX元
🎯 兴趣：XXX

============================================================
🔍 目的地调研
============================================================
[调研结果]

============================================================
💵 预算分配方案
============================================================
[预算分配]

============================================================
🗓️ 详细行程规划
============================================================
[行程规划]

============================================================
📊 预算分析
============================================================
[预算分析]

============================================================
迭代次数：X
============================================================
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

### 3. 为什么对话层不用 LangGraph?

**考虑因素**:
- 当前对话流程较简单（单轮循环）
- LangChain 的 LCEL 已能满足需求
- 避免过度设计

**未来可扩展**:
- 如需复杂对话流程（如条件分支、多轮对话），可迁移到 LangGraph

## 文件结构

```
travel-planner-agent/
├── agent.py              # 主程序
├── config.py             # 配置文件
├── requirements.txt      # 依赖管理
├── .env                  # 环境变量
├── ARCHITECTURE.md       # 架构说明（本文件）
└── README.md             # 项目说明
```

## 运行方式

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量（.env文件）
QIANFANG_API_KEY=your_api_key
QIANFANG_BASE_URL=https://qianfan.baidubce.com/v2
QIANFANG_MODEL=ernie-4.5-turbo-32k
TAVILY_API_KEY=your_tavily_api_key

# 运行
python agent.py
```

## 扩展方向

1. **增加更多节点**: 天气查询、签证顾问、汇率转换
2. **优化循环逻辑**: 根据超支程度动态调整策略
3. **增加工具集成**: 机票预订、酒店查询
4. **对话层迁移**: 将 DemandChatConsultant 改为 LangGraph
5. **持久化存储**: 保存历史规划方案供参考
