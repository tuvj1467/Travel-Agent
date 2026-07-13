"""
景区路线规划节点 - 基于 selected_scenic_detail 生成景区游览路线

设计原则：
1. 基于 selected_scenic_detail 直接生成景区游览路线
2. 只规划景区景点，不涉及住宿、餐饮、交通
3. LLM 可以根据需要调用工具获取额外信息
4. 后续会有专门的 agent 处理住宿、餐饮、交通
"""
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

from models.models import TravelState
from models.models import itinerary_parser
from config.config import llm
from agent.tool_node import get_tools
from utils.utils import retry_on_rate_limit


@retry_on_rate_limit(max_retries=3, delay=2)
async def planner_node(state: TravelState) -> TravelState:
    """景区路线规划节点 - 基于 selected_scenic_detail 生成景区游览路线

    LLM 根据景点详情生成景区游览路线，如需要更多信息可调用工具
    注意：只规划景区景点，不涉及住宿、餐饮、交通
    """
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

    detail_text = str(selected_detail)

    if not history_messages:
        # 首次进入：生成景区游览路线
        system_prompt = """你是一名景区路线规划师。

        【可用景点详情】：
        {detail_data}

        【规划原则】：
        1. 地理聚类：按片区（district）拆分景点，同片区安排在同一天
        2. 偏好筛选：优先用户偏好「{interests}」，优先评分较高的景区
        3. 合理安排：每天最多安排 2-3 个景点，避免行程过密
        4. 时间分配：每个景点游览时长 2-3 小时，上午 1 个，下午 1-2 个
        5. 避免重复：不要安排名称相似或地理位置重叠的景点（如"凤凰山"和"凤凰山公园"选其一）
        6. 片区内排序：按坐标就近排列，减少路途时间

        【费用估算】：
        只估算景区门票费用，使用景点详情中的 ticket_price 字段。
        如 ticket_price 为 0 或空，根据景点类型估算（自然风光通常免费，人文景点可能有门票）。

        【注意】：
        只规划景区游览路线，不涉及住宿、餐饮、交通安排。
        住宿、餐饮、交通将由专门的 agent 后续处理。

        【工具使用】：
        如果需要查询更多信息（如天气、交通路线等），可以调用相应工具。

        【输出要求】：
        生成景区游览路线规划，包含每天的景区活动安排、时间段、时长和门票费用。

        {format_instructions}"""

        system_msg = SystemMessage(content=system_prompt.format(
            detail_data=detail_text,
            interests=state["interests"],
            days=state["days"],
            destination=state["destination"],
            format_instructions=itinerary_parser.get_format_instructions()
        ))
        human_msg = HumanMessage(
            content=f"请为{state['destination']}生成{state['days']}天的景区游览路线规划"
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
