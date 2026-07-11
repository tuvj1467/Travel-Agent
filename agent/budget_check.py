"""
预算检查节点
"""
from langchain_core.prompts import ChatPromptTemplate

from models.models import TravelState
from models.models import budget_analysis_parser
from config.config import llm
from utils.utils import retry_on_rate_limit


@retry_on_rate_limit(max_retries=3, delay=2)
async def budget_check_node(state: TravelState) -> TravelState:
    """预算检查节点 - 验证行程是否超预算，输出结构化 BudgetAnalysis（异步版本）"""
    print(f"[DEBUG] 执行 budget_check_node，当前迭代次数: {state['iteration_count']}")

    budget_allocation = state["budget_allocation"]
    itinerary = state["itinerary"]

    budget_text = budget_allocation.model_dump_json(indent=2) if budget_allocation else "无预算数据"
    itinerary_text = itinerary.model_dump_json(indent=2) if itinerary else "无行程数据"

    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一名旅行财务顾问。
        请分析以下行程是否在{budget}元预算范围内。

        行程规划：
        {itinerary}

        预算分配：
        {budget_allocation}

        【重要禁令】：
        1. 严禁编造价格！必须基于预算分配中的价格信息
        2. 严禁编造轮渡价格！轮渡和门票独立计算
        3. 严禁编造交通费用！基于调研信息估算
        4. 严禁编造住宿价格！基于预算分配中的价格范围
        5. 如果预算分配中某项价格不明确，标注"基于预算分配估算"，不要编造

        请分析：
        1. 估算行程的实际总花费（基于预算分配）
        2. 对比预算{budget}元，判断是否超支
        3. 如果超支，指出超支项目和金额
        4. 如果超支，给出具体的调整建议

        请严格按照以下JSON格式输出：
        {format_instructions}"""),
        ("human", "请分析行程预算情况，基于预算分配，禁止编造价格")
    ]).partial(format_instructions=budget_analysis_parser.get_format_instructions())

    chain = prompt | llm
    response = await chain.ainvoke({
        "budget": state["budget"],
        "itinerary": itinerary_text,
        "budget_allocation": budget_text
    })

    try:
        budget_analysis = budget_analysis_parser.parse(response.content)
        state["budget_analysis"] = budget_analysis
    except Exception as e:
        print(f"[WARN] 解析预算分析失败: {e}")
        state["error"] = f"预算分析解析失败: {e}"
        state["budget_analysis"] = None
        return state

    budget_analysis = state["budget_analysis"]
    tolerance = state["budget"] * 0.1

    if budget_analysis.is_over_budget and budget_analysis.over_amount <= tolerance:
        print(f"[DEBUG] 超支{budget_analysis.over_amount}元，但在容忍度{tolerance:.0f}元内，不调整")
        state["needs_adjustment"] = False
    elif budget_analysis.is_over_budget:
        state["needs_adjustment"] = True
        state["iteration_count"] += 1
        print(f"[DEBUG] 需要调整，迭代次数增加到: {state['iteration_count']}")
    else:
        state["needs_adjustment"] = False

    print(f"[DEBUG] 是否需要调整: {state['needs_adjustment']}")
    print(f"[DEBUG] budget_check_node 完成")
    return state
