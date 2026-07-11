"""
数据模型定义 - 旅行规划系统的核心数据结构

设计原则：
1. 使用 Pydantic 定义结构化数据模型，确保类型安全和数据校验
2. 子模型之间形成层次结构，从基础费用项到完整行程
3. TravelState 保持 TypedDict 格式以兼容 LangGraph 的状态管理
4. 每个模型都配置了对应的 PydanticOutputParser，用于解析 LLM 输出
5. messages 字段使用 Annotated[list, add_messages] 支持 LangGraph ToolNode
"""
from typing import TypedDict, Optional, List, Annotated
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser
from langgraph.graph.message import add_messages


# ========== 基础子模型 ==========

class CostItem(BaseModel):
    """费用明细项 - 用于记录各项开销"""
    name: str = Field(..., description="费用名称，如：经济型住宿、餐饮人均")
    amount: float = Field(..., ge=0, description="金额（元），必须大于等于0")
    category: str = Field(..., description="分类：accommodation(住宿)/food(餐饮)/transport(交通)/activity(活动)/other(其他)")


# ========== 节点输出模型 ==========

# ========== 目的地调研节点 ==========

class ResearchResult(BaseModel):
    """目的地调研结果 - researcher_node 的输出"""
    destination: str = Field(..., description="目的地名称")
    best_season: str = Field(default="", description="最佳旅行季节")
    cost_items: List[CostItem] = Field(default_factory=list, description="当地消费水平参考列表")
    notes: str = Field(default="", description="其他注意事项，如民俗、安全提示")


# ========== 预算分配节点 ==========

class BudgetAllocation(BaseModel):
    """预算分配方案 - budget_analyst_node 的输出"""
    total_budget: float = Field(..., description="总预算金额（元）")
    categories: List[CostItem] = Field(default_factory=list, description="各项预算分配明细")
    remaining: float = Field(default=0.0, description="剩余备用金")
    assessment: str = Field(default="充足", description="预算评估：充足/紧张/不足")


# ========== 预算分配节点 ==========

class Activity(BaseModel):
    """单项活动安排 - 行程中的基本单元"""
    name: str = Field(..., description="活动名称")
    time_slot: str = Field(default="", description="时间段：morning(上午)/afternoon(下午)/evening(晚上)")
    duration_hours: float = Field(default=2.0, description="预计时长（小时）")
    cost: float = Field(default=0.0, description="费用（元）")


class DayPlan(BaseModel):
    """每日行程计划"""
    day: int = Field(..., description="第几天（从1开始）")
    activities: List[Activity] = Field(default_factory=list, description="当天的活动列表")
    estimated_cost: float = Field(default=0.0, description="当日预计总花费")


class Itinerary(BaseModel):
    """完整行程规划 - planner_node 的输出"""
    destination: str = Field(..., description="目的地名称")
    days: int = Field(..., description="总天数")
    day_plans: List[DayPlan] = Field(default_factory=list, description="每日行程列表")
    total_estimated_cost: float = Field(default=0.0, description="全程预计总花费")

class BudgetAnalysis(BaseModel):
    """预算分析结果 - budget_check_node 的输出"""
    total_estimated: float = Field(default=0.0, description="实际预估总花费")
    is_over_budget: bool = Field(default=False, description="是否超预算")
    over_amount: float = Field(default=0.0, description="超预算金额（未超支为0）")
    suggestions: List[str] = Field(default_factory=list, description="调整建议列表")


# ========== 新架构：分层数据结构 ==========
class SimplePOI(BaseModel):
    """轻量化景点信息 - 仅含骨架数据，不拉取长篇介绍"""
    poi_id: str = Field(default="", description="高德 POI ID")
    name: str = Field(..., description="景点名称")
    longitude: float = Field(default=0.0, description="经度")
    latitude: float = Field(default=0.0, description="纬度")
    district: str = Field(default="", description="所属片区，如：市区/湄洲岛/九鲤湖")
    category: str = Field(default="", description="景点分类：自然风光/人文/亲子/美食/购物")


class ScenicDetail(BaseModel):
    """景点详情 - 仅路线选中的景点才加载"""
    poi_id: str = Field(..., description="高德 POI ID")
    name: str = Field(..., description="景点名称")
    description: str = Field(default="", description="景点核心看点")
    ticket_price: float = Field(default=0.0, description="门票价格（元）")
    opening_hours: str = Field(default="", description="开放时间")
    rating: str = Field(default="", description="评分")
    phone: str = Field(default="", description="联系电话")


class WeatherData(BaseModel):
    """天气数据"""
    city: str = Field(..., description="城市名称")
    date: str = Field(default="", description="日期")
    weather: str = Field(default="", description="天气状况")
    temperature: str = Field(default="", description="温度范围")
    humidity: str = Field(default="", description="湿度")


class RoutePOI(BaseModel):
    """路线中的景点条目"""
    poi_id: str = Field(..., description="高德 POI ID")
    name: str = Field(..., description="景点名称")
    day: int = Field(..., description="第几天")
    order: int = Field(default=1, description="当天游览顺序")
    time_slot: str = Field(default="morning", description="时段：morning/afternoon/evening")
    duration_hours: float = Field(default=2.0, description="预计游玩时长")


"""粗路线骨架 - 仅含景点顺序，无详情"""
class RoughRoute(BaseModel):
    destination: str = Field(..., description="目的地")
    days: int = Field(..., description="总天数")
    route_pois: List[RoutePOI] = Field(default_factory=list, description="路线中所有景点")


"""路线相关片区价格"""
class RoutePrice(BaseModel):
    district: str = Field(..., description="片区名称")
    hotel_low: float = Field(default=0.0, description="经济型酒店最低价（元/晚）")
    hotel_high: float = Field(default=0.0, description="经济型酒店最高价（元/晚）")
    meal_low: float = Field(default=0.0, description="餐饮人均最低（元/餐）")
    meal_high: float = Field(default=0.0, description="餐饮人均最高（元/餐）")
    transport_estimate: float = Field(default=0.0, description="片区内日均交通估算（元）")


# ========== LangGraph 状态定义 ==========

"""LangGraph 状态定义 - 在节点之间流转的全局状态"""
class TravelState(TypedDict):
    destination: str  # 目的地
    days: int  # 出行天数
    budget: float  # 总预算（元）
    interests: str  # 兴趣偏好
    messages: Annotated[list, add_messages]  # 消息列表，用于 ToolNode 的工具调用循环
    research_result: Optional[ResearchResult] = None  # 调研结果
    budget_allocation: Optional[BudgetAllocation] = None  # 预算分配方案
    itinerary: Optional[Itinerary] = None  # 行程规划
    budget_analysis: Optional[BudgetAnalysis] = None  # 预算分析结果
    iteration_count: int = 0  # 迭代次数，防止无限循环（最大3次）
    needs_adjustment: bool = False  # 是否需要调整行程
    error: Optional[str] = None  # 错误信息（如有）
    status: str = "researching"  # 当前状态：researching/budgeting/planning/checking/completed/failed
    # 新架构：分层数据字段
    simple_city_poi: Optional[List[dict]] = None  # 全城轻量化景点列表（仅名称/ID/坐标/片区/分类）
    selected_scenic_detail: Optional[List[dict]] = None  # 路线选中景点的详情
    raw_route: Optional[dict] = None  # 粗路线骨架
    route_related_price: Optional[List[dict]] = None  # 路线相关片区的价格
    weather: Optional[dict] = None  # 天气数据


# ========== 需求参数模型 ==========

"""旅行需求参数 - 对话收集阶段使用"""
class TravelDemand(BaseModel):
    destination: Optional[str] = Field(default=None, description="旅行目的地城市，完整名称")
    days: Optional[int] = Field(default=None, description="旅行总天数，正整数")
    budget: Optional[float] = Field(default=None, description="总预算上限，单位默认人民币")
    interests: Optional[str] = Field(default=None, description="旅行兴趣偏好，逗号分隔的标签")


# ========== 输出解析器 ==========
# 每个解析器对应一个模型，用于将 LLM 的 JSON 输出解析为结构化对象

demand_parser = PydanticOutputParser(pydantic_object=TravelDemand)
research_parser = PydanticOutputParser(pydantic_object=ResearchResult)
budget_allocation_parser = PydanticOutputParser(pydantic_object=BudgetAllocation)
itinerary_parser = PydanticOutputParser(pydantic_object=Itinerary)
budget_analysis_parser = PydanticOutputParser(pydantic_object=BudgetAnalysis)