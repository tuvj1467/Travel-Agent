"""
偏好收集节点 - 渐进式需求收集

设计原则：
1. 检查必要字段（destination, days, budget, interests）是否齐全
2. 缺失字段时生成提问并通过 interrupt 暂停等待用户输入
3. 信息齐全后直接流转到下一个节点
"""
from models.models import TravelState, UserPreferences
from models.status import FlowStatus
from utils.utils import retry_on_rate_limit


@retry_on_rate_limit(max_retries=3, delay=2)
async def collect_preferences_node(state: TravelState) -> TravelState:
    """偏好收集节点 - 检查并收集用户旅行偏好

    Args:
        state: 当前工作流状态

    Returns:
        更新后的 TravelState，包含 preferences 或 interrupt 请求
    """
    print(f"[DEBUG] 执行 collect_preferences_node")

    # 检查是否已有完整的 preferences
    existing_prefs = state.get("preferences")

    # 从旧版字段构建 preferences
    destination = state.get("destination", "")
    days = state.get("days", 0)
    budget = state.get("budget", 0.0)
    interests = state.get("interests", "")

    # 判断各字段是否缺失
    missing_fields = []
    if not destination:
        missing_fields.append("destination（目的地）")
    if not days or days <= 0:
        missing_fields.append("days（天数）")
    if not budget or budget <= 0:
        missing_fields.append("budget（预算）")
    if not interests:
        missing_fields.append("interests（兴趣偏好）")

    if missing_fields:
        print(f"[DEBUG] 缺少必要字段: {', '.join(missing_fields)}")
        # 如果所有字段都缺失，并且有用户原始查询，尝试从 CLI 参数构建
        if destination and days > 0 and budget > 0 and not interests:
            # 兼容：interests 可能有默认值
            pass
        else:
            # 在中断场景下，生成提示信息
            missing_list = "、".join([f.split("（")[0] for f in missing_fields])
            prompt = f"请提供以下缺失信息：{missing_list}"
            print(f"[PROMPT] {prompt}")
            state["status"] = FlowStatus.COLLECTING.value
            state["error"] = prompt
            return state

    # 构建 UserPreferences
    preferences = UserPreferences(
        destination=destination,
        days=days,
        budget=budget,
        interests=interests
    )
    state["preferences"] = preferences
    state["status"] = FlowStatus.SEARCHING_POIS.value
    print(f"[DEBUG] 偏好收集完成，目的地: {destination}, 天数: {days}, 预算: {budget}")
    return state
