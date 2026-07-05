"""
LangGraph 图构建模块
"""
from langgraph.graph import StateGraph, END

from models import TravelState, TravelDemand
from graph_nodes import researcher_node, budget_analyst_node, planner_node, budget_check_node


def should_adjust(state: TravelState) -> str:
    """条件边函数：决定是否需要调整行程"""
    # 如果超支且迭代次数小于3次，返回planner重新规划
    if state["needs_adjustment"] and state["iteration_count"] < 3:
        print(f"[DEBUG] 条件边：需要调整，返回planner (迭代次数: {state['iteration_count']})")
        return "planner"
    # 否则结束
    print(f"[DEBUG] 条件边：不需要调整或达到最大迭代次数，结束流程")
    return END


def build_travel_graph(demand: TravelDemand) -> str:
    """构建并执行LangGraph旅行规划流程"""
    # 初始化状态
    initial_state: TravelState = {
        "destination": demand.destination,
        "days": demand.days,
        "budget": demand.budget,
        "interests": demand.interests,
        "research_result": "",
        "budget_allocation": "",
        "itinerary": "",
        "budget_analysis": "",
        "iteration_count": 0,
        "needs_adjustment": False
    }
    
    # 构建图
    workflow = StateGraph(TravelState)
    
    # 添加节点
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("budget_analyst", budget_analyst_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("budget_check", budget_check_node)
    
    # 设置入口点
    workflow.set_entry_point("researcher")
    
    # 添加边
    workflow.add_edge("researcher", "budget_analyst")
    workflow.add_edge("budget_analyst", "planner")
    workflow.add_edge("planner", "budget_check")
    
    # 添加条件边：如果超支则回到planner，否则结束
    workflow.add_conditional_edges(
        "budget_check",
        should_adjust,
        {
            "planner": "planner",
            END: END
        }
    )
    
    # 编译图
    app = workflow.compile()
    
    # 执行流程
    print("🔍 开始调研目的地信息...")
    final_state = app.invoke(initial_state)
    
    # 格式化输出
    result = f"""
    {'='*60}
    📋 旅行规划报告
    {'='*60}
    
    📍 目的地：{final_state['destination']}
    📅 天数：{final_state['days']}天
    💰 预算：{final_state['budget']}元
    🎯 兴趣：{final_state['interests']}
    
    {'='*60}
    🔍 目的地调研
    {'='*60}
    {final_state['research_result']}
    
    {'='*60}
    💵 预算分配方案
    {'='*60}
    {final_state['budget_allocation']}
    
    {'='*60}
    🗓️ 详细行程规划
    {'='*60}
    {final_state['itinerary']}
    
    {'='*60}
    📊 预算分析
    {'='*60}
    {final_state['budget_analysis']}
    
    {'='*60}
    迭代次数：{final_state['iteration_count']}
    {'='*60}
    """
    
    return result
