"""
预算分析师节点 - 基于行程和航班进行预算分配

设计原则：
1. 基于 itinerary 中的各项费用进行预算分配
2. 整合航班费用到预算中
3. 为住宿、餐饮、交通分配预算
4. 直接生成预算分配方案
"""
from langchain_core.messages import SystemMessage, HumanMessage

from models.models import TravelState
from models.models import budget_allocation_parser
from config.config import llm
from utils.utils import retry_on_rate_limit


@retry_on_rate_limit(max_retries=3, delay=2)
async def budget_analyst_node(state: TravelState) -> TravelState:
    """预算分析师节点 - 基于行程进行预算分配

    流程：
    1. 基于 itinerary 中的各项费用
    2. 整合航班费用到预算中
    3. 在总预算范围内制定预算分配方案
    4. 输出预算分配明细
    """
    print(f"[DEBUG] 执行 budget_analyst_node，预算: {state['budget']}元")

    itinerary = state.get("itinerary")

    if not itinerary:
        print(f"[WARN] 缺少景区路线数据，无法进行预算分配")
        state["error"] = "缺少景区路线数据"
        state["status"] = "checking"
        return state

    itinerary_text = itinerary.model_dump_json(indent=2)

    # 航班信息
    flights = state.get("flights", [])
    has_airport = state.get("has_airport", False)
    flight_cost_text = ""
    if flights and len(flights) > 0:
        cheapest = min(flights, key=lambda f: f.ticket_price)
        flight_cost_text = (
            f"有直飞航班，最低票价 ¥{cheapest.ticket_price} "
            f"（{cheapest.flight_no} {cheapest.airline_name}）"
        )
    else:
        flight_cost_text = "无双直飞航班，按高铁往返估算 ¥800-1000"

    system_prompt = """你是一名旅行财务顾问。

【任务】
基于行程规划和总预算，制定预算分配方案。

【行程规划】：
{itinerary}

【航班费用】：{flight_cost}
【总预算】：{budget}元
【出行天数】：{days}天（住宿 {days}晚）

【要求】：
请如实列出各项费用明细，不要为了凑预算而压低实际价格。

费用分类应包括：
1. 往返交通：航班或高铁费用
2. 住宿费用：经济型酒店约 150-200 元/晚
3. 门票费用：基于行程中的门票价格
4. 餐饮费用：约 100-150 元/天
5. 市内交通：景点间交通约 50-80 元/天
6. 备用金：预留约 10%

【注意】：
- 如实反映真实花费，t总花费可以超过总预算
- 后续节点会判断是否超支并生成调整建议
- 严禁编造价格、严禁调整价格来凑预算

{format_instructions}"""

    system_msg = SystemMessage(content=system_prompt.format(
        budget=state["budget"],
        days=state["days"],
        itinerary=itinerary_text[:3000],
        flight_cost=flight_cost_text,
        format_instructions=budget_allocation_parser.get_format_instructions()
    ))
    human_msg = HumanMessage(content="请制定预算分配方案")

    response = await llm.ainvoke([system_msg, human_msg])

    try:
        budget_allocation = budget_allocation_parser.parse(response.content)
        state["budget_allocation"] = budget_allocation
        print(f"[DEBUG] 预算分配方案生成完成")
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
