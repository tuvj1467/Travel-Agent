# 旅行规划助手 - 需求文档

## 文档信息
- **版本**: v2.1
- **状态**: 开发中
- **更新日期**: 2026-07-21

---

## 一、业务背景

### 1.1 问题陈述
传统旅游方案存在三大痛点：
1. **模板化严重**：攻略网站推荐路线千篇一律，无法贴合个人偏好
2. **信息滞后**：静态知识库无法反映实时价格、天气、景点开放状态
3. **预算失控**：行程规划与预算管理脱节，用户常在旅途中超支

### 1.2 解决方案
基于 LangGraph 多智能体协同框架，构建预算感知的个性化旅行规划系统：
- **多智能体协作**：调研、规划、预算、校验四类节点解耦，共 11 个节点
- **实时数据采集**：通过高德 MCP 获取景点/天气，聚合数据 MCP 获取航班价格
- **预算闭环**：规划-核算-调整的迭代循环，确保行程在预算内
- **人机交互**：支持 interrupt 暂停等待用户输入，实现渐进式需求收集与反馈修正

### 1.3 目标用户
- 自由行游客（25-45岁）
- 注重预算控制的旅行者
- 希望获得个性化行程的游客

---

## 二、用户故事

### 2.1 核心用户故事
**作为**一名自由行游客，
**我希望**输入目的地、天数、预算、兴趣偏好后，系统能生成贴合预算的完整行程方案，
**以便**我能放心出行而不担心超支。

### 2.2 详细用户故事

| ID | 用户故事 | 优先级 | 状态 |
|----|---------|--------|------|
| US-01 | 作为用户，我希望系统能收集我的旅行偏好（目的地、天数、预算、兴趣），缺少信息时主动询问 | P0 | 进行中 |
| US-02 | 作为用户，我希望系统能搜索目的地的景点活动 | P0 | 已完成 |
| US-03 | 作为用户，我希望系统能查询目的地的天气情况 | P0 | 已完成 |
| US-04 | 作为用户，我希望系统能搜索前往目的地的航班信息 | P0 | 已完成 |
| US-05 | 作为用户，我希望系统能根据我的偏好生成结构化的每日行程 | P0 | 已完成 |
| US-06 | 作为用户，我希望系统能核算行程费用并与预算对比 | P0 | 已完成 |
| US-07 | 作为用户，我希望能看到生成的行程并提出修改意见 | P0 | 已完成 |
| US-08 | 作为用户，我希望系统能根据我的反馈优化行程 | P0 | 已完成 |
| US-09 | 作为用户，我希望最终确认行程并输出完整方案 | P0 | 已完成 |
| US-10 | 作为用户，我希望超支时系统能自动调整方案 | P1 | 已完成 |
| US-11 | 作为用户，我希望系统能搜索目的地酒店信息 | P1 | 占位 |

---

## 三、功能性需求

### 3.1 工作流架构

**整体流程图**：

```
collect_preferences → search_pois → search_weather → search_flights → search_hotels
       ↓                                                                 ↓
  (条件循环)                                                    generate_itinerary
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

### 3.2 节点定义

#### 节点列表

| 节点 | 文件 | 职责 | 输入 | 输出 | 状态 |
|------|------|------|------|------|------|
| `collect_preferences` | collect_preferences.py | 收集用户偏好，缺字段时中断询问 | query | preferences | 进行中 |
| `search_pois` | researcher.py | 搜索目的地景点（骨架+详情） | destination, interests | simple_city_poi, selected_scenic_detail | 已完成 |
| `search_weather` | search_weather.py | 查询目的地天气 | destination | weather | 已完成 |
| `search_flights` | search_flights.py | 搜索前往目的地的航班 | destination | flights, has_airport | 已完成 |
| `search_hotels` | search_hotels.py | 搜索目的地酒店 | destination, budget, days | hotels | 占位 |
| `generate_itinerary` | planner.py | 生成结构化每日行程 | preferences, 所有搜索结果 | itinerary | 已完成 |
| `budget_analysis` | budget_analyst.py | 核算各项费用（机票、酒店、门票、餐饮、交通） | itinerary, budget | budget_allocation | 已完成 |
| `budget_check` | budget_check.py | 预算校验，超支时标记调整 | budget_allocation, budget | budget_analysis, need_adjust | 已完成 |
| `present_and_feedback` | present_and_feedback.py | 呈现行程，中断获取用户反馈 | itinerary, budget_allocation | feedback, user_choice | 已完成 |
| `refine_itinerary` | refine_itinerary.py | 根据用户反馈优化行程 | itinerary, feedback | itinerary | 已完成 |
| `finalize` | finalize.py | 确认最终行程，输出结果 | itinerary, budget_allocation | final_result | 已完成 |

#### 节点详细说明

##### 1. collect_preferences（偏好收集节点）

**职责**：收集用户旅行偏好，检查必要字段是否齐全

**必要字段**：
- destination（目的地）
- days（天数）
- budget（预算）
- interests（兴趣标签）

**逻辑**：
- 从 TravelDemand（CLI 参数）或 state.preferences 读取字段
- 若缺少任意字段，生成提问并调用 `interrupt` 暂停等待用户输入
- 用户补充后继续检查，直至信息齐全
- 当前实现：直接从 CLI 参数兼容传递，完全交互收集待实现

**状态**：进行中（CLI 兼容模式已完成，interrupt 交互收集待完善）

##### 2. search_pois（景点搜索节点 → researcher_node）

**职责**：搜索目的地景点，分两阶段采集骨架数据和详情数据

**工具调用**：
- 阶段1：`maps_text_search` — 搜索景点骨架列表（名称、ID、经纬度、片区、分类）
- 阶段2：`maps_search_detail` — 拉取选中景点的详情（门票、营业时间、评分）

**输出**：
- `simple_city_poi`（骨架景点列表）
- `selected_scenic_detail`（选中景点详情，采集上限 20 个）

**设计要点**：
- 代码层直接调用工具，不经过 LLM 决策
- 数据自检机制：缺少数据时自动补采（最多 5 次）
- 使用 `SimplePOI.model_validate()` 解析高德返回数据

##### 3. search_weather（天气查询节点）

**职责**：查询目的地天气情况

**工具调用**：`maps_weather` — 查询目的地未来几天天气

**输出**：`weather`（包含每日天气、温度、风力、日期）

**设计要点**：
- 代码层直接调用工具
- 仅查询目的地城市，不查询其他区域

##### 4. search_flights（航班搜索节点）

**职责**：搜索前往目的地的航班信息

**工具调用**：`get_flight_info`（聚合数据 juhe_mcp）

**输入**：
- departure_city（出发城市，默认：北京）
- destination（目的地城市）
- travel_date（出行日期，默认：当天）

**输出**：
- `flights`（List[FlightInfo]，含航司名称、航班号、时间、票价、经停数）
- `has_airport`（bool，目的地是否有机场）

**解析方式**：
```
MCP 返回 → [{"type": "text", "text": "{...}"}]
  → json.loads(text)
  → FlightResponse(**data)        ← 直接 Pydantic 实例化
  → flight_response.result.flight_info  ← List[FlightInfo]
```

**降级处理**：
- 目的地无机场：设置 `has_airport=False`，`flights = []`
- 聚合 MCP 加载失败：跳过航班搜索，`flights = []`
- 前端无机场时提示"建议高铁出行"

**FlightInfo 字段**（仅保留必要字段）：

| 字段 | 类型 | 说明 |
|------|------|------|
| airline_name | str | 航司名称 |
| flight_no | str | 航班号 |
| departure_time | str | 出发时间 |
| arrival_time | str | 到达时间 |
| arrival_name | str | 到达机场名称 |
| duration | str | 航班时长 |
| transfer_num | int | 航段数量 |
| ticket_price | float | 参考票价 |

##### 5. search_hotels（酒店搜索节点）

**职责**：搜索目的地酒店信息

**状态**：占位节点，当前直接跳过，`hotels = []`

**待实现**：
- 集成酒店搜索 API（携程/美团等）
- 按预算范围筛选
- 按评分和位置排序

##### 6. generate_itinerary（行程生成节点 → planner_node）

**职责**：将偏好和所有搜索结果交给 LLM，生成结构化每日行程

**输入**：
- preferences（用户偏好）
- simple_city_poi（景点骨架列表）
- selected_scenic_detail（景点详情）
- weather（天气信息）
- flights（航班信息，可选）
- hotels（酒店信息，可选）

**输出**：`itinerary`（结构化每日行程，含 DayPlan、Activity、total_estimated_cost）

**内部流程（两段式规划）**：
1. **阶段1**（搭粗框架）: 基于 simple_city_poi 的坐标/片区信息搭框架，调用工具获取选中景点详情
2. **阶段2**（精细填充）: 工具结果返回后，基于详情生成完整行程

**设计要点**：
- 地理聚类：按片区拆分景点，同片区安排在同一天
- 片区内排序：按坐标就近排列
- 含航班、酒店、天气信息（如果可用）
- 解析器：`itinerary_parser`

##### 7. budget_analysis（预算分析节点 → budget_analyst_node）

**职责**：核算各项费用并与预算对比

**费用分类**：
- 机票：根据搜索到的航班价格
- 酒店：根据搜索到的酒店价格
- 门票：根据景点详情中的门票价格
- 餐饮：根据目的地消费水平和天数估算
- 交通：根据路线距离估算

**输出**：`budget_allocation`（预算分配方案）
**解析器**：`budget_allocation_parser`

##### 8. budget_check（预算校验节点 → budget_check_node）

**职责**：预算校验，超支时生成调整建议

**逻辑**（代码层直接计算）：
- 从 `itinerary.total_estimated_cost` 获取预估总花费
- 与 `budget` 比较差值
- 预算容忍度为 10%，超支在 10% 以内不触发调整
- 超支时设置 `needs_adjustment = True`，增加 `iteration_count`
- 最多循环调整 3 次

**输出**：`budget_analysis`（预算分析结果）、`needs_adjustment`（是否需要调整）
**解析器**：`budget_analysis_parser`

##### 9. present_and_feedback（呈现与反馈节点）

**职责**：呈现行程给用户，中断获取反馈

**逻辑**：
- 格式化输出行程方案（每日安排、费用明细）
- 输出目的地是否有航班（has_airport）
- 调用 `interrupt` 暂停等待用户反馈

**用户选择**：满意（satisfied）/ 修改（modify）/ 调整预算（adjust_budget）

**输出**：`feedback`（用户反馈）、`user_choice`（用户选择）

##### 10. refine_itinerary（行程优化节点）

**职责**：根据用户反馈优化行程

**逻辑**：
- 结合用户反馈和原行程重新生成
- 更新 itinerary
- 完成后路由回 `generate_itinerary` 重新规划

**输出**：`itinerary`（优化后的行程）

##### 11. finalize（最终确认节点）

**职责**：确认最终行程，输出结果

**逻辑**：
- 汇总行程方案和费用明细
- 生成最终输出格式
- 标记状态为 `completed`

**输出**：`final_result`（最终结果）

### 3.3 条件路由

#### 路由函数列表

| 路由函数 | 源节点 | 目标节点映射 |
|----------|--------|-------------|
| `route_after_collect` | collect_preferences | search_pois（信息齐全）/ collect_preferences（继续收集） |
| `route_after_generate` | generate_itinerary | tool_node / budget_analysis / search_pois / generate_itinerary |
| `route_after_budget_analysis` | budget_analysis | tool_node / budget_check |
| `after_tool` | tool_node | generate_itinerary / budget_analysis / search_pois |
| `route_after_budget_check` | budget_check | present_and_feedback（未超支）/ refine_itinerary（超支） |
| `route_after_feedback` | present_and_feedback | finalize（满意）/ refine_itinerary（修改）/ collect_preferences（调整预算） |

#### 路由逻辑

```python
def route_after_collect(state):
    """偏好收集后的路由：信息齐全 → search_pois，否则自循环"""
    prefs = state.get("preferences")
    if prefs and prefs.get("destination") and prefs.get("days", 0) > 0 and prefs.get("budget", 0) > 0:
        return "search_pois"
    return "collect_preferences"

def route_after_budget_check(state):
    """预算校验后的路由：超支 且 未达最大迭代 → refine"""
    if state["budget_analysis"].is_over_budget and state.get("iteration_count", 0) < 3:
        return "refine_itinerary"
    return "present_and_feedback"

def route_after_feedback(state):
    """用户反馈后的路由"""
    choice = state.get("user_choice", "satisfied")
    if choice == "satisfied":
        return "finalize"
    elif choice == "modify":
        return "refine_itinerary"
    elif choice == "adjust_budget":
        return "collect_preferences"
    return "present_and_feedback"
```

### 3.4 状态管理

#### 状态字段定义

| 字段 | 类型 | 说明 | 填充节点 |
|------|------|------|----------|
| query | str | 用户原始查询 | 输入 |
| preferences | dict | 用户旅行偏好 | collect_preferences |
| destination | str | 目的地 | 输入/collect_preferences |
| days | int | 出行天数 | 输入/collect_preferences |
| budget | float | 总预算 | 输入/collect_preferences |
| interests | str | 兴趣偏好 | 输入/collect_preferences |
| messages | list | 消息循环 | ToolNode/LLM |
| simple_city_poi | list | 轻量化景点列表 | search_pois |
| selected_scenic_detail | list | 选中景点详情 | search_pois / generate_itinerary |
| weather | dict | 天气信息 | search_weather |
| flights | list | 航班信息列表 | search_flights |
| hotels | list | 酒店信息列表 | search_hotels |
| itinerary | Itinerary | 行程方案 | generate_itinerary |
| budget_allocation | BudgetAllocation | 预算分配 | budget_analysis |
| budget_analysis | BudgetAnalysis | 预算分析结果 | budget_check |
| need_adjust | bool | 是否需要调整 | budget_check |
| needs_adjustment | bool | 是否需要调整（兼容旧字段） | budget_check |
| has_airport | bool | 目的地是否有机场 | search_flights |
| feedback | str | 用户反馈 | present_and_feedback |
| user_choice | str | 用户选择 | present_and_feedback |
| final_result | dict | 最终结果 | finalize |
| iteration_count | int | 迭代次数 | budget_check |
| status | str | 当前状态 | 各节点 |

#### 状态枚举

| 状态值 | 含义 | 所属节点 |
|--------|------|----------|
| collecting | 收集偏好中 | collect_preferences |
| searching_pois | 搜索景点中 | search_pois |
| searching_weather | 查询天气中 | search_weather |
| searching_flights | 搜索航班中 | search_flights |
| searching_hotels | 搜索酒店中 | search_hotels |
| generating | 生成行程中 | generate_itinerary |
| planning_tool | 规划阶段工具调用 | generate_itinerary |
| budgeting | 预算分析中 | budget_analysis |
| budgeting_tool | 预算阶段工具调用 | budget_analysis |
| checking | 预算校验中 | budget_check |
| presenting | 呈现行程中 | present_and_feedback |
| refining | 优化行程中 | refine_itinerary |
| completed | 已完成 | finalize |
| failed | 失败 | - |

### 3.5 错误处理

#### 降级策略

| 场景 | 降级策略 |
|------|---------|
| 高德 MCP 加载失败 | 跳过工具，使用 LLM 知识估算 |
| 聚合 MCP 加载失败 | 跳过航班搜索，`flights = []` |
| 景点搜索失败 | 使用空列表，行程生成时使用默认景点 |
| 天气查询失败 | 使用空字典，不影响主流程 |
| 目的地无机场 | `has_airport=False`，前端提示"建议高铁出行" |
| LLM 输出解析失败 | 重试 2 次，仍失败则返回默认值 |
| 速率限制 | 指数退避重试（retry_on_rate_limit），最多 3 次 |

---

## 四、非功能性需求

### 4.1 性能需求

| 指标 | 要求 |
|------|------|
| 单次规划响应时间 | ≤ 60 秒 |
| 单节点工具调用次数 | ≤ 5 次 |
| ToolMessage 长度 | ≤ 2000 字符 |
| 预算调整迭代次数 | ≤ 3 次 |
| 景点详情采集上限 | ≤ 20 个 |

### 4.2 可靠性需求
- LLM 输出必须通过 Pydantic 模型校验
- 工具调用失败时记录错误并继续流程（降级处理）
- MCP 加载失败不影响主流程
- 速率限制自动重试（retry_on_rate_limit 装饰器）

### 4.3 可维护性需求
- 节点函数必须为异步（async def）
- 节点函数必须使用 `retry_on_rate_limit` 装饰器
- 节点完成后必须清空 `messages`
- 命名遵循 snake_case，类名遵循 PascalCase

### 4.4 安全需求
- API Key 通过环境变量加载，禁止硬编码
- 禁止将敏感信息写入日志
- 禁止使用 Tavily Search（项目规则）

---

## 五、验收标准

### 5.1 功能验收
- [x] 能搜索目的地景点活动并返回详情
- [x] 能查询目的地天气
- [x] 能搜索航班信息（含无机场降级处理）
- [x] 能生成结构化每日行程
- [x] 能核算各项费用并与预算对比
- [x] 超支时能生成调整建议
- [x] 能呈现行程并获取用户反馈
- [x] 能根据用户反馈优化行程
- [x] 能确认最终行程并输出结果
- [ ] 缺少必要字段时系统能主动询问用户（CLI 兼容模式已完成，interrupt 模式待完善）
- [ ] 能搜索目的地酒店信息（占位状态）

### 5.2 交互验收
- [x] interrupt 机制能正确暂停等待用户输入
- [x] 用户补充信息后能继续流程
- [x] 用户反馈后能正确路由到对应节点
- [x] 最多支持 3 次预算调整迭代

### 5.3 质量验收
- [x] 所有 LLM 输出通过 Pydantic 校验
- [x] 工具调用失败时有降级策略
- [x] 符合命名规范和编码规范

---

## 六、边界与约束

### 6.1 不做的事
- 不做多目的地规划
- 不做实时预订（机票、酒店）
- 不做用户账号系统

### 6.2 技术约束
- LLM：百度千帆 ernie-4.5-turbo-32k
- 框架：LangChain 0.3.x + LangGraph 0.2.x
- 地图工具：仅使用高德 MCP（禁止 Tavily Search）
- 航班工具：聚合数据 juhe_mcp（get_flight_info）
- Python：3.12+

### 6.3 数据约束
- 景点详情数据最多采集 20 个
- 天气数据仅查询目的地城市
- 航班结果截取 top 3 条展示

### 6.4 解析规则
- MCP 工具返回（list[dict]）→ 直接 Pydantic 实例化解析
- LLM 输出（raw string）→ 通过 PydanticOutputParser 解析
- 正则表达式解析仅在 Pydantic 解析失败时使用

---

## 七、术语表

| 术语 | 含义 |
|------|------|
| POI | Point of Interest，兴趣点（景点） |
| ScenicDetail | 景点详情模型 |
| FlightInfo | 航班信息模型（聚合数据） |
| FlightResponse | 航班 API 响应模型 |
| Interrupt | LangGraph 中断机制，用于暂停等待用户输入 |
| Checkpoint | LangGraph 状态检查点，用于会话续跑 |
| MCP | Model Context Protocol，模型上下文协议 |
| retry_on_rate_limit | 速率限制重试装饰器 |
