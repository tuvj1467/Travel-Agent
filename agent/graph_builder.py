"""
LangGraph 图构建模块 - 适配结构化输出和工具调用循环

设计原则：
1. 使用条件边路由实现工具调用循环
2. researcher_node → [有tool_calls] → tool_node → researcher_node（循环）
3. researcher_node → [无tool_calls] → budget_analyst（继续流程）
"""
from langgraph.graph import StateGraph, END
from langchain_core.messages import AIMessage

from models.models import TravelState, TravelDemand
from agent.researcher import researcher_node
from agent.tool_node import init_tools, get_tool_node
from agent.budget_analyst import budget_analyst_node
from agent.planner import planner_node
from agent.budget_check import budget_check_node


def should_call_tool_researcher(state: TravelState) -> str:
    """条件边：researcher 的工具调用路由"""
    from langchain_core.messages import AIMessage, ToolMessage
    
    messages = state.get("messages", [])
    tool_call_count = sum(1 for m in messages if isinstance(m, ToolMessage))
    MAX_TOOL_CALLS = 5
    
    if tool_call_count >= MAX_TOOL_CALLS:
        print(f"[DEBUG] researcher 工具调用达上限（{tool_call_count}/{MAX_TOOL_CALLS}），强制进入 planner")
        return "planner"
    
    if messages:
        last_message = messages[-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            print(f"[DEBUG] researcher 需要调用工具（已完成 {tool_call_count}/{MAX_TOOL_CALLS} 次）")
            return "tool_node"
    
    print(f"[DEBUG] researcher 完成采集，流转到 planner")
    return "planner"


def should_call_tool_planner(state: TravelState) -> str:
    """条件边：planner 的工具调用路由"""
    from langchain_core.messages import AIMessage, ToolMessage
    
    messages = state.get("messages", [])
    tool_call_count = sum(1 for m in messages if isinstance(m, ToolMessage))
    MAX_TOOL_CALLS = 5
    
    if tool_call_count >= MAX_TOOL_CALLS:
        print(f"[DEBUG] planner 工具调用达上限（{tool_call_count}/{MAX_TOOL_CALLS}），强制进入 budget_analyst")
        return "budget_analyst"
    
    if messages:
        last_message = messages[-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            print(f"[DEBUG] planner 需要调用工具（已完成 {tool_call_count}/{MAX_TOOL_CALLS} 次）")
            return "tool_node"
    
    print(f"[DEBUG] planner 完成规划，流转到 budget_analyst")
    return "budget_analyst"


def should_call_tool_budget(state: TravelState) -> str:
    """条件边：budget_analyst 的工具调用路由"""
    from langchain_core.messages import AIMessage, ToolMessage
    
    messages = state.get("messages", [])
    tool_call_count = sum(1 for m in messages if isinstance(m, ToolMessage))
    MAX_TOOL_CALLS = 5
    
    if tool_call_count >= MAX_TOOL_CALLS:
        print(f"[DEBUG] budget_analyst 工具调用达上限（{tool_call_count}/{MAX_TOOL_CALLS}），强制进入 budget_check")
        return "budget_check"
    
    if messages:
        last_message = messages[-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            print(f"[DEBUG] budget_analyst 需要调用工具（已完成 {tool_call_count}/{MAX_TOOL_CALLS} 次）")
            return "tool_node"
    
    print(f"[DEBUG] budget_analyst 完成核算，流转到 budget_check")
    return "budget_check"


def should_adjust(state: TravelState) -> str:
    """条件边函数：决定是否需要调整行程"""
    budget_analysis = state.get("budget_analysis")
    if budget_analysis and budget_analysis.is_over_budget and state["iteration_count"] < 3:
        print(f"[DEBUG] 条件边：需要调整，返回 planner (迭代次数: {state['iteration_count']})")
        return "planner"
    print(f"[DEBUG] 条件边：不需要调整或达到最大迭代次数，结束流程")
    return END


async def build_travel_graph(demand: TravelDemand) -> dict:
    """构建并执行LangGraph旅行规划流程（异步版本）"""
    # 在构建图之前初始化所有工具
    await init_tools()
    
    initial_state: TravelState = {
        "destination": demand.destination,
        "days": demand.days,
        "budget": demand.budget,
        "interests": demand.interests,
        "messages": [],
        "research_result": None,
        "budget_allocation": None,
        "itinerary": None,
        "budget_analysis": None,
        "iteration_count": 0,
        "tool_call_count": 0,
        "needs_adjustment": False,
        "error": None,
        "status": "researching",
        "simple_city_poi": None,
        "selected_scenic_detail": None,
        "raw_route": None,
        "route_related_price": None,
        "weather": None
    }

    workflow = StateGraph(TravelState)

    # 动态获取工具节点（必须在 init_tools 之后）
    current_tool_node = get_tool_node()

    workflow.add_node("researcher", researcher_node)
    workflow.add_node("tool_node", current_tool_node)
    workflow.add_node("budget_analyst", budget_analyst_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("budget_check", budget_check_node)

    workflow.set_entry_point("researcher")

    # researcher 的工具调用循环
    workflow.add_conditional_edges(
        "researcher",
        should_call_tool_researcher,
        {
            "tool_node": "tool_node",
            "planner": "planner"
        }
    )

    # planner 的工具调用循环
    workflow.add_conditional_edges(
        "planner",
        should_call_tool_planner,
        {
            "tool_node": "tool_node",
            "budget_analyst": "budget_analyst"
        }
    )

    def after_tool(state: TravelState) -> str:
        """工具执行后，根据 status 决定回到哪个节点"""
        status = state.get("status", "")
        if status == "planning_tool":
            return "planner"
        if status == "budgeting_tool":
            return "budget_analyst"
        return "researcher"
    
    workflow.add_conditional_edges(
        "tool_node",
        after_tool,
        {
            "researcher": "researcher",
            "planner": "planner",
            "budget_analyst": "budget_analyst"
        }
    )

    # budget_analyst 的工具调用循环
    workflow.add_conditional_edges(
        "budget_analyst",
        should_call_tool_budget,
        {
            "tool_node": "tool_node",
            "budget_check": "budget_check"
        }
    )

    workflow.add_conditional_edges(
        "budget_check",
        should_adjust,
        {
            "planner": "planner",
            END: END
        }
    )

    app = workflow.compile()

    print("🔍 开始调研目的地信息...")
    final_state = await app.ainvoke(initial_state)

    result = {
        "destination": final_state['destination'],
        "days": final_state['days'],
        "budget": final_state['budget'],
        "interests": final_state['interests'],
        "research_result": final_state['research_result'].model_dump() if final_state['research_result'] else None,
        "budget_allocation": final_state['budget_allocation'].model_dump() if final_state['budget_allocation'] else None,
        "itinerary": final_state['itinerary'].model_dump() if final_state['itinerary'] else None,
        "budget_analysis": final_state['budget_analysis'].model_dump() if final_state['budget_analysis'] else None,
        "iteration_count": final_state['iteration_count'],
        "error": final_state['error'],
        "status": final_state['status']
    }

    return result