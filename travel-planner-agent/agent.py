"""
Travel Planner Agent using CrewAI.

Multi-agent crew that creates personalized travel itineraries:
- Destination Researcher: gathers destination info
- Activity Planner: creates day-by-day activities
- Budget Analyst: estimates costs

Usage:
    python agent.py --destination "Tokyo, Japan" --days 5 --budget 2000
"""

import argparse
import time
import re

import litellm
from langchain_core.chat_history import InMemoryChatMessageHistory

import config
from typing import Optional

from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
# from langchain.memory import ConversationBufferMemory
from langchain_classic.memory import ConversationBufferMemory

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

# load_dotenv()

#网页搜索工具
tavily_search = TavilySearch(max_results=10)

llm = ChatOpenAI(
    model=config.QIANFANG_MODEL,
    base_url=config.QIANFANG_BASE_URL,
    api_key=config.QIANFANG_API_KEY,
    temperature=0.4
)

# ========== 重试装饰器 ==========
def retry_on_rate_limit(max_retries=3, delay=2):
    """重试装饰器，处理速率限制错误"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if "429" in str(e) or "速率限制" in str(e) or "1302" in str(e):
                        if attempt < max_retries - 1:
                            wait_time = delay * (attempt + 1)
                            print(f"[WARN] 遇到速率限制，等待 {wait_time} 秒后重试... (尝试 {attempt + 1}/{max_retries})")
                            time.sleep(wait_time)
                            continue
                    raise
        return wrapper
    return decorator

# ========== LangGraph 状态定义 ==========
class TravelState(TypedDict):
    """旅行规划状态"""
    destination: str  #目的地
    days: int     # 出行天数
    budget: float   #预算
    interests: str   #  兴趣
    research_result: str  # 调研结果
    budget_allocation: str  # 预算分配
    itinerary: str  # 行程规划
    budget_analysis: str  # 预算分析结果
    iteration_count: int  # 迭代次数，防止无限循环
    needs_adjustment: bool  # 是否需要调整

# ========== 结构化需求参数模型 ==========
class TravelDemand(BaseModel):
    destination: Optional[str] = Field(default=None, description="旅行目的地城市，完整名称")
    days: Optional[int] = Field(default=None, description="旅行总天数，正整数")
    budget: Optional[float] = Field(default=None, description="总预算上限，单位默认人民币")
    interests: Optional[str] = Field(default=None, description="旅行兴趣偏好，逗号分隔的标签")

demand_parser = PydanticOutputParser(pydantic_object=TravelDemand)


# ========== 第一层：交互式对话需求顾问 ==========
class DemandChatConsultant:
    def __init__(self):
        # self.memory = ConversationBufferMemory(
        #     memory_key="chat_history",
        #     return_messages=True
        # )
        self.history_store = InMemoryChatMessageHistory()

        self.tools = [tavily_search]
        # 新增：给LLM绑定搜索工具，让模型具备调用工具能力
        self.llm_with_tools = llm.bind_tools(self.tools)
        self._build_chat_chain()

    def _build_chat_chain(self):
        prompt = ChatPromptTemplate.from_messages([
            ("system", """
                你是一名专业的旅行顾问，擅长通过友好的对话引导用户明确旅行需求。
                你的核心工作：
                1. 从对话中逐步收集 4 项核心信息：目的地城市、出行天数、总预算、兴趣偏好
                2. 信息缺失时主动提问，一次只问 1-2 个问题，不要一次性抛出所有问题
                3. 用户对目的地/行程迷茫时，必须使用搜索工具查询当下热门、符合预算、适配季节的目的地，给出 2-3 个推荐供用户选择
                4. 不要提前生成详细行程，只负责收集需求和给出建议
                5. 每次回复的末尾，必须附带当前收集到的参数状态，严格遵循以下 JSON 格式：
                {format_instructions}

                回复规则：
                - 语气自然友好，不要机械生硬
                - 用户信息模糊时主动引导，不要强行脑补
                - 推荐目的地时说明推荐理由（季节适配、消费水平、特色亮点）
                - 4 项信息全部收集完成后，询问用户是否确认并开始生成详细行程
            """),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{user_input}")
        ]).partial(format_instructions=demand_parser.get_format_instructions())

        # 改动：链式管道使用绑定了工具的 llm_with_tools，不再使用原始 llm
        self.chain = prompt | self.llm_with_tools

    @retry_on_rate_limit(max_retries=3, delay=2)
    def chat(self, user_input: str) -> tuple[str, TravelDemand]:
        """单轮对话，返回回复文本和当前收集到的需求参数"""
        input_vars = {
            "user_input": user_input,
            "chat_history": self.history_store.messages
        }
        response = self.chain.invoke(input_vars)

        # ========= 新增：循环处理工具调用 =========
        from langchain_core.messages import ToolMessage
        # 如果模型需要调用搜索工具，循环执行
        tool_call_count = 0
        max_tool_calls = 3  # 限制最多3次工具调用
        while response.tool_calls and tool_call_count < max_tool_calls:
            tool_call_count += 1
            print(f"[DEBUG] 工具调用次数: {tool_call_count}")
            tool_messages = []
            # 遍历所有要调用的工具
            for call in response.tool_calls:
                # 匹配对应工具
                target_tool = next(t for t in self.tools if t.name == call["name"])
                # 执行搜索
                tool_result = target_tool.invoke(call["args"])
                # 封装工具返回消息
                tool_messages.append(ToolMessage(content=str(tool_result), tool_call_id=call["id"]))

            # 将工具调用记录、搜索结果写入历史
            # self.memory.chat_memory.add_messages([response, *tool_messages])
             # 修改 self.memory → self.history_store
            self.history_store.add_messages([response, *tool_messages])
            # 重新调用模型，结合搜索结果生成最终回答
            input_vars["chat_history"] = self.history_store.messages
            response = self.chain.invoke(input_vars)
        # ========================================

        # 保存对话历史
        # self.memory.chat_memory.add_user_message(user_input)
        # self.memory.chat_memory.add_ai_message(response.content)
        # 保存对话历史 全部替换
        self.history_store.add_user_message(user_input)
        self.history_store.add_ai_message(response.content)

        # 提取结构化参数
        try:
            demand = demand_parser.parse(response.content)
        except Exception:
            # 解析失败时从对话历史中提取
            demand = self._extract_demand_from_history()

        # 清理掉AI回复里的JSON部分，只保留自然语言回复给用户
        reply_text = response.content.split("```json")[0].strip()
        return reply_text, demand

    def _extract_demand_from_history(self) -> TravelDemand:
        """从对话历史中提取旅行需求参数"""
        import re
        
        # 获取所有对话内容
        all_messages = self.history_store.messages
        full_text = "\n".join([msg.content for msg in all_messages if hasattr(msg, 'content')])
        
        demand = TravelDemand()
        
        # 提取目的地（城市名）
        # 匹配"去XX旅游"、"XX游玩"、"到XX"等模式
        city_patterns = [
            r'去([^\s，。、,]{2,10})旅游',
            r'去([^\s，。、,]{2,10})游玩',
            r'到([^\s，。、,]{2,10})',
            r'从[^\s，。、,]{2,10}去([^\s，。、,]{2,10})',
        ]
        for pattern in city_patterns:
            match = re.search(pattern, full_text)
            if match:
                demand.destination = match.group(1)
                break
        
        # 提取天数
        day_match = re.search(r'(\d+)\s*[天日]', full_text)
        if day_match:
            demand.days = int(day_match.group(1))
        
        # 提取预算
        budget_match = re.search(r'(\d+)\s*[元块钱]', full_text)
        if budget_match:
            demand.budget = float(budget_match.group(1))
        
        # 提取兴趣
        interest_keywords = ['自然风光', '文化', '历史', '美食', '购物', '探险', '休闲']
        found_interests = []
        for keyword in interest_keywords:
            if keyword in full_text:
                found_interests.append(keyword)
        if found_interests:
            demand.interests = ",".join(found_interests)
        
        return demand

    def is_demand_complete(self, demand: TravelDemand) -> bool:
        """校验4项核心参数是否全部收集完成"""
        return all([
            demand.destination,
            demand.days and demand.days > 0,
            demand.budget and demand.budget > 0,
            demand.interests
        ])


# ========== LangGraph 节点函数 ==========

@retry_on_rate_limit(max_retries=3, delay=2)
def researcher_node(state: TravelState) -> TravelState:
    """目的地调研节点"""
    print(f"[DEBUG] 执行 researcher_node，目的地: {state['destination']}")

    # 先联网查询实时价格信息
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
        涵盖内容：最佳出行时节、推荐住宿片区及价格区间、必打卡景点及门票价格、
        当地特色美食及消费水平、市内交通指南及费用、当地民俗注意事项。
        游客偏好：{interests}

        请特别关注当地的消费水平，包括：
        - 经济型住宿价格范围（元/晚）
        - 餐饮人均消费（元/餐）
        - 景点门票价格
        - 市内交通费用

        重要：必须参考以下联网搜索的实时价格信息，避免价格幻觉：
        {search_context}"""),
        ("human", "请提供{destination}的综合调研简报")
    ])

    chain = prompt | llm
    research_result = chain.invoke({
        "destination": state["destination"],
        "days": state["days"],
        "interests": state["interests"],
        "search_context": search_context
    })

    state["research_result"] = research_result.content
    print(f"[DEBUG] researcher_node 完成")
    return state


@retry_on_rate_limit(max_retries=3, delay=2)
def budget_analyst_node(state: TravelState) -> TravelState:
    """预算分析师节点 - 前置预算分配"""
    print(f"[DEBUG] 执行 budget_analyst_node，预算: {state['budget']}元")
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一名旅行财务顾问。
        根据目的地调研结果，在{budget}元总预算范围内，为{days}天旅行制定预算分配方案。
        
        调研信息：
        {research_result}
        
        请提供：
        1. 各项预算分配（住宿、餐饮、交通、门票、其他）
        2. 每项预算的具体限制
        3. 如果预算紧张，标注哪些项目需要特别注意
        4. 给出省钱建议
        
        输出格式要求清晰，方便后续规划师参考。"""),
        ("human", "请制定{destination}{days}天的预算分配方案")
    ])
    
    chain = prompt | llm
    budget_allocation = chain.invoke({
        "destination": state["destination"],
        "days": state["days"],
        "budget": state["budget"],
        "research_result": state["research_result"]
    })
    
    state["budget_allocation"] = budget_allocation.content
    print(f"[DEBUG] budget_analyst_node 完成")
    return state


@retry_on_rate_limit(max_retries=3, delay=2)
def planner_node(state: TravelState) -> TravelState:
    """行程规划节点 - 在预算约束下规划"""
    print(f"[DEBUG] 执行 planner_node，迭代次数: {state['iteration_count']}")
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一名拥有15年经验的高端旅行顾问。
        为{destination}制作{days}日旅行行程，必须严格遵守预算限制。
        
        预算分配方案：
        {budget_allocation}
        
        调研信息：
        {research_result}
        
        游客偏好：{interests}
        
        要求：
        1. 严格在预算分配范围内规划
        2. 包含早/中/晚间活动安排
        3. 推荐具体餐厅和景点，考虑价格因素
        4. 各景点间通勤耗时和费用
        5. 行程节奏合理，游玩体验舒适
        6. 如果某项活动可能超预算，说明原因并给出替代方案
        
        输出按天划分的完整行程。"""),
        ("human", "请规划{destination}{days}天的详细行程")
    ])
    
    chain = prompt | llm
    itinerary = chain.invoke({
        "destination": state["destination"],
        "days": state["days"],
        "interests": state["interests"],
        "budget_allocation": state["budget_allocation"],
        "research_result": state["research_result"]
    })
    
    state["itinerary"] = itinerary.content
    print(f"[DEBUG] planner_node 完成")
    return state


@retry_on_rate_limit(max_retries=3, delay=2)
def budget_check_node(state: TravelState) -> TravelState:
    """预算检查节点 - 验证行程是否超预算"""
    print(f"[DEBUG] 执行 budget_check_node，当前迭代次数: {state['iteration_count']}")
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一名旅行财务顾问。
        请分析以下行程是否在{budget}元预算范围内。

        行程规划：
        {itinerary}

        预算分配：
        {budget_allocation}

        请分析：
        1. 估算行程的实际总花费
        2. 对比预算{budget}元，判断是否超支
        3. 如果超支，指出超支项目和金额
        4. 如果超支，给出具体的调整建议

        输出格式：
        - 预估总花费：XXX元
        - 是否超支：是/否
        - 超支金额：XXX元（如未超支则写0）
        - 调整建议：..."""),
        ("human", "请分析行程预算情况")
    ])

    chain = prompt | llm
    budget_analysis = chain.invoke({
        "budget": state["budget"],
        "itinerary": state["itinerary"],
        "budget_allocation": state["budget_allocation"]
    })

    state["budget_analysis"] = budget_analysis.content

    # 判断是否需要调整
    analysis_text = budget_analysis.content.lower()
    is_over_budget = "超支" in analysis_text or "超出" in analysis_text

    # 提取超支金额
    over_budget_amount = 0
    amount_match = re.search(r'超支金额[：:]\s*(\d+)', analysis_text)
    if amount_match:
        over_budget_amount = int(amount_match.group(1))

    # 如果超支但不超过10%，则不需要调整
    tolerance = state["budget"] * 0.1  # 10%容忍度
    if is_over_budget and over_budget_amount <= tolerance:
        print(f"[DEBUG] 超支{over_budget_amount}元，但在容忍度{tolerance:.0f}元内，不调整")
        state["needs_adjustment"] = False
    elif is_over_budget:
        state["needs_adjustment"] = True
        state["iteration_count"] += 1
        print(f"[DEBUG] 需要调整，迭代次数增加到: {state['iteration_count']}")
    else:
        state["needs_adjustment"] = False

    print(f"[DEBUG] 是否需要调整: {state['needs_adjustment']}")
    print(f"[DEBUG] budget_check_node 完成")
    return state


def should_adjust(state: TravelState) -> str:
    """条件边函数：决定是否需要调整行程"""
    # 如果超支且迭代次数小于3次，返回planner重新规划
    if state["needs_adjustment"] and state["iteration_count"] < 3:
        print(f"[DEBUG] 条件边：需要调整，返回planner (迭代次数: {state['iteration_count']})")
        return "planner"
    # 否则结束
    print(f"[DEBUG] 条件边：不需要调整或达到最大迭代次数，结束流程")
    return END


def build_travel_graph(demand: TravelDemand) -> str:
    """构建并执行LangGraph旅行规划流程"""
    # 初始化状态
    initial_state: TravelState = {
        "destination": demand.destination,
        "days": demand.days,
        "budget": demand.budget,
        "interests": demand.interests,
        "research_result": "",
        "budget_allocation": "",
        "itinerary": "",
        "budget_analysis": "",
        "iteration_count": 0,
        "needs_adjustment": False
    }
    
    # 构建图
    workflow = StateGraph(TravelState)
    
    # 添加节点
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("budget_analyst", budget_analyst_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("budget_check", budget_check_node)
    
    # 设置入口点
    workflow.set_entry_point("researcher")
    
    # 添加边
    workflow.add_edge("researcher", "budget_analyst")
    workflow.add_edge("budget_analyst", "planner")
    workflow.add_edge("planner", "budget_check")
    
    # 添加条件边：如果超支则回到planner，否则结束
    workflow.add_conditional_edges(
        "budget_check",
        should_adjust,
        {
            "planner": "planner",
            END: END
        }
    )
    
    # 编译图
    app = workflow.compile()
    
    # 执行流程
    print("🔍 开始调研目的地信息...")
    final_state = app.invoke(initial_state)
    
    # 格式化输出
    result = f"""
    {'='*60}
    📋 旅行规划报告
    {'='*60}
    
    📍 目的地：{final_state['destination']}
    📅 天数：{final_state['days']}天
    💰 预算：{final_state['budget']}元
    🎯 兴趣：{final_state['interests']}
    
    {'='*60}
    🔍 目的地调研
    {'='*60}
    {final_state['research_result']}
    
    {'='*60}
    💵 预算分配方案
    {'='*60}
    {final_state['budget_allocation']}
    
    {'='*60}
    🗓️ 详细行程规划
    {'='*60}
    {final_state['itinerary']}
    
    {'='*60}
    📊 预算分析
    {'='*60}
    {final_state['budget_analysis']}
    
    {'='*60}
    迭代次数：{final_state['iteration_count']}
    {'='*60}
    """
    
    return result

#900元去莆田旅游3天 ，自然风景
def main():
    print("=" * 60)
    print("✈️  智能旅行规划助手")
    print("告诉我你的旅行想法，我会帮你逐步完善并生成详细行程")
    print("输入 quit 可随时退出")
    print("=" * 60 + "\n")

    consultant = DemandChatConsultant()

    while True:
        user_input = input("你: ").strip()
        if user_input.lower() in ["quit", "exit", "q"]:
            print("助手: 期待下次为你规划旅行，再见！")
            break

        if not user_input:
            continue

        reply, demand = consultant.chat(user_input)
        print(f"\n助手: {reply}\n")

        # 参数收集完成且用户确认后，启动规划
        if consultant.is_demand_complete(demand):
            confirm = input("确认以上需求并生成详细行程吗？(yes/no): ").strip().lower()
            if confirm in ["yes", "y", "确认"]:
                print("\n🔍 正在为你生成详细旅行方案，请稍候...\n")
                itinerary = build_travel_graph(demand)
                print(itinerary)
                break
            else:
                print("\n助手: 好的，你可以告诉我需要调整的地方~")

    # parser = argparse.ArgumentParser(description="Travel Planner Agent")
    # parser.add_argument("--destination", default="Tokyo, Japan", help="Travel destination")
    # parser.add_argument("--days", type=int, default=7, help="Number of days")
    # parser.add_argument("--budget", type=float, default=3000, help="Total budget in USD")
    # parser.add_argument("--interests", default="food, culture, history", help="Traveler interests")
    # args = parser.parse_args()
    #
    # print(f"\n✈️  Planning {args.days}-day trip to {args.destination} (Budget: ${args.budget})\n")
    # itinerary = build_travel_crew(args.destination, args.days, args.budget, args.interests)
    #
    # print("=" * 60)
    # print("🗺️  TRAVEL ITINERARY")
    # print("=" * 60)
    # print(itinerary)


if __name__ == "__main__":
    main()
