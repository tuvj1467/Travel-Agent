# 旅行规划助手 - 任务拆分

## 文档信息
- **版本**: v2.1
- **更新日期**: 2026-07-21

---

## 一、已完成任务

### 阶段 1：基础架构搭建

| ID | 任务 | 状态 | 产出文件 |
|----|------|------|----------|
| T-01 | 搭建 LangGraph 4 节点工作流（researcher → planner → budget_analyst → budget_check） | 已完成 | agent/researcher.py, agent/planner.py, agent/budget_analyst.py, agent/budget_check.py |
| T-02 | 实现 ToolNode 工具执行节点（日志 + 截断） | 已完成 | agent/tool_node.py |
| T-03 | 实现图构建和条件路由 | 已完成 | agent/graph_builder.py |
| T-04 | 定义 Pydantic 数据模型和解析器 | 已完成 | models/models.py |
| T-05 | 实现 CLI 参数解析入口 | 已完成 | main.py |

### 阶段 2：工具集成

| ID | 任务 | 状态 | 产出文件 |
|----|------|------|----------|
| T-06 | 集成高德 MCP 工具（maps_text_search, maps_weather, maps_search_detail, maps_direction） | 已完成 | tools/mcp/gaode_mcp.py |
| T-07 | 实现工具异步初始化 + 动态注册 | 已完成 | agent/tool_node.py |
| T-08 | 移除 Tavily Search 依赖（项目规则禁止） | 已完成 | tools/api/travily.py（保留备用） |

### 阶段 3：核心功能完善

| ID | 任务 | 状态 | 产出文件 |
|----|------|------|----------|
| T-09 | 实现分层数据架构（simple_city_poi → selected_scenic_detail） | 已完成 | agent/researcher.py, models/models.py |
| T-10 | 实现两段式规划（粗框架 + 精细填充） | 已完成 | agent/planner.py |
| T-11 | 实现预算校验闭环（10% 容忍度，3 次迭代） | 已完成 | agent/budget_check.py |
| T-12 | budget_check 改用代码层直接计算（itinerary.total_estimated_cost vs budget） | 已完成 | agent/budget_check.py |

### 阶段 4：架构升级到 11 节点

| ID | 任务 | 状态 | 产出文件 |
|----|------|------|----------|
| T-13 | 新增 collect_preferences 节点（CLI 兼容模式） | 已完成 | agent/collect_preferences.py |
| T-14 | 拆分 search_weather 为独立节点 | 已完成 | agent/search_weather.py |
| T-15 | 新增 search_flights 节点（聚合数据航班搜索） | 已完成 | agent/search_flights.py |
| T-16 | 新增 search_hotels 节点（占位） | 已完成 | agent/search_hotels.py |
| T-17 | 新增 present_and_feedback 节点（用户交互） | 已完成 | agent/present_and_feedback.py |
| T-18 | 新增 refine_itinerary 节点（行程优化） | 已完成 | agent/refine_itinerary.py |
| T-19 | 新增 finalize 节点（最终确认） | 已完成 | agent/finalize.py |
| T-20 | 重构 graph_builder 支持 11 节点 + 完整条件路由 | 已完成 | agent/graph_builder.py |

### 阶段 5：航班搜索集成

| ID | 任务 | 状态 | 产出文件 |
|----|------|------|----------|
| T-21 | 集成聚合数据 juhe_mcp（get_flight_info） | 已完成 | tools/mcp/juhe_mcp.py |
| T-22 | 定义 FlightInfo / FlightResult / FlightResponse 模型 | 已完成 | models/models.py |
| T-23 | 实现 MCP 返回结果解析（FlightResponse Pydantic 实例化） | 已完成 | agent/search_flights.py |
| T-24 | 实现无机场降级处理（has_airport=False） | 已完成 | agent/search_flights.py, agent/present_and_feedback.py |
| T-25 | 定义流程状态枚举 | 已完成 | models/status.py |

### 阶段 6：文档同步

| ID | 任务 | 状态 | 产出文件 |
|----|------|------|----------|
| T-26 | 编写需求文档 | 已完成 | docs/REQUIREMENTS.md |
| T-27 | 编写架构文档 | 已完成 | docs/ARCHITECTURE.md |
| T-28 | 编写项目 README | 已完成 | README.md |
| T-29 | 同步更新全部文档至 v2.1 | 已完成 | docs/*.md, README.md |

---

## 二、待完成任务

### P1（高优先级）

| ID | 任务 | 说明 | 估算 |
|----|------|------|------|
| T-30 | 完善 collect_preferences 的 interrupt 交互收集 | 当前为 CLI 兼容模式，需实现真正的多轮对话收集（缺字段 → 生成提问 → interrupt → 用户输入 → 继续） | 中 |
| T-31 | 实现 search_hotels 节点 | 当前为占位节点，需集成酒店搜索 API（携程/美团 MCP 或第三方 API），按预算筛选 | 大 |
| T-32 | 实现 departure_city 从用户输入获取 | 当前硬编码为"北京"，需从 collect_preferences 或 CLI 参数获取出发城市 | 小 |

### P2（中优先级）

| ID | 任务 | 说明 | 估算 |
|----|------|------|----------|
| T-33 | 增加交通规划节点 | 目的地城市内的交通规划（地铁/公交/打车），估算交通费用 | 中 |
| T-34 | 增加就餐规划节点 | 基于片区推荐餐厅，估算餐饮费用 | 中 |
| T-35 | 预算分析精细化 | 基于航班真实价格、酒店真实价格做更准确的预算分配，而非 LLM 估算 | 中 |
| T-36 | 行程详情增强 | 增加景点营业时间校验、距离计算、游览时长优化 | 中 |

### P3（低优先级）

| ID | 任务 | 说明 | 估算 |
|----|------|------|------|
| T-37 | 提供 FastAPI REST API 接口 | 将 graph 封装为 API 端点，支持前端集成 | 中 |
| T-38 | 支持多目的地规划 | 多城市行程编排 | 大 |
| T-39 | 添加单元测试覆盖 | 模型校验测试、节点函数测试、图流程测试 | 大 |
| T-40 | 行程可视化 | 静态地图展示、时间线视图 | 大 |
| T-41 | 前端 Web 界面 | 基于 Streamlit/Gradio 或纯前端框架 | 大 |
| T-42 | 多语言支持 | 支持英文等多语言行程输出 | 小 |

---

## 三、待修复/优化

| ID | 问题 | 优先级 | 说明 |
|----|------|--------|------|
| B-01 | planner 输出总费用为 0 | 高 | 行程中活动费用未正确计算，导致 total_estimated_cost 始终为 0 |
| B-02 | budget_analysis 的 LLM 估算不够准确 | 中 | LLM 估算的住宿/餐饮费用与实际偏差较大，需要基于真实数据 |
| B-03 | route_adjuster.py 未在主流程中使用 | 低 | 该文件存在但未在 graph_builder 中注册为节点 |
| B-04 | need_adjust / needs_adjustment 字段冗余 | 低 | 两个字段语义相同，考虑统一 |
