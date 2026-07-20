"""
酒店搜索节点 - 搜索目的地酒店信息

注意：当前为占位节点，仅做数据透传，不搜索真实酒店。
后续可集成携程、美团等酒店搜索 API。
"""
from models.models import TravelState
from models.status import FlowStatus
from utils.utils import retry_on_rate_limit


@retry_on_rate_limit(max_retries=3, delay=2)
async def search_hotels_node(state: TravelState) -> TravelState:
    """酒店搜索节点 - 占位实现

    当前版本直接跳过酒店搜索，后续版本可集成真实 API。

    Args:
        state: 当前工作流状态

    Returns:
        更新后的 TravelState，hotels 保持空列表
    """
    print(f"[DEBUG] 执行 search_hotels_node（占位）")

    # 占位：不执行实际搜索，hotels 保持为空
    if not state.get("hotels"):
        state["hotels"] = []

    state["status"] = FlowStatus.GENERATING.value
    print(f"[DEBUG] search_hotels_node 完成（跳过）")
    return state
