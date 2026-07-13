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
from pydantic import BaseModel, Field, model_validator, field_validator
from langchain_core.output_parsers import PydanticOutputParser
from langgraph.graph.message import add_messages
from utils.utils import PydanticListOutputParser


# ========== 基础子模型 ==========

class CostItem(BaseModel):
    """费用明细项 - 用于记录各项开销"""
    name: str = Field(..., description="费用名称，如：经济型住宿、餐饮人均")
    amount: float = Field(..., ge=0, description="金额（元），必须大于等于0")
    category: str = Field(..., description="分类：accommodation(住宿)/food(餐饮)/transport(交通)/activity(活动)/other(其他)")


# ========== 节点输出模型 ==========

# ========== 目的地调研节点 ==========




# ========== 预算分配节点 ==========

class BudgetAllocation(BaseModel):
    """预算分配方案 - budget_analyst_node 的输出"""
    total_budget: float = Field(..., description="总预算金额（元）")
    categories: List[CostItem] = Field(default_factory=list, description="各项预算分配明细")
    remaining: float = Field(default=0.0, description="剩余备用金")
    assessment: str = Field(default="充足", description="预算评估：充足/紧张/不足")


# ========== 旅行规划节点 ==========

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


# ========== 预算分析节点 ==========
class BudgetAnalysis(BaseModel):
    """预算分析结果 - budget_check_node 的输出"""
    total_estimated: float = Field(default=0.0, description="实际预估总花费")
    is_over_budget: bool = Field(default=False, description="是否超预算")
    over_amount: float = Field(default=0.0, description="超预算金额（未超支为0）")
    suggestions: List[str] = Field(default_factory=list, description="调整建议列表")


# ========== 节点输出模型 ==========


# ========== 新架构：分层数据结构 ==========
class SimplePOI(BaseModel):
    """轻量化景点信息 - text_search 返回的精简字段

    字段映射（高德 MCP text_search → SimplePOI）：
    - id → poi_id
    - name → name
    - location（"经度,纬度"字符串）→ longitude, latitude
    - adname → district
    - type → category（简化为第一级分类）
    - address → address（可选）

    注意：text_search 不包含 cost、opentime2、tag、photo、parking_type 等深度信息
    """
    poi_id: str = Field(default="", alias="id", description="高德 POI ID")
    name: str = Field(..., description="景点名称")
    longitude: float = Field(default=0.0, description="经度")
    latitude: float = Field(default=0.0, description="纬度")
    district: str = Field(default="", alias="adname", description="所属片区，如：市区/湄洲岛/九鲤湖")
    category: str = Field(default="", alias="type", description="景点分类")
    address: str = Field(default="", description="详细地址")

    @model_validator(mode="before")
    @classmethod
    def _parse_location(cls, data):
        """从 location 字段拆分经纬度"""
        if isinstance(data, dict):
            location = data.get("location", "")
            if isinstance(location, str) and "," in location:
                parts = location.split(",")
                if len(parts) == 2:
                    try:
                        data["longitude"] = float(parts[0])
                        data["latitude"] = float(parts[1])
                    except (ValueError, TypeError):
                        pass
        return data

    @field_validator("category", mode="after")
    @classmethod
    def _simplify_category(cls, v):
        """简化分类：取分号分隔的第一级"""
        if isinstance(v, str) and ";" in v:
            return v.split(";")[0]
        return v
    
    model_config = {
        "populate_by_name": True,
        "extra": "ignore"
    }


class ScenicDetail(SimplePOI):
    """景点详情 - detail_search 返回的深度信息

    继承 SimplePOI 的所有字段，并添加深度信息字段。

    字段映射（高德 MCP detail_search → ScenicDetail）：
    - business_area → business_area（商圈）
    - cost → ticket_price（门票价格）
    - opentime2 → opening_hours（详细营业时间）
    - tag → tags（特色标签）
    - photos → photos（实拍图列表）
    - parking_type → parking_type（停车类型）
    - intro → description（景点介绍）

    这些是行程规划的关键素材：门票价格用于预算，营业时间用于时间安排，
    标签用于兴趣匹配，实拍图用于展示
    """
    business_area: str = Field(default="", description="所属商圈")
    ticket_price: float = Field(default=0.0, alias="cost", description="门票价格（元）")
    opening_hours: str = Field(default="", alias="opentime2", description="详细营业时间")
    tags: List[str] = Field(default_factory=list, alias="tag", description="特色标签")
    photos: List[str] = Field(default_factory=list, alias="photos", description="实拍图 URL 列表")
    parking_type: str = Field(default="", description="停车类型")
    description: str = Field(default="", alias="intro", description="景点介绍")
    rating: str = Field(default="", description="评分")
    phone: str = Field(default="", description="联系电话")

    @field_validator("ticket_price", mode="before")
    @classmethod
    def _parse_ticket_price(cls, v):
        """处理空字符串或无效的门票价格"""
        if isinstance(v, str):
            if not v or v.strip() == "":
                return 0.0
            try:
                return float(v)
            except (ValueError, TypeError):
                return 0.0
        return v

    model_config = {
        "populate_by_name": True,
        "extra": "ignore"
    }


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


class RoughRoute(BaseModel):
    """粗路线骨架 - 仅含景点顺序，无详情"""
    destination: str = Field(..., description="目的地")
    days: int = Field(..., description="总天数")
    route_pois: List[RoutePOI] = Field(default_factory=list, description="路线中所有景点")


class RoutePrice(BaseModel):
    """路线相关片区价格"""
    district: str = Field(..., description="片区名称")
    hotel_low: float = Field(default=0.0, description="经济型酒店最低价（元/晚）")
    hotel_high: float = Field(default=0.0, description="经济型酒店最高价（元/晚）")
    meal_low: float = Field(default=0.0, description="餐饮人均最低（元/餐）")
    meal_high: float = Field(default=0.0, description="餐饮人均最高（元/餐）")
    transport_estimate: float = Field(default=0.0, description="片区内日均交通估算（元）")


# ========== LangGraph 状态定义 ==========

class TravelState(TypedDict):
    """LangGraph 状态定义 - 在节点之间流转的全局状态"""
    destination: str  # 目的地
    days: int  # 出行天数
    budget: float  # 总预算（元）
    interests: str  # 兴趣偏好
    messages: Annotated[list, add_messages]  # 消息列表，用于 ToolNode 的工具调用循环


    budget_allocation: Optional[BudgetAllocation] = None  # 预算分配方案
    itinerary: Optional[Itinerary] = None  # 行程规划
    budget_analysis: Optional[BudgetAnalysis] = None  # 预算分析结果

    iteration_count: int = 0  # 迭代次数，防止无限循环（最大3次）
    needs_adjustment: bool = False  # 是否需要调整行程
    error: Optional[str] = None  # 错误信息（如有）
    status: str = "researching"  # 当前状态：researching/budgeting/planning/checking/completed/failed
    # 新架构：分层数据字段
    simple_city_poi: Optional[List[SimplePOI]] = None  # 全城轻量化景点列表（仅名称/ID/坐标/片区/分类）
    selected_scenic_detail: Optional[List[ScenicDetail]] = None  # 路线选中景点的详情
    
    roughRoute: Optional[RoughRoute] = None  # 粗路线骨架
    # route_related_price: Optional[List[RoutePrice]] = None  # 路线相关片区的价格
    weather: Optional[WeatherData] = None  # 天气数据
    routePOI: Optional[List[RoutePOI]] = None  # 路线中的景点条目


# ========== 需求参数模型 ==========

class TravelDemand(BaseModel):
    """旅行需求参数 - 对话收集阶段使用"""
    destination: Optional[str] = Field(default=None, description="旅行目的地城市，完整名称")
    days: Optional[int] = Field(default=None, description="旅行总天数，正整数")
    budget: Optional[float] = Field(default=None, description="总预算上限，单位默认人民币")
    interests: Optional[str] = Field(default=None, description="旅行兴趣偏好，逗号分隔的标签")


# ========== 输出解析器 ==========
# 每个解析器对应一个模型，用于将 LLM 的 JSON 输出解析为结构化对象

demand_parser = PydanticOutputParser(pydantic_object=TravelDemand)

budget_allocation_parser = PydanticOutputParser(pydantic_object=BudgetAllocation)
itinerary_parser = PydanticOutputParser(pydantic_object=Itinerary)
budget_analysis_parser = PydanticOutputParser(pydantic_object=BudgetAnalysis)

simplePOI_parser = PydanticOutputParser(pydantic_object=SimplePOI)
scenic_detail_parser = PydanticOutputParser(pydantic_object=ScenicDetail)
weather_parser = PydanticOutputParser(pydantic_object=WeatherData)
routePOI_parser = PydanticOutputParser(pydantic_object=RoutePOI)
roughRoute_parser = PydanticOutputParser(pydantic_object=RoughRoute)
# route_related_price_parser = PydanticOutputParser(pydantic_object=RoutePrice)

# ========== 列表解析器 ==========
# 用于直接解析 LLM 输出的列表类型，无需定义包装模型
# PydanticListOutputParser 类定义在 utils/utils.py 中


# 列表解析器实例
simple_poi_list_parser = PydanticListOutputParser(pydantic_type=SimplePOI)
scenic_detail_list_parser = PydanticListOutputParser(pydantic_type=ScenicDetail)
# route_related_price_list_parser = PydanticListOutputParser(pydantic_type=RoutePrice)
route_poi_list_parser = PydanticListOutputParser(pydantic_type=RoutePOI)


