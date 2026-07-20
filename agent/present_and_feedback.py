"""
呈现与反馈节点 - 呈现行程并获取用户反馈

设计原则：
1. 格式化输出行程方案和费用明细
2. 通过 interrupt 暂停等待用户反馈
3. 根据用户反馈（满意/修改/调整预算）路由到不同节点
"""
from models.models import TravelState
from models.status import FlowStatus
from utils.utils import retry_on_rate_limit


def _format_itinerary(state: TravelState) -> str:
    """格式化行程为可读文本"""
    itinerary = state.get("itinerary")
    budget_allocation = state.get("budget_allocation")
    flights = state.get("flights", [])
    weather = state.get("weather")

    lines = []
    lines.append("=" * 50)
    lines.append(f"  【旅行方案】{state.get('destination', '')}")
    lines.append("=" * 50)

    # 天气
    if weather:
        lines.append(f"\n🌤️ 天气: {weather}")

    # 航班信息
    if flights and len(flights) > 0:
        lines.append(f"\n✈️  推荐航班:")
        for f in flights[:3]:
            lines.append(f"  {f.flight_no} | {f.airline_name}")
            lines.append(f"  {f.departure_time} → {f.arrival_time} | {f.duration} | ¥{f.ticket_price}")
    elif state.get("has_airport") is False:
        lines.append(f"\n🚄 无双直飞航班，建议高铁出行")

    if itinerary:
        lines.append(f"\n目的地: {itinerary.destination}")
        lines.append(f"天数: {itinerary.days}天")
        lines.append(f"预估总费用: {itinerary.total_estimated_cost:.0f}元\n")

        for day_plan in itinerary.day_plans:
            lines.append(f"--- 第{day_plan.day}天 ---")
            for activity in day_plan.activities:
                time_label = {"morning": "上午", "afternoon": "下午", "evening": "晚上"}.get(
                    activity.time_slot, activity.time_slot
                )
                lines.append(f"  {time_label}: {activity.name} ({activity.duration_hours}h, ¥{activity.cost:.0f})")
            lines.append(f"  当日小计: ¥{day_plan.estimated_cost:.0f}")

    if budget_allocation:
        lines.append(f"\n--- 费用明细 ---")
        lines.append(f"总预算: ¥{budget_allocation.total_budget:.0f}")
        for item in budget_allocation.categories:
            lines.append(f"  {item.category}: {item.name} ¥{item.amount:.0f}")
        lines.append(f"剩余备用金: ¥{budget_allocation.remaining:.0f}")
        lines.append(f"预算评估: {budget_allocation.assessment}")

    lines.append("\n" + "=" * 50)
    lines.append("请反馈: 满意 / 修改 / 调整预算")
    lines.append("=" * 50)

    return "\n".join(lines)


@retry_on_rate_limit(max_retries=3, delay=2)
async def present_and_feedback_node(state: TravelState) -> TravelState:
    """呈现与反馈节点 - 展示行程并等待用户反馈

    当前版本使用 CLI 输出方式呈现，后续可扩展为 interrupt 模式。

    Args:
        state: 当前工作流状态

    Returns:
        更新后的 TravelState，包含 user_choice
    """
    print(f"[DEBUG] 执行 present_and_feedback_node")

    # 格式化行程
    output = _format_itinerary(state)
    print("\n" + output)

    # CLI 模式：直接接收用户输入
    try:
        user_input = input("\n请输入您的选择 (满意/修改/调整预算): ").strip()
    except (EOFError, KeyboardInterrupt):
        user_input = "满意"

    if "修改" in user_input:
        state["user_choice"] = "modify"
        state["feedback"] = user_input
        state["status"] = FlowStatus.REFINING.value
        print(f"[DEBUG] 用户选择: 修改行程")
    elif "预算" in user_input or "调整" in user_input:
        state["user_choice"] = "adjust_budget"
        state["feedback"] = user_input
        state["status"] = FlowStatus.COLLECTING.value
        print(f"[DEBUG] 用户选择: 调整预算")
    else:
        state["user_choice"] = "satisfied"
        state["feedback"] = user_input
        state["status"] = FlowStatus.FINALIZED.value
        print(f"[DEBUG] 用户选择: 满意，确认行程")

    return state
