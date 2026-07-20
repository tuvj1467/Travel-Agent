"""
最终确认节点 - 确认并输出最终行程结果

设计原则：
1. 汇总行程方案和费用明细
2. 生成最终输出格式
3. 标记流程状态为 finalized
"""
from models.models import TravelState
from models.status import FlowStatus
from utils.utils import retry_on_rate_limit


@retry_on_rate_limit(max_retries=3, delay=2)
async def finalize_node(state: TravelState) -> TravelState:
    """最终确认节点 - 汇总并输出最终结果

    Args:
        state: 当前工作流状态

    Returns:
        更新后的 TravelState，包含 final_result
    """
    print(f"[DEBUG] 执行 finalize_node")

    itinerary = state.get("itinerary")
    budget_allocation = state.get("budget_allocation")

    # 构建最终结果
    final_result = {
        "destination": state.get("destination", ""),
        "days": state.get("days", 0),
        "budget": state.get("budget", 0.0),
        "status": "confirmed",
        "itinerary": itinerary.model_dump() if itinerary else None,
        "budget_allocation": budget_allocation.model_dump() if budget_allocation else None,
    }

    state["final_result"] = final_result
    state["status"] = FlowStatus.FINALIZED.value

    print(f"[DEBUG] 行程已确认")
    print(f"  - 目的地: {final_result['destination']}")
    print(f"  - 天数: {final_result['days']}天")
    print(f"  - 预算: ¥{final_result['budget']:.0f}")

    return state
