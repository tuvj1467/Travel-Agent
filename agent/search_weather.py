"""
天气查询节点 - 获取目的地天气信息

设计原则：
1. 调用高德 MCP maps_weather 工具获取天气数据
2. 查询失败时降级处理，不影响主流程
"""
from models.models import TravelState
from models.status import FlowStatus
from agent.tool_node import get_tools
from utils.utils import retry_on_rate_limit


def _find_weather_tool(tools: list):
    """从工具列表中查找 maps_weather 工具"""
    for tool in tools:
        if getattr(tool, 'name', '') == 'maps_weather':
            return tool
    return None


@retry_on_rate_limit(max_retries=3, delay=2)
async def search_weather_node(state: TravelState) -> TravelState:
    """天气查询节点 - 获取目的地天气数据

    Args:
        state: 当前工作流状态

    Returns:
        更新后的 TravelState，包含 weather 字段
    """
    print(f"[DEBUG] 执行 search_weather_node，目的地: {state.get('destination', '')}")

    # 数据自检：已存在则跳过
    if state.get("weather"):
        print(f"[DEBUG] 天气数据已存在，跳过查询")
        state["status"] = FlowStatus.SEARCHING_FLIGHTS.value
        return state

    tools = get_tools()
    weather_tool = _find_weather_tool(tools)

    if not weather_tool:
        print(f"[WARN] 未找到 maps_weather 工具，跳过天气查询")
        state["status"] = FlowStatus.SEARCHING_FLIGHTS.value
        return state

    try:
        destination = state.get("destination", "")
        print(f"[DEBUG] 调用 maps_weather 查询: {destination}")
        result = await weather_tool.ainvoke({
            "city": destination
        })
        print(f"[DEBUG] maps_weather 返回: {str(result)[:200]}")

        # 解析天气结果
        import json
        if isinstance(result, list) and len(result) > 0:
            first_item = result[0]
            if isinstance(first_item, dict) and 'text' in first_item:
                weather_data = json.loads(first_item['text'])
                if isinstance(weather_data, dict):
                    state["weather"] = weather_data
                    print(f"[DEBUG] 天气查询成功")
                else:
                    print(f"[WARN] 天气数据格式异常")
            else:
                state["weather"] = first_item
        elif isinstance(result, str):
            state["weather"] = json.loads(result)
        else:
            state["weather"] = result

    except Exception as e:
        print(f"[WARN] 天气查询失败: {e}，继续流程")
        # 降级处理：不阻塞主流程

    state["status"] = FlowStatus.SEARCHING_FLIGHTS.value
    print(f"[DEBUG] search_weather_node 完成")
    return state
