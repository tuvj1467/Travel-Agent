"""
目的地调研节点 - 轻量化素材采集

设计原则：
1. 代码层做数据自检，确定缺少哪些数据
2. 仅拉取景点骨架数据（名称/ID/坐标/片区/分类），不拉详情
3. 天气数据单独采集
4. 严格禁止使用 tavily_search，只用高德地图工具
"""
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage, ToolMessage

from models.models import TravelState
from models.models import research_parser
from config.config import llm
from agent.tool_node import get_tools
from utils.utils import retry_on_rate_limit


def _check_data_completeness(state: TravelState) -> dict:
    """代码层数据自检：返回缺失的数据项"""
    missing = []
    if not state.get("simple_city_poi"):
        missing.append("simple_city_poi")
    if not state.get("weather"):
        missing.append("weather")
    return {
        "has_poi": state.get("simple_city_poi") is not None,
        "has_weather": state.get("weather") is not None,
        "missing": missing,
        "complete": len(missing) == 0
    }


@retry_on_rate_limit(max_retries=3, delay=2)
async def researcher_node(state: TravelState) -> TravelState:
    """目的地调研节点 - 轻量化素材采集
    
    采集策略：
    1. 代码层检查 simple_city_poi 和 weather 是否存在
    2. 缺失则引导 LLM 调用对应的高德工具
    3. 只采集骨架数据，不拉取详情
    """
    print(f"[DEBUG] 执行 researcher_node，目的地: {state['destination']}")

    # 数据自检
    completeness = _check_data_completeness(state)
    print(f"[DEBUG] 数据自检: POI={'有' if completeness['has_poi'] else '无'}, "
          f"天气={'有' if completeness['has_weather'] else '无'}")

    # 数据齐全，直接流转
    if completeness["complete"]:
        print(f"[DEBUG] 数据已齐全，跳过采集，流转到下一阶段")
        state["status"] = "budgeting"
        return state

    tools = get_tools()
    llm_with_tools = llm.bind_tools(tools)
    history_messages = state.get("messages", [])

    # 构建工具引导提示
    tool_hints = []
    if not completeness["has_poi"]:
        tool_hints.append("- 缺少景点数据：请调用 maps_text_search 搜索「{destination} 景点」，获取景点名称、POI ID、经纬度、所属片区")
    if not completeness["has_weather"]:
        tool_hints.append("- 缺少天气数据：请调用 maps_weather 查询「{destination}」天气")

    system_prompt = """你是一名旅行地理信息采集员，职责是收集{destination}的基础地理骨架数据用于后续的路线规划。

【当前缺失数据】：
{hints}

【工具使用指南】- 优先用高德地图工具

【采集铁律】：
1. 景点搜索只获取骨架数据(名称、ID、经纬度、片区、分类)，绝对不要拉取详情
2. 严禁编造任何数据

{format_instructions}"""

    if not history_messages:
        system_msg = SystemMessage(content=system_prompt.format(
            destination=state["destination"],
            hints="\n".join(tool_hints),
            format_instructions=research_parser.get_format_instructions()
        ))
        human_msg = HumanMessage(
            content=f"请采集{state['destination']}的基础地理骨架数据，"
                    f"缺失项：{', '.join(completeness['missing'])}"
        )
        messages_to_send = [system_msg, human_msg]
    else:
        messages_to_send = list(history_messages)

    response = await llm_with_tools.ainvoke(messages_to_send)

    if not history_messages:
        state["messages"] = messages_to_send + [response]
    else:
        state["messages"] = [response]

    if isinstance(response, AIMessage) and response.tool_calls:
        tool_names = [tc['name'] for tc in response.tool_calls]
        print(f"[DEBUG] LLM 请求工具调用: {tool_names}")
        state["status"] = "tool_calling"
        current_count = state.get("tool_call_count", 0) or 0
        state["tool_call_count"] = current_count + 1
        print(f"[DEBUG] 工具调用次数: {state['tool_call_count']}/5")
    else:
        print(f"[DEBUG] LLM 返回采集结果，尝试解析")
        try:
            research_result = research_parser.parse(response.content)
            state["research_result"] = research_result
            state["status"] = "budgeting"
            # 清空 messages，为后续节点腾出 token 空间
            state["messages"] = []
        except Exception as e:
            print(f"[WARN] 解析调研结果失败: {e}")
            state["error"] = f"调研解析失败: {e}"
            state["research_result"] = None
            state["status"] = "budgeting"
            state["messages"] = []

    print(f"[DEBUG] researcher_node 完成，状态: {state['status']}")
    return state