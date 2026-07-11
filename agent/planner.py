"""
行程规划节点 - 两段式规划

设计原则：
1. 阶段1（粗框架）：仅靠坐标和片区标签搭行程骨架，不查详情
2. 阶段2（精细填充）：只查路线选中景点的详情，不加载全城数据
3. 支持工具调用循环，采集路线沿途缺失数据
"""
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage, ToolMessage

from models.models import TravelState
from models.models import itinerary_parser
from config.config import llm
from agent.tool_node import get_tools
from utils.utils import retry_on_rate_limit


@retry_on_rate_limit(max_retries=3, delay=2)
async def planner_node(state: TravelState) -> TravelState:
    """行程规划节点 - 两段式规划

    阶段1：基于 simple_city_poi 的坐标和片区信息搭粗框架
    阶段2：查选中景点的详情，精细填充行程
    """
    print(f"[DEBUG] 执行 planner_node，迭代次数: {state['iteration_count']}")

    tools = get_tools()
    llm_with_tools = llm.bind_tools(tools)

    simple_city_poi = state.get("simple_city_poi")
    selected_detail = state.get("selected_scenic_detail")
    raw_route = state.get("raw_route")
    history_messages = state.get("messages", [])

    # 判断当前阶段
    simple_city_poi = state.get("simple_city_poi")

    if not simple_city_poi:
        print(f"[WARN] 缺少景点数据，跳过规划")
        state["status"] = "checking"
        return state

    if not history_messages:
        # 阶段1：首次进入，搭粗框架 + 请求详情
        poi_text = str(simple_city_poi)[:3000]

        system_prompt = """你是一名旅行路线规划师，专精地理空间排布。

【当前阶段】粗路线骨架搭建 + 请求景点详情。

【可用景点骨架数据】（仅含名称、坐标、片区、分类）：
{poi_data}

【规划步骤】：
1. 地理聚类：按片区（district）拆分景点，同片区安排在同一天
2. 偏好筛选：根据用户偏好「{interests}」过滤，{days}天选{max_pois}个左右景点
3. 天数分配：避免远距离往返
4. 片区内排序：按坐标就近排列


{format_instructions}"""

        system_msg = SystemMessage(content=system_prompt.format(
            poi_data=poi_text,
            interests=state["interests"],
            days=state["days"],
            max_pois=state["days"] * 3,
            format_instructions=itinerary_parser.get_format_instructions()
        ))
        human_msg = HumanMessage(
            content=f"请为{state['destination']}搭建{state['days']}天行程骨架，"
                    f"然后调用 maps_search_detail 获取选中景点的详情"
        )
        messages_to_send = [system_msg, human_msg]
    else:
        # 阶段2：工具结果已返回，基于详情生成完整行程
        messages_to_send = list(history_messages)

    response = await llm_with_tools.ainvoke(messages_to_send)

    if not history_messages:
        state["messages"] = messages_to_send + [response]
    else:
        state["messages"] = [response]

    if isinstance(response, AIMessage) and response.tool_calls:
        tool_names = [tc['name'] for tc in response.tool_calls]
        print(f"[DEBUG] planner 请求工具调用: {tool_names}")
        state["status"] = "planning_tool"
    else:
        print(f"[DEBUG] planner 返回规划结果")
        try:
            itinerary = itinerary_parser.parse(response.content)
            state["itinerary"] = itinerary
            state["status"] = "checking"
            state["messages"] = []  # 清空，为后续节点腾空间
        except Exception as e:
            print(f"[WARN] 解析行程规划失败: {e}")
            state["error"] = f"行程解析失败: {e}"
            state["itinerary"] = None
            state["status"] = "checking"
            state["messages"] = []

    print(f"[DEBUG] planner_node 完成，状态: {state['status']}")
    return state
