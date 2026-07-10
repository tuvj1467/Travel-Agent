"""
LangGraph 节点函数 - 适配结构化输出
"""
import re
from langchain_core.prompts import ChatPromptTemplate

from models.models import TravelState
from models.models import (
    research_parser,
    budget_allocation_parser,
    itinerary_parser,
    budget_analysis_parser
)
from config.config import llm, tavily_search
from utils.utils import retry_on_rate_limit


@retry_on_rate_limit(max_retries=3, delay=2)
def researcher_node(state: TravelState) -> TravelState:
    """目的地调研节点 - 输出结构化 ResearchResult"""
    print(f"[DEBUG] 执行 researcher_node，目的地: {state['destination']}")

    search_queries = [
        f"{state['destination']} 门票价格 轮渡费用",
        f"{state['destination']} 住宿价格 消费水平",
        f"{state['destination']} 交通费用 公交票价"
    ]

    search_results = []
    for query in search_queries:
        try:
            result = tavily_search.invoke(query)
            search_results.append(f"搜索结果: {query}\n{result}\n")
        except Exception as e:
            print(f"[WARN] 搜索失败: {query}, 错误: {e}")

    search_context = "\n".join(search_results) if search_results else "搜索无结果"

    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一名资深旅行撰稿人，游历过100多个国家。
        请调研{destination}的相关信息，适配{days}天出行需求。
        游客偏好：{interests}

        请特别关注当地的消费水平，包括：
        - 经济型住宿价格范围（元/晚）
        - 餐饮人均消费（元/餐）
        - 景点门票价格
        - 市内交通费用

        【重要禁令】：
        1. 严禁编造价格信息！必须严格参考以下联网搜索结果
        2. 如果搜索结果中没有某项价格信息，明确标注"暂无数据"，不要编造
        3. 严禁编造地理信息（如码头对应关系、航线是否存在）
        4. 严禁编造轮渡价格，区分基础票和套票
        5. 所有价格必须标注来源（搜索结果/官方信息）

        联网搜索的实时价格信息：
        {search_context}

        请严格按照以下JSON格式输出：
        {format_instructions}"""),
        ("human", "请提供{destination}的综合调研简报，严格基于搜索结果，禁止编造")
    ]).partial(format_instructions=research_parser.get_format_instructions())

    chain = prompt | llm
    response = chain.invoke({
        "destination": state["destination"],
        "days": state["days"],
        "interests": state["interests"],
        "search_context": search_context
    })

    try:
        research_result = research_parser.parse(response.content)
        state["research_result"] = research_result
    except Exception as e:
        print(f"[WARN] 解析调研结果失败: {e}")
        state["error"] = f"调研解析失败: {e}"
        state["research_result"] = None

    state["status"] = "budgeting"
    print(f"[DEBUG] researcher_node 完成")
    return state


@retry_on_rate_limit(max_retries=3, delay=2)
def budget_analyst_node(state: TravelState) -> TravelState:
    """预算分析师节点 - 前置预算分配，输出结构化 BudgetAllocation"""
    print(f"[DEBUG] 执行 budget_analyst_node，预算: {state['budget']}元")

    research_result = state["research_result"]
    research_text = research_result.model_dump_json(indent=2) if research_result else "无调研数据"

    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一名旅行财务顾问。
        根据目的地调研结果，在{budget}元总预算范围内，为{days}天旅行制定预算分配方案。

        调研信息：
        {research_result}

        【重要禁令】：
        1. 严禁出现负数分项！所有预算分项必须≥0
        2. 严禁倒推凑数！必须采用正向计算逻辑：
           - 先扣除刚性成本（门票、轮渡等固定费用）
           - 再计算必需成本（住宿、餐饮）
           - 最后分配弹性成本（交通、其他）
           - 剩余作为备用金
        3. 如果刚性成本+必需成本已超过预算，明确告知用户"预算不足"，不要编造低价
        4. 严禁编造价格！必须基于调研结果中的价格信息
        5. 严禁把轮渡费用算在门票里，两者独立计算

        请严格按照以下JSON格式输出：
        {format_instructions}"""),
        ("human", "请制定{destination}{days}天的预算分配方案，正向计算，禁止负数")
    ]).partial(format_instructions=budget_allocation_parser.get_format_instructions())

    chain = prompt | llm
    response = chain.invoke({
        "destination": state["destination"],
        "days": state["days"],
        "budget": state["budget"],
        "research_result": research_text
    })

    try:
        budget_allocation = budget_allocation_parser.parse(response.content)
        state["budget_allocation"] = budget_allocation
    except Exception as e:
        print(f"[WARN] 解析预算分配失败: {e}")
        state["error"] = f"预算分配解析失败: {e}"
        state["budget_allocation"] = None

    state["status"] = "planning"
    print(f"[DEBUG] budget_analyst_node 完成")
    return state


@retry_on_rate_limit(max_retries=3, delay=2)
def planner_node(state: TravelState) -> TravelState:
    """行程规划节点 - 在预算约束下规划，输出结构化 Itinerary"""
    print(f"[DEBUG] 执行 planner_node，迭代次数: {state['iteration_count']}")

    research_result = state["research_result"]
    budget_allocation = state["budget_allocation"]

    research_text = research_result.model_dump_json(indent=2) if research_result else "无调研数据"
    budget_text = budget_allocation.model_dump_json(indent=2) if budget_allocation else "无预算数据"

    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一名拥有15年经验的高端旅行顾问。
        为{destination}制作{days}日旅行行程，必须严格遵守预算限制。

        预算分配方案：
        {budget_allocation}

        调研信息：
        {research_result}

        游客偏好：{interests}

        【重要禁令】：
        1. 严禁编造地理信息！不要编造不存在的航线（如文甲码头到石城码头）
        2. 严禁编造码头对应关系！每个码头对应特定岛屿，不要混用
        3. 严禁编造轮渡价格！轮渡和门票独立计算，不要把轮渡算在门票里
        4. 严禁编造景点距离！如果不确定通勤时间，标注"预估"，不要编造具体时间
        5. 优先保留符合用户偏好的景点（如用户要求自然风光，不要替换成宗教景点）
        6. 如果预算紧张，优先减少景点数量，不要编造低价

        要求：
        1. 严格在预算分配范围内规划
        2. 包含早/中/晚间活动安排
        3. 推荐具体餐厅和景点，考虑价格因素
        4. 各景点间通勤耗时和费用（基于调研信息）
        5. 行程节奏合理，游玩体验舒适
        6. 如果某项活动可能超预算，说明原因并给出替代方案

        请严格按照以下JSON格式输出：
        {format_instructions}"""),
        ("human", "请规划{destination}{days}天的详细行程，基于调研信息，禁止编造")
    ]).partial(format_instructions=itinerary_parser.get_format_instructions())

    chain = prompt | llm
    response = chain.invoke({
        "destination": state["destination"],
        "days": state["days"],
        "interests": state["interests"],
        "budget_allocation": budget_text,
        "research_result": research_text
    })

    try:
        itinerary = itinerary_parser.parse(response.content)
        state["itinerary"] = itinerary
    except Exception as e:
        print(f"[WARN] 解析行程规划失败: {e}")
        state["error"] = f"行程解析失败: {e}"
        state["itinerary"] = None

    state["status"] = "checking"
    print(f"[DEBUG] planner_node 完成")
    return state


@retry_on_rate_limit(max_retries=3, delay=2)
def budget_check_node(state: TravelState) -> TravelState:
    """预算检查节点 - 验证行程是否超预算，输出结构化 BudgetAnalysis"""
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
    response = chain.invoke({
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