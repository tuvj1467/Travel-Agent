"""
航班搜索节点 - 通过聚合数据 MCP 搜索航班信息

设计原则：
1. 调用聚合数据 MCP get_flight_info 工具
2. 使用 FlightResponse / FlightInfo 模型解析返回数据
3. 无出发城市时跳过（可选节点）
4. 查询失败时降级处理，不阻塞主流程
"""
import json
from models.models import TravelState, FlightResponse, FlightInfo
from models.status import FlowStatus
from agent.tool_node import get_tools
from utils.utils import retry_on_rate_limit

# 默认出发城市
DEFAULT_DEPARTURE = "北京"


def _find_flight_tool(tools: list):
    """从工具列表中查找聚合数据航班搜索工具"""
    for tool in tools:
        if 'flight' in str(getattr(tool, 'name', '')).lower():
            return tool
    return None


def _parse_flight_result(result) -> list:
    """使用 Pydantic 模型解析 get_flight_info 的 MCP 返回结果

    MCP 返回格式: [{"type": "text", "text": "{ \"reason\": \"成功\", \"result\": { ... } }"}]
    解析为 List[FlightInfo]
    """
    if not result:
        return []

    # MCP 工具返回的是 list[dict]，第一个元素的 text 字段含 JSON
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict) and 'text' in item:
                try:
                    data = json.loads(item['text'])
                    # 使用 FlightResponse 做结构化解析
                    flight_response = FlightResponse(**data)
                    if flight_response.reason == '成功' and flight_response.result:
                        return flight_response.result.flight_info
                except Exception as e:
                    print(f"[WARN] 航班结果解析失败: {e}")

    # 兜底：尝试直接作为 dict 列表解析
    if isinstance(result, list):
        try:
            items = []
            for item in result:
                if isinstance(item, dict):
                    items.append(FlightInfo(**item))
            return items
        except Exception:
            pass

    return []


@retry_on_rate_limit(max_retries=3, delay=2)
async def search_flights_node(state: TravelState) -> TravelState:
    """航班搜索节点 - 搜索前往目的地的航班信息

    Args:
        state: 当前工作流状态

    Returns:
        更新后的 TravelState，包含 List[FlightInfo] 的 flights 字段
    """
    print(f"[DEBUG] 执行 search_flights_node")

    # 数据自检：已存在则跳过
    if state.get("flights"):
        print(f"[DEBUG] 航班数据已存在（{len(state['flights'])} 条），跳过查询")
        state["status"] = FlowStatus.SEARCHING_HOTELS.value
        return state

    tools = get_tools()
    flight_tool = _find_flight_tool(tools)

    if not flight_tool:
        print(f"[WARN] 未找到航班搜索工具，跳过")
        state["flights"] = []
        state["status"] = FlowStatus.SEARCHING_HOTELS.value
        return state

    destination = state.get("destination", "")
    if not destination:
        print(f"[WARN] 未指定目的地，跳过航班搜索")
        state["flights"] = []
        state["status"] = FlowStatus.SEARCHING_HOTELS.value
        return state

    try:
        print(f"[DEBUG] 调用 get_flight_info: {DEFAULT_DEPARTURE} → {destination}")
        result = await flight_tool.ainvoke({
            "departure": DEFAULT_DEPARTURE,
            "arrival": destination,
            "departureDate": "2026-07-25"  # 占位日期，后续可从用户输入获取  
            #todo
        })

        flight_list = _parse_flight_result(result)
        state["flights"] = flight_list
        # 标记是否有航班可用，供 generate_itinerary 判断是否切换为高铁
        state["has_airport"] = len(flight_list) > 0
        print(f"[DEBUG] 航班搜索成功: 获取 {len(flight_list)} 条航班信息")

        # 打印简要信息
        for f in flight_list[:10]:
            print(f"  - {f.flight_no}: {f.airline_name} "
                  f"{f.departure_time} → {f.arrival_time}, "
                  f"¥{f.ticket_price}, {f.duration}")

    except Exception as e:
        print(f"[WARN] 航班搜索失败: {e}，继续流程")
        state["flights"] = []
        # 降级处理：不阻塞主流程

    state["status"] = FlowStatus.SEARCHING_HOTELS.value
    print(f"[DEBUG] search_flights_node 完成")
    return state
