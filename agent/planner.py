"""
景区路线规划节点 - 基于 selected_scenic_detail 生成景区游览路线

设计原则：
1. 基于 selected_scenic_detail 生成景区游览路线
2. 整合航班、天气信息，生成完整行程
3. LLM 可以根据需要调用工具获取额外信息
4. 输出结构化 Itinerary，包含每日活动、费用和航班信息
"""
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

from models.models import TravelState, FlightInfo
from models.models import itinerary_parser
from config.config import llm
from agent.tool_node import get_tools
from utils.utils import retry_on_rate_limit


@retry_on_rate_limit(max_retries=3, delay=2)
async def planner_node(state: TravelState) -> TravelState:
    """景区路线规划节点 - 整合景点、航班、天气生成完整行程"""
    print(f"[DEBUG] 执行 planner_node，迭代次数: {state['iteration_count']}")

    selected_detail = state.get("selected_scenic_detail")
    history_messages = state.get("messages", [])

    # 数据自检
    if not selected_detail:
        print(f"[WARN] 缺少景点详情数据，返回 researcher_node")
        state["status"] = "researcher"
        return state

    # 准备工具
    tools = get_tools()
    llm_with_tools = llm.bind_tools(tools)

    # 序列化景点详情
    detail_items = []
    for sd in selected_detail:
        detail_items.append(sd.model_dump_json())
    detail_text = "\n".join(detail_items)

    # 序列化航班信息
    flights = state.get("flights", [])
    has_airport = state.get("has_airport", False)
    flight_text = ""
    if flights and len(flights) > 0:
        flight_lines = []
        for f in flights[:5]:  # 只取前5条，避免 token 超限
            flight_lines.append(
                f"- {f.flight_no}: {f.airline_name} "
                f"{f.departure_time}→{f.arrival_time}, "
                f"¥{f.ticket_price}, {f.duration}"
            )
        flight_text = "\n".join(flight_lines)
    else:
        flight_text = "（无双直飞航班，将采用高铁/自驾方式）"

    # 天气信息
    weather = state.get("weather")
    weather_text = "（未查询）"
    if weather:
        weather_text = str(weather)

    if not history_messages:
        # 首次进入：生成完整行程
        system_prompt = """你是一名旅行行程规划师。

【目的地】：{destination}
【天数】：{days}天
【兴趣偏好】：{interests}
【预算】：{budget}元

【可用景点详情】：
{detail_data}

【航班信息】：
{flight_data}

【天气情况】：
{weather_data}

【规划原则】：
1. 地理聚类：按片区（district）拆分景点，同片区安排在同一天
2. 偏好筛选：优先用户偏好「{interests}」，优先评分较高的景区
3. 合理安排：每天最多安排 2-3 个景点，避免行程过密
4. 时间分配：每个景点游览时长 2-3 小时，上午 1 个，下午 1-2 个
5. 避免重复：不要安排名称相似或地理位置重叠的景点
6. 考虑天气：雨天优先安排室内景点，户外景点安排在天气好的时段

【费用估算】：
1. 门票费用：使用景点详情中的 ticket_price 字段
2. 航班费用：使用航班信息中的 ticket_price，没有航班则按高铁估算（约 ¥500-800）
3. 住宿费用：按经济型酒店 150-200 元/晚估算
4. 餐饮费用：按每天 100-150 元估算
5. 交通费用：景点间交通按每天 50-80 元估算

【注意】：
- 如果航班为直飞且有合理价格，将航班信息写入首日行程
- 如果无双直飞航班（flight_text 显示为"无双直飞航班"），则在费用中按高铁估算
- 每日活动的 estimated_cost 应该包含该日所有花费（门票+餐饮+交通+当日住宿分摊）

【输出要求】：
生成结构化的每日行程，包含活动安排、时间段、时长、各项费用。

{format_instructions}"""

        system_msg = SystemMessage(content=system_prompt.format(
            destination=state["destination"],
            days=state["days"],
            interests=state["interests"],
            budget=state["budget"],
            detail_data=detail_text,
            flight_data=flight_text,
            weather_data=weather_text,
            format_instructions=itinerary_parser.get_format_instructions()
        ))
        human_msg = HumanMessage(
            content=f"请为{state['destination']}生成{state['days']}天的完整旅行行程规划"
        )
        messages_to_send = [system_msg, human_msg]

        response = await llm_with_tools.ainvoke(messages_to_send)

        state["messages"] = messages_to_send + [response]
    else:
        # 工具结果已返回，继续处理
        messages_to_send = list(history_messages)
        response = await llm_with_tools.ainvoke(messages_to_send)
        state["messages"] = [response]

    # 检查是否需要工具调用
    if isinstance(response, AIMessage) and response.tool_calls:
        tool_names = [tc['name'] for tc in response.tool_calls]
        print(f"[DEBUG] planner 请求工具调用: {tool_names}")
        state["status"] = "planning_tool"
    else:
        # 解析行程
        try:
            itinerary = itinerary_parser.parse(response.content)
            state["itinerary"] = itinerary
            print(f"[DEBUG] 景区游览路线生成完成")
            state["status"] = "checking"
            state["messages"] = []
        except Exception as e:
            print(f"[WARN] 解析景区路线规划失败: {e}")
            state["error"] = f"景区路线解析失败: {e}"
            state["itinerary"] = None
            state["status"] = "checking"
            state["messages"] = []

    print(f"[DEBUG] planner_node 完成，状态: {state['status']}")
    return state
