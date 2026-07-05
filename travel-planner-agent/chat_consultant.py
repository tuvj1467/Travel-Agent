"""
对话需求收集模块
"""
import re
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import ToolMessage

from models import TravelDemand, demand_parser
from config import llm, tavily_search


def retry_on_rate_limit(max_retries=3, delay=2):
    """重试装饰器，处理速率限制错误"""
    import time
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


class DemandChatConsultant:
    """交互式对话需求顾问"""
    
    def __init__(self):
        self.history_store = InMemoryChatMessageHistory()
        self.tools = [tavily_search]
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

        self.chain = prompt | self.llm_with_tools

    @retry_on_rate_limit(max_retries=3, delay=2)
    def chat(self, user_input: str) -> tuple[str, TravelDemand]:
        """单轮对话，返回回复文本和当前收集到的需求参数"""
        input_vars = {
            "user_input": user_input,
            "chat_history": self.history_store.messages
        }
        response = self.chain.invoke(input_vars)

        # 循环处理工具调用
        tool_call_count = 0
        max_tool_calls = 3
        while response.tool_calls and tool_call_count < max_tool_calls:
            tool_call_count += 1
            print(f"[DEBUG] 工具调用次数: {tool_call_count}")
            tool_messages = []
            for call in response.tool_calls:
                target_tool = next(t for t in self.tools if t.name == call["name"])
                tool_result = target_tool.invoke(call["args"])
                tool_messages.append(ToolMessage(content=str(tool_result), tool_call_id=call["id"]))

            self.history_store.add_messages([response, *tool_messages])
            input_vars["chat_history"] = self.history_store.messages
            response = self.chain.invoke(input_vars)

        # 保存对话历史
        self.history_store.add_user_message(user_input)
        self.history_store.add_ai_message(response.content)

        # 提取结构化参数
        try:
            demand = demand_parser.parse(response.content)
        except Exception:
            demand = self._extract_demand_from_history()

        # 清理掉AI回复里的JSON部分
        reply_text = response.content.split("```json")[0].strip()
        return reply_text, demand

    def _extract_demand_from_history(self) -> TravelDemand:
        """从对话历史中提取旅行需求参数"""
        all_messages = self.history_store.messages
        full_text = "\n".join([msg.content for msg in all_messages if hasattr(msg, 'content')])
        
        demand = TravelDemand()
        
        # 提取目的地
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
