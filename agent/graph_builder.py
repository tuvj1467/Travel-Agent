"""
LangGraph 图构建模块 - 适配结构化输出
"""
from langgraph.graph import StateGraph, END

from models.models import TravelState, TravelDemand
from agent.graph_nodes import researcher_node, budget_analyst_node, planner_node, budget_check_node


def should_adjust(state: TravelState) -> str:
    """条件边函数：决定是否需要调整行程"""
    budget_analysis = state.get("budget_analysis")
    if budget_analysis and budget_analysis.is_over_budget and state["iteration_count"] < 3:
        print(f"[DEBUG] 条件边：需要调整，返回planner (迭代次数: {state['iteration_count']})")
        return "planner"
    print(f"[DEBUG] 条件边：不需要调整或达到最大迭代次数，结束流程")
    return END


def build_travel_graph(demand: TravelDemand) -> dict:
    """构建并执行LangGraph旅行规划流程"""
    initial_state: TravelState = {
        "destination": demand.destination,
        "days": demand.days,
        "budget": demand.budget,
        "interests": demand.interests,
        "research_result": None,
        "budget_allocation": None,
        "itinerary": None,
        "budget_analysis": None,
        "iteration_count": 0,
        "needs_adjustment": False,
        "error": None,
        "status": "researching"
    }

    workflow = StateGraph(TravelState)

    workflow.add_node("researcher", researcher_node)
    workflow.add_node("budget_analyst", budget_analyst_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("budget_check", budget_check_node)

    workflow.set_entry_point("researcher")

    workflow.add_edge("researcher", "budget_analyst")
    workflow.add_edge("budget_analyst", "planner")
    workflow.add_edge("planner", "budget_check")

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
    final_state = app.invoke(initial_state)

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