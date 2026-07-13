"""
目的地调研节点 - 两阶段数据采集

设计原则：
1. 第一次调用 maps_text_search 获取精简字段（SimplePOI）
2. 第二次调用 maps_search_detail 获取深度信息（ScenicDetail）
3. 直接调用高德 MCP 工具，不经过 LLM
4. 工具调用结果由代码层直接解析
"""
import json
from models.models import TravelState, simple_poi_list_parser, scenic_detail_list_parser
from agent.tool_node import get_tools
from utils.utils import retry_on_rate_limit


def _parse_gaode_poi_result(content) -> list:
    """解析高德 MCP maps_text_search 返回的 POI 数据

    Args:
        content: 工具返回内容（字符串、字典或列表）

    Returns:
        List[SimplePOI]: 解析后的景点列表，解析失败返回空列表
    """
    try:
        # 处理高德 MCP 返回的嵌套格式：[{'type': 'text', 'text': '{"suggestion":...,"pois":[...]}'}]
        if isinstance(content, list) and len(content) > 0:
            first_item = content[0]
            if isinstance(first_item, dict) and 'text' in first_item:
                # 提取 text 字段中的 JSON 字符串
                content = first_item['text']

        data = json.loads(content) if isinstance(content, str) else content

        # 处理不同格式的返回数据
        if isinstance(data, list):
            pois_data = data
        elif isinstance(data, dict):
            pois_data = data.get("pois", [])
        else:
            print(f"[WARN] 未知的数据格式: {type(data)}")
            return []

        # 使用 parse 方法而不是 parse_list
        return simple_poi_list_parser.parse(json.dumps(pois_data))
    except Exception as e:
        print(f"[WARN] 解析工具返回结果失败: {e}")
        print(f"[DEBUG] 原始内容类型: {type(content)}, 内容: {str(content)}")
        return []


def _parse_gaode_detail_result(content) -> list:
    """解析高德 MCP maps_search_detail 返回的景点详情

    Args:
        content: 工具返回内容（字符串、字典或列表）

    Returns:
        List[ScenicDetail]: 解析后的景点详情列表，解析失败返回空列表
    """
    try:
        # 处理高德 MCP 返回的嵌套格式
        if isinstance(content, list) and len(content) > 0:
            first_item = content[0]
            if isinstance(first_item, dict) and 'text' in first_item:
                content = first_item['text']

        data = json.loads(content) if isinstance(content, str) else content

        # detail_search 返回单个景点详情对象，直接包装为列表
        if isinstance(data, list):
            detail_data = data
        elif isinstance(data, dict):
            # 单个景点详情对象，直接包装为列表
            detail_data = [data]
        else:
            print(f"[WARN] 未知的数据格式: {type(data)}")
            return []

        return scenic_detail_list_parser.parse(json.dumps(detail_data))
    except Exception as e:
        print(f"[WARN] 解析景点详情失败: {e}")
        print(f"[DEBUG] 原始内容类型: {type(content)}, 内容: {str(content)}")
        return []


def _find_poi_search_tool(tools: list):
    """从工具列表中查找 maps_text_search 工具"""
    for tool in tools:
        if getattr(tool, 'name', '') == 'maps_text_search':
            return tool
    return None


def _find_detail_search_tool(tools: list):
    """从工具列表中查找 maps_search_detail 工具"""
    for tool in tools:
        if getattr(tool, 'name', '') == 'maps_search_detail':
            return tool
    return None


@retry_on_rate_limit(max_retries=3, delay=2)
async def researcher_node(state: TravelState) -> TravelState:
    """目的地调研节点 - 两阶段数据采集

    采集策略：
    1. 数据自检：若 simple_city_poi 和 selected_scenic_detail 已存在则直接流转
    2. 第一次调用 maps_text_search 获取景点列表（SimplePOI）
    3. 第二次调用 maps_search_detail 获取景点详情（ScenicDetail）
    """
    print(f"[DEBUG] 执行 researcher_node，目的地: {state['destination']}")

    # 数据自检：已存在则跳过
    if state.get("simple_city_poi") and state.get("selected_scenic_detail"):
        print(f"[DEBUG] 数据已存在，跳过采集")
        state["status"] = "planner"
        return state

    # 获取高德 MCP 工具
    tools = get_tools()
    search_tool = _find_poi_search_tool(tools)
    detail_tool = _find_detail_search_tool(tools)

    if not search_tool:
        print(f"[ERROR] 未找到 maps_text_search 工具")
        state["error"] = "未找到 maps_text_search 工具"
        state["status"] = "failed"
        return state

    # 阶段1：调用 maps_text_search 获取景点列表
    if not state.get("simple_city_poi"):
        try:
            print(f"[DEBUG] 阶段1：调用 maps_text_search 搜索: {state['interests']}")
            result = await search_tool.ainvoke({
                "keywords": f"{state['interests']}",
                "city": state["destination"]
            })

            simple_pois = _parse_gaode_poi_result(result)

            if simple_pois:
                state["simple_city_poi"] = simple_pois
                print(f"[DEBUG] 阶段1完成：采集 {len(simple_pois)} 个景点骨架")
            else:
                print(f"[WARN] 阶段1失败：未采集到景点数据")
                state["error"] = "景点数据采集失败"
                state["status"] = "failed"
                return state
        except Exception as e:
            print(f"[ERROR] 阶段1工具调用失败: {e}")
            state["error"] = f"工具调用失败: {e}"
            state["status"] = "failed"
            return state

    # 阶段2：调用 maps_search_detail 获取景点详情
    if not state.get("selected_scenic_detail") and detail_tool:
        try:
            simple_pois = state.get("simple_city_poi", [])
            # 限制查询数量，避免过多 API 调用
            max_query = min(len(simple_pois), 20)
            selected_pois = simple_pois[:max_query]

            print(f"[DEBUG] 阶段2：调用 maps_search_detail 查询 {len(selected_pois)} 个景点详情")
            print(f"[DEBUG] detail_tool 名称: {getattr(detail_tool, 'name', 'unknown')}")

            all_details = []
            for idx, poi in enumerate(selected_pois):
                try:
                    print(f"[DEBUG] 查询景点 {idx+1}/{len(selected_pois)}: {poi.name} (ID: {poi.poi_id})")
                    result = await detail_tool.ainvoke({
                        "id": poi.poi_id
                    })
                    print(f"[DEBUG] 景点 {poi.name} 原始返回: {str(result)[:200]}")
                    details = _parse_gaode_detail_result(result)
                    print(f"[DEBUG] 景点 {poi.name} 解析结果数量: {len(details)}")
                    all_details.extend(details)
                except Exception as e:
                    print(f"[WARN] 查询景点 {poi.name} 详情失败: {e}")
                    import traceback
                    traceback.print_exc()
                    continue

            if all_details:
                state["selected_scenic_detail"] = all_details
                print(f"[DEBUG] 阶段2完成：采集 {len(all_details)} 个景点详情")
            else:
                print(f"[WARN] 阶段2失败：未采集到景点详情")
                # 不失败，继续使用骨架数据
                state["selected_scenic_detail"] = []
        except Exception as e:
            print(f"[ERROR] 阶段2工具调用失败: {e}")
            # 不失败，继续使用骨架数据
            state["selected_scenic_detail"] = []

    state["status"] = "planner"
    print(f"[DEBUG] researcher_node 完成，下一步状态: {state['status']}")
    return state