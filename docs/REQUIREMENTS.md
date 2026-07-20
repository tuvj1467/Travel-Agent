# 旅行规划助手 - 需求文档

## 文档信息
- **版本**: v2.0
- **状态**: 规划中
- **更新日期**: 2026-07-20

---

## 一、业务背景

### 1.1 问题陈述
传统旅游方案存在三大痛点：
1. **模板化严重**：攻略网站推荐路线千篇一律，无法贴合个人偏好
2. **信息滞后**：静态知识库无法反映实时价格、天气、景点开放状态
3. **预算失控**：行程规划与预算管理脱节，用户常在旅途中超支

### 1.2 解决方案
基于 LangGraph 多智能体协同框架，构建预算感知的个性化旅行规划系统：
- **多智能体协作**：调研、规划、预算、校验四类节点解耦
- **实时数据采集**：通过高德 MCP 获取最新景点、天气、价格数据
- **预算闭环**：规划-核算-调整的迭代循环，确保行程在预算内
- **人机交互**：支持中断等待用户输入，实现渐进式需求收集与反馈修正

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

| ID | 用户故事 | 优先级 |
|----|---------|--------|
| US-01 | 作为用户，我希望系统能收集我的旅行偏好（目的地、天数、预算、兴趣），缺少信息时主动询问 | P0 |
| US-02 | 作为用户，我希望系统能搜索目的地的景点活动 | P0 |
| US-03 | 作为用户，我希望系统能查询目的地的天气情况 | P0 |
| US-04 | 作为用户，我希望系统能根据我的偏好生成结构化的每日行程 | P0 |
| US-05 | 作为用户，我希望系统能核算行程费用并与预算对比 | P0 |
| US-06 | 作为用户，我希望能看到生成的行程并提出修改意见 | P0 |
| US-07 | 作为用户，我希望系统能根据我的反馈优化行程 | P0 |
| US-08 | 作为用户，我希望最终确认行程并输出完整方案 | P0 |
| US-09 | 作为用户，我希望超支时系统能自动调整方案 | P1 |

---

## 三、功能性需求

### 3.1 工作流架构

**整体流程图**：

```
collect_preferences → search_pois → search_weather → search_flights → search_hotels → generate_itinerary → budget_analysis → budget_check → present_and_feedback
                          ↓                   ↓                ↓                ↓                                                  ↓
                     (interrupt)         (interrupt)        (可选)           (可选)                                         (interrupt)
                          ↓                   ↓                ↓                ↓                                                  ↓
                 用户补充信息         用户补充信息          航班信息         酒店信息                                      用户反馈/确认
                                                                                                                                    ↓
                                                                                                                     ┌───────────────┼───────────────┐
                                                                                                                     ↓               ↓               ↓
                                                                                                               满意→finalize   修改→refine_itinerary  调整预算
                                                                                                                                    ↓
                                                                                                                               generate_itinerary（循环）
```

### 3.2 节点定义

#### 节点列表

| 节点 | 职责 | 输入 | 输出 | 是否中断 |
|------|------|------|------|----------|
| `collect_preferences` | 收集用户旅行偏好，缺字段时中断询问 | query, preferences? | preferences | 是 |
| `search_pois` | 搜索目的地景点活动 | destination, interests | selected_scenic_detail | 否 |
| `search_weather` | 查询目的地天气 | destination | weather | 否 |
| `search_flights` | 搜索航班信息 | destination, departure_city, travel_date | flights | 否 |
| `search_hotels` | 搜索酒店信息 | destination, budget, days | hotels | 否 |
| `generate_itinerary` | 生成结构化每日行程 | preferences, selected_scenic_detail, weather, flights, hotels | itinerary | 否 |
| `budget_analysis` | 核算各项费用（机票、酒店、门票、餐饮、交通） | itinerary, budget | budget_allocation | 否 |
| `budget_check` | 预算校验，超支时生成调整建议 | budget_allocation, budget | budget_analysis, need_adjust | 否 |
| `present_and_feedback` | 呈现行程，中断获取用户反馈 | itinerary, budget_allocation | feedback, user_choice | 是 |
| `refine_itinerary` | 根据用户反馈优化行程 | itinerary, feedback | itinerary | 否 |
| `finalize` | 确认最终行程，输出结果 | itinerary, budget_allocation | final_result | 否 |

#### 节点详细说明

##### 1. collect_preferences（偏好收集节点）

**职责**：收集用户旅行偏好，检查必要字段是否齐全

**必要字段**：
- destination（目的地）
- days（天数）
- budget（预算）
- interests（兴趣标签）

**逻辑**：
- 若缺少任意字段，生成提问并调用 `interrupt` 暂停等待用户输入
- 用户补充后继续检查，直至信息齐全
- 若信息齐全直接传递到下一个节点

##### 2. search_pois（景点搜索节点）

**职责**：基于目的地和兴趣搜索景点活动

**工具调用**：
- `maps_text_search`：搜索景点列表（骨架数据）
- `maps_search_detail`：查询景点详情（详情数据）

**输出**：`selected_scenic_detail`（景点详情列表）

**注意**：researcher 的输出是 `selected_scenic_detail`，不是 `simple_city_poi`

##### 3. search_weather（天气查询节点）

**职责**：查询目的地天气情况

**工具调用**：
- `maps_weather`：查询目的地天气

**输出**：`weather`（天气信息）

##### 4. search_flights（航班搜索节点）

**职责**：搜索前往目的地的航班信息

**输入**：
- departure_city（出发城市）
- destination（目的地城市）
- travel_date（出行日期）

**工具调用**：
- 航班搜索工具（如飞猪、携程等）

**输出**：`flights`（航班信息列表，包含航班号、时间、价格）

**注意**：此节点为可选节点，若用户未提供出发城市或选择自驾/高铁，则跳过

##### 5. search_hotels（酒店搜索节点）

**职责**：搜索目的地酒店信息

**输入**：
- destination（目的地城市）
- budget（预算）
- days（天数）

**工具调用**：
- 酒店搜索工具（如携程、美团等）

**输出**：`hotels`（酒店信息列表，包含名称、价格、评分、位置）

**注意**：此节点为可选节点，若用户选择住民宿或亲友家，则跳过

##### 6. generate_itinerary（行程生成节点）

**职责**：将偏好和所有搜索结果交给 LLM，生成结构化每日行程

**输入**：
- preferences（用户偏好）
- selected_scenic_detail（景点详情）
- weather（天气信息）
- flights（航班信息，可选）
- hotels（酒店信息，可选）

**输出**：`itinerary`（结构化每日行程）

**内部流程**：
1. 筛选阶段：根据兴趣偏好筛选景点
2. 聚类阶段：按地理片区聚类，分配到每天
3. 排序阶段：根据开放时间、距离优化每日景点顺序
4. 生成阶段：输出完整 Itinerary（含航班、酒店、活动、时长、费用）

##### 7. budget_analysis（预算分析节点）

**职责**：核算各项费用并与预算对比

**费用分类**：
- 机票：根据搜索到的航班价格
- 酒店：根据搜索到的酒店价格
- 门票：根据景点详情中的门票价格
- 餐饮：根据目的地消费水平和天数估算
- 交通：根据路线距离估算

**输出**：`budget_allocation`（预算分配方案）

##### 8. budget_check（预算校验节点）

**职责**：预算校验，超支时生成调整建议

**逻辑**：
- 计算预估总花费与预算的差值
- 预算容忍度为 10%，超支在 10% 以内不触发调整
- 超支时生成调整建议，标记 `need_adjust = True`
- 最多循环调整 3 次

**输出**：`budget_analysis`（预算分析结果）、`need_adjust`（是否需要调整）

##### 9. present_and_feedback（呈现与反馈节点）

**职责**：呈现行程给用户，中断获取反馈

**逻辑**：
- 格式化输出行程方案（每日安排、费用明细）
- 调用 `interrupt` 暂停等待用户反馈
- 用户反馈可能为：满意、修改、调整预算

**输出**：`feedback`（用户反馈）、`user_choice`（用户选择）

##### 10. refine_itinerary（行程优化节点）

**职责**：根据用户反馈优化行程

**输入**：
- itinerary（原行程）
- feedback（用户反馈）

**逻辑**：
- 结合用户反馈和原行程重新生成
- 更新 itinerary

**输出**：`itinerary`（优化后的行程）

##### 11. finalize（最终确认节点）

**职责**：确认最终行程，输出结果

**输入**：
- itinerary（最终行程）
- budget_allocation（预算分配）

**输出**：`final_result`（最终结果）

**逻辑**：
- 汇总行程方案和费用明细
- 生成最终输出格式
- 标记状态为 completed

### 3.3 条件路由

#### 路由函数列表

| 路由函数 | 源节点 | 目标节点映射 |
|----------|--------|-------------|
| `route_after_collect` | collect_preferences | search_pois（信息齐全）/ collect_preferences（继续收集） |
| `route_after_budget_check` | budget_check | present_and_feedback（未超支）/ refine_itinerary（超支） |
| `route_after_feedback` | present_and_feedback | finalize（满意）/ refine_itinerary（修改）/ collect_preferences（调整预算） |

#### 路由逻辑

```python
def route_after_collect(state):
    """偏好收集后的路由"""
    if state.get("preferences") and _is_complete(state["preferences"]):
        return "search_pois"
    return "collect_preferences"

def route_after_budget_check(state):
    """预算校验后的路由"""
    if state.get("need_adjust"):
        return "refine_itinerary"
    return "present_and_feedback"

def route_after_feedback(state):
    """用户反馈后的路由"""
    choice = state.get("user_choice")
    if choice == "satisfied":
        return "finalize"
    elif choice == "modify":
        return "refine_itinerary"
    elif choice == "adjust_budget":
        return "collect_preferences"
    return "present_and_feedback"
```

### 3.4 状态管理

#### 状态枚举规范

| 状态值 | 含义 | 所属节点 |
|--------|------|----------|
| collecting | 收集偏好中 | collect_preferences |
| searching_pois | 搜索景点中 | search_pois |
| searching_weather | 查询天气中 | search_weather |
| searching_flights | 搜索航班中 | search_flights |
| searching_hotels | 搜索酒店中 | search_hotels |
| generating | 生成行程中 | generate_itinerary |
| budgeting | 预算分析中 | budget_analysis |
| checking | 预算校验中 | budget_check |
| presenting | 呈现行程中 | present_and_feedback |
| refining | 优化行程中 | refine_itinerary |
| finalized | 已完成 | finalize |
| failed | 失败 | - |

#### 状态字段定义

| 字段 | 类型 | 说明 | 初始值 |
|------|------|------|--------|
| query | str | 用户原始查询 | "" |
| preferences | dict | 用户旅行偏好 | {} |
| selected_scenic_detail | list | 景点详情列表 | [] |
| weather | dict | 天气信息 | {} |
| flights | list | 航班信息列表 | [] |
| hotels | list | 酒店信息列表 | [] |
| itinerary | Itinerary | 行程方案 | None |
| budget_allocation | BudgetAllocation | 预算分配 | None |
| budget_analysis | BudgetAnalysis | 预算分析 | None |
| need_adjust | bool | 是否需要调整 | False |
| feedback | str | 用户反馈 | "" |
| user_choice | str | 用户选择 | "" |
| final_result | dict | 最终结果 | {} |
| iteration_count | int | 迭代次数 | 0 |
| status | str | 当前状态 | "collecting" |
| messages | list | 消息列表 | [] |

### 3.5 错误处理

#### 降级策略

| 场景 | 降级策略 |
|------|---------|
| 高德 MCP 加载失败 | 跳过工具，使用 LLM 知识估算 |
| 景点搜索失败 | 使用空列表，行程生成时使用默认景点 |
| 天气查询失败 | 使用空字典，不影响主流程 |
| LLM 输出解析失败 | 重试 2 次，仍失败则返回默认值 |
| 速率限制 | 指数退避重试，最多 3 次 |

---

## 四、非功能性需求

### 4.1 性能需求
| 指标 | 要求 |
|------|------|
| 单次规划响应时间 | ≤ 60 秒 |
| 单节点工具调用次数 | ≤ 5 次 |
| ToolMessage 长度 | ≤ 2000 字符 |
| 预算调整迭代次数 | ≤ 3 次 |

### 4.2 可靠性需求
- LLM 输出必须通过 Pydantic 模型校验
- 工具调用失败时记录错误并继续流程（降级处理）
- 高德 MCP 加载失败不影响主流程
- 速率限制自动重试（最多 3 次，间隔 2 秒）

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
- [ ] 缺少必要字段时系统能主动询问用户
- [ ] 能搜索目的地景点活动并返回详情
- [ ] 能查询目的地天气
- [ ] 能生成结构化每日行程
- [ ] 能核算各项费用并与预算对比
- [ ] 超支时能生成调整建议
- [ ] 能呈现行程并获取用户反馈
- [ ] 能根据用户反馈优化行程
- [ ] 能确认最终行程并输出结果

### 5.2 交互验收
- [ ] interrupt 机制能正确暂停等待用户输入
- [ ] 用户补充信息后能继续流程
- [ ] 用户反馈后能正确路由到对应节点
- [ ] 最多支持 3 次预算调整迭代

### 5.3 质量验收
- [ ] 所有 LLM 输出通过 Pydantic 校验
- [ ] 工具调用失败时有降级策略
- [ ] 符合命名规范和编码规范

---

## 六、边界与约束

### 6.1 不做的事
- 不做多目的地规划
- 不做实时预订（机票、酒店）
- 不做用户账号系统

### 6.2 技术约束
- LLM：百度千帆 ernie-4.5-turbo-32k
- 框架：LangChain 0.3.x + LangGraph 0.2.x
- 地图：仅使用高德 MCP（禁止 Tavily）
- Python：3.12+

### 6.3 数据约束
- 景点详情数据最多查询 20 个
- 天气数据仅查询目的地城市

---

## 七、术语表

| 术语 | 含义 |
|------|------|
| POI | Point of Interest，兴趣点（景点） |
| ScenicDetail | 景点详情模型 |
| Interrupt | LangGraph 中断机制，用于暂停等待用户输入 |
| Checkpoint | LangGraph 状态检查点，用于会话续跑 |
| MCP | Model Context Protocol，模型上下文协议 |