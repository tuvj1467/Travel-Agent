"""
预算分析师节点 - 成本核算 + 价格查询

设计原则：
1. 代码层检查 route_related_price 是否存在
2. 缺失则引导 LLM 调用工具查询路线涉及片区的价格
3. 基于真实价格核算总花费
4. 超预算标记回退，由 graph_builder 路由回 planner
"""
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage, ToolMessage

from models.models import TravelState
from models.models import budget_allocation_parser
from config.config import llm
from agent.tool_node import get_tools
from utils.utils import retry_on_rate_limit


@retry_on_rate_limit(max_retries=3, delay=2)
async def budget_analyst_node(state: TravelState) -> TravelState:
    """预算分析师节点 - 基于行程做成本核算

    流程：
    1. 检查 route_related_price 是否存在
    2. 缺失则调用工具查询价格
    3. 有价格后核算总花费，输出预算分配
    """
    print(f"[DEBUG] 执行 budget_analyst_node，预算: {state['budget']}元")

    tools = get_tools()
    llm_with_tools = llm.bind_tools(tools)

    itinerary = state.get("itinerary")
    route_related_price = state.get("route_related_price")
    history_messages = state.get("messages", [])

    itinerary_text = itinerary.model_dump_json(indent=2) if itinerary else "无行程数据"

    has_price = route_related_price is not None
    print(f"[DEBUG] 价格数据自检: {'有' if has_price else '无'}")

    if not history_messages:
        # 首次进入：检查是否需要查价格
        if has_price:
            # 已有价格，直接核算
            price_text = str(route_related_price)[:2000]
            system_prompt = """你是一名旅行财务顾问。
根据已有价格数据，在{budget}元总预算范围内制定{days}天预算分配方案。

行程：{itinerary}
片区价格：{price_data}

正向计算：门票→住宿→餐饮→交通→备用金。
严禁负数、严禁编造。

{format_instructions}"""
            system_msg = SystemMessage(content=system_prompt.format(
                budget=state["budget"],
                days=state["days"],
                itinerary=itinerary_text[:2000],
                price_data=price_text,
                format_instructions=budget_allocation_parser.get_format_instructions()
            ))
            human_msg = HumanMessage(content="请基于已有价格数据制定预算分配方案")
            messages_to_send = [system_msg, human_msg]
        else:
            # 缺少价格，需要查询
            system_prompt = """你是一名旅行财务顾问。

【当前状态】缺少路线涉及片区的实时价格数据，需要先查询。

行程规划（提取其中涉及的片区和消费项）：
{itinerary}

【任务】：
1. 从行程中提取涉及的片区（如市区、湄洲岛等）
2. 调用 tavily_search 查询各片区的经济型酒店价格、餐饮人均消费
3. 查询完成后，基于真实价格制定预算分配方案

{format_instructions}"""
            system_msg = SystemMessage(content=system_prompt.format(
                itinerary=itinerary_text[:2000],
                format_instructions=budget_allocation_parser.get_format_instructions()
            ))
            human_msg = HumanMessage(
                content=f"请先查询{state['destination']}各片区的住宿餐饮价格，再制定预算方案"
            )
            messages_to_send = [system_msg, human_msg]
    else:
        # 工具结果已返回，基于结果核算
        messages_to_send = list(history_messages)

    response = await llm_with_tools.ainvoke(messages_to_send)

    if not history_messages:
        state["messages"] = messages_to_send + [response]
    else:
        state["messages"] = [response]

    if isinstance(response, AIMessage) and response.tool_calls:
        tool_names = [tc['name'] for tc in response.tool_calls]
        print(f"[DEBUG] budget_analyst 请求工具调用: {tool_names}")
        state["status"] = "budgeting_tool"
    else:
        print(f"[DEBUG] budget_analyst 返回预算分配方案")
        try:
            budget_allocation = budget_allocation_parser.parse(response.content)
            state["budget_allocation"] = budget_allocation
            state["status"] = "checking"
            state["messages"] = []
        except Exception as e:
            print(f"[WARN] 解析预算分配失败: {e}")
            state["error"] = f"预算分配解析失败: {e}"
            state["budget_allocation"] = None
            state["status"] = "checking"
            state["messages"] = []

    print(f"[DEBUG] budget_analyst_node 完成，状态: {state['status']}")
    return state
