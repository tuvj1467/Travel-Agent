"""
预算分析师节点 - 基于行程进行预算分配

设计原则：
1. 基于 itinerary 中的费用估算和总预算进行预算分配
2. 不再调用工具查询价格（景点详情已由 researcher 获取）
3. 直接生成预算分配方案
"""
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage

from models.models import TravelState
from models.models import budget_allocation_parser
from config.config import llm
from utils.utils import retry_on_rate_limit


@retry_on_rate_limit(max_retries=3, delay=2)
async def budget_analyst_node(state: TravelState) -> TravelState:
    """预算分析师节点 - 基于行程进行预算分配

    流程：
    1. 基于 itinerary 中的费用估算
    2. 在总预算范围内制定预算分配方案
    3. 输出预算分配明细
    """
    print(f"[DEBUG] 执行 budget_analyst_node，预算: {state['budget']}元")

    itinerary = state.get("itinerary")

    if not itinerary:
        print(f"[WARN] 缺少行程数据，无法进行预算分配")
        state["error"] = "缺少行程数据"
        state["status"] = "checking"
        return state

    itinerary_text = itinerary.model_dump_json(indent=2)

    system_prompt = """你是一名旅行财务顾问。

【任务】
基于行程规划和总预算，制定合理的预算分配方案。

【行程规划】：
{itinerary}

【总预算】：{budget}元
【出行天数】：{days}天

【预算分配原则】：
1. 门票费用：基于行程中的门票价格
2. 住宿费用：根据天数估算经济型酒店费用
3. 餐饮费用：根据天数估算每日餐饮费用
4. 交通费用：估算景点间交通费用
5. 备用金：预留 10-15% 作为应急资金
6. 确保总分配不超过总预算
7. 严禁负数、严禁编造

{format_instructions}"""

    system_msg = SystemMessage(content=system_prompt.format(
        budget=state["budget"],
        days=state["days"],
        itinerary=itinerary_text[:3000],
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
