"""
行程规划节点 - 两阶段规划

设计原则：
1. 阶段1（粗骨架）：基于 simple_city_poi 生成 roughRoute（仅景点ID和顺序）
2. 阶段2（完整行程）：基于 roughRoute + selected_scenic_detail 生成完整 itinerary

注意：景点详情由 researcher 节点预先获取，planner 不再调用工具查询详情
"""
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

from models.models import TravelState
from models.models import itinerary_parser, roughRoute_parser
from config.config import llm
from utils.utils import retry_on_rate_limit


@retry_on_rate_limit(max_retries=3, delay=2)
async def planner_node(state: TravelState) -> TravelState:
    """行程规划节点 - 两阶段规划

    阶段1：基于 simple_city_poi 生成 roughRoute（粗路线骨架）
    阶段2：基于 roughRoute + selected_scenic_detail 生成完整 itinerary
    """
    print(f"[DEBUG] 执行 planner_node，迭代次数: {state['iteration_count']}")

    simple_city_poi = state.get("simple_city_poi")
    rough_route = state.get("roughRoute")
    selected_detail = state.get("selected_scenic_detail")

    # 数据自检
    if not simple_city_poi:
        print(f"[WARN] 缺少基础地理骨架数据，返回 researcher_node")
        state["status"] = "researcher"
        return state

    # 阶段判断
    stage = "rough_route"  # 默认阶段1
    if rough_route and selected_detail:
        stage = "final_itinerary"
    elif rough_route and not selected_detail:
        # 有粗路线但没有详情，使用粗路线直接生成行程（降级处理）
        print(f"[WARN] 缺少景点详情，使用粗路线降级生成行程")
        stage = "final_itinerary"

    print(f"[DEBUG] planner 当前阶段: {stage}")

    # 阶段1：生成粗路线骨架（roughRoute）
    if stage == "rough_route":
        poi_text = str(simple_city_poi)

        system_prompt = """你是一名旅行路线规划师，专精地理空间排布。

        【当前阶段】粗路线骨架搭建。

        【可用景点骨架数据】（仅含名称、坐标、片区、分类）：
        {poi_data}

        【规划原则】：
        1. 地理聚类：按片区（district）拆分景点，同片区安排在同一天
        2. 偏好筛选：根据用户偏好「{interests}」过滤，选择最相关的景点
        3. 合理安排：每天最多安排 2-3 个景点，避免行程过密
        4. 时间分配：每个景点游览时长 2-3 小时，上午 1 个，下午 1-2 个
        5. 避免重复：不要安排名称相似或地理位置重叠的景点（如"凤凰山"和"凤凰山公园"选其一）
        6. 片区内排序：按坐标就近排列，减少路途时间

        【输出要求】：
        仅输出路线骨架，包含景点ID、名称、第几天、游览顺序、时段、时长。

        {format_instructions}"""

        system_msg = SystemMessage(content=system_prompt.format(
            poi_data=poi_text,
            interests=state["interests"],
            days=state["days"],
            max_pois=state["days"] * 3,
            format_instructions=roughRoute_parser.get_format_instructions()
        ))
        human_msg = HumanMessage(
            content=f"请为{state['destination']}搭建{state['days']}天行程骨架（粗路线）"
        )
        messages_to_send = [system_msg, human_msg]

        response = await llm.ainvoke(messages_to_send)

        try:
            rough_route = roughRoute_parser.parse(response.content)
            state["roughRoute"] = rough_route
            print(f"[DEBUG] 粗路线骨架生成完成")
            state["status"] = "planning"  # 继续进入阶段2
            state["messages"] = []
        except Exception as e:
            print(f"[WARN] 解析粗路线失败: {e}")
            state["error"] = f"粗路线解析失败: {e}"
            state["roughRoute"] = None
            state["status"] = "checking"
            state["messages"] = []

    # 阶段2：生成完整行程（itinerary）
    elif stage == "final_itinerary":
        detail_text = str(selected_detail) if selected_detail else "无详情数据"
        route_text = str(rough_route)

        system_prompt = """你是一名旅行路线规划师。

        【当前阶段】生成完整行程规划。

        【路线骨架】：
        {route_data}

        【景点详情】：
        {detail_data}

        【任务】：
        基于路线骨架和景点详情，生成完整的行程规划，包含：
        - 每天的活动安排
        - 时间段和时长
        - 费用估算（基于景点详情中的门票价格，如无详情则估算）

        【费用估算原则】：
        1. 优先使用景点详情中的 ticket_price 字段
        2. 如 ticket_price 为 0 或空，根据景点类型估算（自然风光通常免费，人文景点可能有门票）
        3. 住宿费用：根据天数估算经济型酒店费用（约 150-300 元/晚）
        4. 餐饮费用：根据天数估算每日餐饮费用（约 100-150 元/天）
        5. 交通费用：估算景点间交通费用（约 50-100 元/天）

        {format_instructions}"""

        system_msg = SystemMessage(content=system_prompt.format(
            route_data=route_text,
            detail_data=detail_text,
            format_instructions=itinerary_parser.get_format_instructions()
        ))
        human_msg = HumanMessage(
            content=f"请生成{state['destination']}的完整行程规划"
        )
        messages_to_send = [system_msg, human_msg]

        response = await llm.ainvoke(messages_to_send)

        try:
            itinerary = itinerary_parser.parse(response.content)
            state["itinerary"] = itinerary
            print(f"[DEBUG] 完整行程生成完成")
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
