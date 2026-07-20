"""
LangGraph 图构建模块 v2.0 - 基于需求文档的 11 节点工作流

节点流转：
collect_preferences → search_pois → search_weather → search_flights → search_hotels
  → generate_itinerary → budget_analysis → budget_check → present_and_feedback
    → finalize / refine_itinerary / collect_preferences
"""
from langgraph.graph import StateGraph, END
from langchain_core.messages import AIMessage, ToolMessage

from models.models import TravelState, TravelDemand, UserPreferences
from agent.researcher import researcher_node
from agent.tool_node import init_tools, get_tool_node
from agent.budget_analyst import budget_analyst_node
from agent.planner import planner_node
from agent.budget_check import budget_check_node
from agent.collect_preferences import collect_preferences_node
from agent.search_weather import search_weather_node
from agent.search_flights import search_flights_node
from agent.search_hotels import search_hotels_node
from agent.present_and_feedback import present_and_feedback_node
from agent.refine_itinerary import refine_itinerary_node
from agent.finalize import finalize_node


# ========== 条件路由函数 ==========

def route_after_collect(state: TravelState) -> str:
    """偏好收集后的路由：信息齐全 → search_pois，否则自循环"""
    prefs = state.get("preferences")
    if prefs:
        p = prefs if isinstance(prefs, dict) else prefs.model_dump()
        if p.get("destination") and p.get("days", 0) > 0 and p.get("budget", 0) > 0:
            return "search_pois"
    return "collect_preferences"


def route_after_generate(state: TravelState) -> str:
    """生成行程后的路由：工具调用 / 预算分析 / 回退 / 自循环"""
    status = state.get("status", "")
    # 回退到 researcher
    if status == "researcher":
        return "search_pois"
    # 工具调用循环
    if status == "planning_tool":
        return "tool_node"
    # 自循环重新生成
    if status == "planning":
        return "generate_itinerary"
    # 完成生成，进入预算分析
    if state.get("itinerary"):
        return "budget_analysis"
    return "budget_analysis"


def route_after_budget_analysis(state: TravelState) -> str:
    """预算分析后的路由：工具调用 / 预算校验"""
    messages = state.get("messages", [])
    tool_call_count = sum(1 for m in messages if isinstance(m, ToolMessage))
    MAX_TOOL_CALLS = 5

    if tool_call_count >= MAX_TOOL_CALLS:
        return "budget_check"

    if messages:
        last_message = messages[-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tool_node"

    return "budget_check"


def route_after_budget_check(state: TravelState) -> str:
    """预算校验后的路由：未超支 → present_and_feedback，超支 → refine_itinerary"""
    budget_analysis = state.get("budget_analysis")
    if budget_analysis and budget_analysis.is_over_budget and state.get("iteration_count", 0) < 3:
        return "refine_itinerary"
    return "present_and_feedback"


def route_after_feedback(state: TravelState) -> str:
    """用户反馈后的路由"""
    choice = state.get("user_choice", "satisfied")
    if choice == "satisfied":
        return "finalize"
    elif choice == "modify":
        return "refine_itinerary"
    elif choice == "adjust_budget":
        return "collect_preferences"
    return "present_and_feedback"


def after_tool(state: TravelState) -> str:
    """工具执行后，根据 status 决定回到哪个节点"""
    status = state.get("status", "")
    if status == "planning_tool":
        return "generate_itinerary"
    if status == "budgeting_tool":
        return "budget_analysis"
    return "search_pois"


# ========== 图构建 ==========

async def build_travel_graph(demand: TravelDemand) -> dict:
    """构建并执行 v2.0 旅行规划工作流

    Args:
        demand: 用户旅行需求参数

    Returns:
        dict: 包含最终行程和预算的完整结果
    """
    # 初始化所有工具
    await init_tools()

    # 构建初始状态
    initial_state: TravelState = {
        # 用户输入
        "query": "",
        "preferences": None,
        # 旧版兼容字段
        "destination": demand.destination or "",
        "days": demand.days or 0,
        "budget": demand.budget or 0.0,
        "interests": demand.interests or "",
        # 消息和结果
        "messages": [],
        "simple_city_poi": None,
        "selected_scenic_detail": None,
        "weather": None,
        "flights": None,
        "hotels": None,
        "itinerary": None,
        "budget_allocation": None,
        "budget_analysis": None,
        # 用户交互
        "feedback": "",
        "user_choice": "",
        "final_result": None,
        # 流程控制
        "need_adjust": False,
        "needs_adjustment": False,
        "has_airport": False,
        "iteration_count": 0,
        "error": None,
        "status": "collecting",
    }

    workflow = StateGraph(TravelState)

    # 获取工具节点
    current_tool_node = get_tool_node()

    # ---- 注册所有节点 ----
    workflow.add_node("collect_preferences", collect_preferences_node)
    workflow.add_node("search_pois", researcher_node)
    workflow.add_node("search_weather", search_weather_node)
    workflow.add_node("search_flights", search_flights_node)
    workflow.add_node("search_hotels", search_hotels_node)
    workflow.add_node("generate_itinerary", planner_node)
    workflow.add_node("tool_node", current_tool_node)
    workflow.add_node("budget_analysis", budget_analyst_node)
    workflow.add_node("budget_check", budget_check_node)
    workflow.add_node("present_and_feedback", present_and_feedback_node)
    workflow.add_node("refine_itinerary", refine_itinerary_node)
    workflow.add_node("finalize", finalize_node)

    # ---- 设置入口 ----
    workflow.set_entry_point("collect_preferences")

    # ---- 偏好收集 → 搜索阶段 ----
    workflow.add_conditional_edges(
        "collect_preferences",
        route_after_collect,
        {
            "search_pois": "search_pois",
            "collect_preferences": "collect_preferences",
        }
    )

    # ---- 搜索阶段（直连） ----
    workflow.add_edge("search_pois", "search_weather")
    workflow.add_edge("search_weather", "search_flights")
    workflow.add_edge("search_flights", "search_hotels")
    workflow.add_edge("search_hotels", "generate_itinerary")

    # ---- 规划阶段（工具调用循环 + 自循环） ----
    workflow.add_conditional_edges(
        "generate_itinerary",
        route_after_generate,
        {
            "tool_node": "tool_node",
            "budget_analysis": "budget_analysis",
            "search_pois": "search_pois",
            "generate_itinerary": "generate_itinerary",
        }
    )

    # ---- 工具节点路由 ----
    workflow.add_conditional_edges(
        "tool_node",
        after_tool,
        {
            "generate_itinerary": "generate_itinerary",
            "budget_analysis": "budget_analysis",
        }
    )

    # ---- 预算阶段（工具调用循环） ----
    workflow.add_conditional_edges(
        "budget_analysis",
        route_after_budget_analysis,
        {
            "tool_node": "tool_node",
            "budget_check": "budget_check",
        }
    )

    # ---- 预算校验 → 呈现反馈 ----
    workflow.add_conditional_edges(
        "budget_check",
        route_after_budget_check,
        {
            "present_and_feedback": "present_and_feedback",
            "refine_itinerary": "refine_itinerary",
        }
    )

    # ---- 呈现反馈 → 最终路由 ----
    workflow.add_conditional_edges(
        "present_and_feedback",
        route_after_feedback,
        {
            "finalize": "finalize",
            "refine_itinerary": "refine_itinerary",
            "collect_preferences": "collect_preferences",
            "present_and_feedback": "present_and_feedback",
        }
    )

    # ---- 行程优化 → 回到规划 ----
    workflow.add_edge("refine_itinerary", "generate_itinerary")

    # ---- 最终确认 → 结束 ----
    workflow.add_edge("finalize", END)

    # ---- 编译并执行 ----
    app = workflow.compile()

    print("=" * 50)
    print(f"  旅行规划助手 v2.0")
    print(f"  目的地: {demand.destination}")
    print(f"  天数: {demand.days}天")
    print(f"  预算: ¥{demand.budget:.0f}")
    print("=" * 50)

    print("\n[1/6] 收集偏好...")
    final_state = await app.ainvoke(initial_state)

    # 构建返回结果
    result = {
        "destination": final_state.get("destination", ""),
        "days": final_state.get("days", 0),
        "budget": final_state.get("budget", 0.0),
        "interests": final_state.get("interests", ""),
        "status": final_state.get("status", ""),
        "error": final_state.get("error"),
        "iteration_count": final_state.get("iteration_count", 0),
        "simple_city_poi": [
            poi.model_dump()
            for poi in final_state.get("simple_city_poi") or []
        ] if final_state.get("simple_city_poi") else None,
        "selected_scenic_detail": [
            detail.model_dump()
            for detail in final_state.get("selected_scenic_detail") or []
        ] if final_state.get("selected_scenic_detail") else None,
        "itinerary": final_state["itinerary"].model_dump()
        if final_state.get("itinerary") else None,
        "budget_allocation": final_state["budget_allocation"].model_dump()
        if final_state.get("budget_allocation") else None,
        "budget_analysis": final_state["budget_analysis"].model_dump()
        if final_state.get("budget_analysis") else None,
        "final_result": final_state.get("final_result"),
    }

    return result
