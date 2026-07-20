"""
行程优化节点 - 根据用户反馈优化行程

设计原则：
1. 结合用户反馈和原行程重新生成
2. 将反馈作为额外约束交给 LLM
3. 更新 itinerary 后回到 generate_itinerary 重新生成
"""
from models.models import TravelState, itinerary_parser
from models.status import FlowStatus
from config.config import llm
from utils.utils import retry_on_rate_limit
from langchain_core.messages import SystemMessage, HumanMessage


@retry_on_rate_limit(max_retries=3, delay=2)
async def refine_itinerary_node(state: TravelState) -> TravelState:
    """行程优化节点 - 基于用户反馈重新生成行程

    Args:
        state: 当前工作流状态

    Returns:
        更新后的 TravelState，包含优化后的 itinerary
    """
    print(f"[DEBUG] 执行 refine_itinerary_node")

    feedback = state.get("feedback", "")
    if not feedback:
        print(f"[WARN] 用户反馈为空，直接跳过优化")
        state["status"] = FlowStatus.GENERATING.value
        return state

    print(f"[DEBUG] 用户反馈: {feedback}")

    # 获取原行程和景点详情
    itienrary = state.get("itinerary")
    selected_detail = state.get("selected_scenic_detail", [])

    if not itienrary:
        print(f"[WARN] 原行程不存在，无法优化")
        state["status"] = FlowStatus.GENERATING.value
        return state

    # 构建优化提示
    detail_text = ""
    if selected_detail:
        for detail in selected_detail[:10]:
            detail_text += (
                f"- {detail.name}: 门票¥{detail.ticket_price}, "
                f"营业时间{detail.opening_hours}, 标签{detail.tags}\n"
            )

    system_msg = SystemMessage(content=f"""你是旅行行程优化专家。用户对已生成的行程不满意，请根据反馈优化行程。

原始行程:
{itienrary.model_dump_json(indent=2)}

可用景点信息:
{detail_text}

用户反馈: {feedback}

请根据反馈优化行程，输出格式必须是合法的 JSON，包含 destination、days、day_plans 字段。
每个 day_plan 包含 day、activities、estimated_cost。
每个 activity 包含 name、time_slot（morning/afternoon/evening）、duration_hours、cost。

注意：
- 每天2-3个景点，每个景点2-3小时
- 同一天景点应在同一地理片区
- 考虑景点开放时间""")

    human_msg = HumanMessage(content="请根据反馈优化行程")

    try:
        response = await llm.ainvoke([system_msg, human_msg])
        parsed = itinerary_parser.parse(response.content)
        state["itinerary"] = parsed
        state["status"] = FlowStatus.GENERATING.value
        print(f"[DEBUG] 行程优化成功, 共 {len(parsed.day_plans)} 天")
    except Exception as e:
        print(f"[WARN] 行程优化失败: {e}")
        state["status"] = FlowStatus.GENERATING.value
        # 保留原行程不变

    return state
