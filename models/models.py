"""
数据模型定义 - 旅行规划系统的核心数据结构

设计原则：
1. 使用 Pydantic 定义结构化数据模型，确保类型安全和数据校验
2. 子模型之间形成层次结构，从基础费用项到完整行程
3. TravelState 保持 TypedDict 格式以兼容 LangGraph 的状态管理
4. 每个模型都配置了对应的 PydanticOutputParser，用于解析 LLM 输出
"""
from typing import TypedDict, Optional, List
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser


# ========== 基础子模型 ==========

class CostItem(BaseModel):
    """费用明细项 - 用于记录各项开销"""
    name: str = Field(..., description="费用名称，如：经济型住宿、餐饮人均")
    amount: float = Field(..., ge=0, description="金额（元），必须大于等于0")
    category: str = Field(..., description="分类：accommodation(住宿)/food(餐饮)/transport(交通)/activity(活动)/other(其他)")


# ========== 节点输出模型 ==========

class ResearchResult(BaseModel):
    """目的地调研结果 - researcher_node 的输出"""
    destination: str = Field(..., description="目的地名称")
    best_season: str = Field(default="", description="最佳旅行季节")
    cost_items: List[CostItem] = Field(default_factory=list, description="当地消费水平参考列表")
    notes: str = Field(default="", description="其他注意事项，如民俗、安全提示")


class BudgetAllocation(BaseModel):
    """预算分配方案 - budget_analyst_node 的输出"""
    total_budget: float = Field(..., description="总预算金额（元）")
    categories: List[CostItem] = Field(default_factory=list, description="各项预算分配明细")
    remaining: float = Field(default=0.0, description="剩余备用金")
    assessment: str = Field(default="充足", description="预算评估：充足/紧张/不足")


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


# ========== LangGraph 状态定义 ==========

class TravelState(TypedDict):
    """
    LangGraph 状态定义 - 在节点之间流转的全局状态
    
    状态流转：
    researching → budgeting → planning → checking → [planning(循环) / completed]
    
    字段说明：
    - 输入字段：destination, days, budget, interests（初始化时设置）
    - 节点输出字段：research_result, budget_allocation, itinerary, budget_analysis（各节点依次填充）
    - 控制字段：iteration_count, needs_adjustment（控制循环逻辑）
    - 追踪字段：error, status（记录流程状态和错误信息）
    """
    destination: str  # 目的地
    days: int  # 出行天数
    budget: float  # 总预算（元）
    interests: str  # 兴趣偏好
    research_result: Optional[ResearchResult] = None  # 调研结果
    budget_allocation: Optional[BudgetAllocation] = None  # 预算分配方案
    itinerary: Optional[Itinerary] = None  # 行程规划
    budget_analysis: Optional[BudgetAnalysis] = None  # 预算分析结果
    iteration_count: int = 0  # 迭代次数，防止无限循环（最大3次）
    needs_adjustment: bool = False  # 是否需要调整行程
    error: Optional[str] = None  # 错误信息（如有）
    status: str = "researching"  # 当前状态：researching/budgeting/planning/checking/completed/failed


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
research_parser = PydanticOutputParser(pydantic_object=ResearchResult)
budget_allocation_parser = PydanticOutputParser(pydantic_object=BudgetAllocation)
itinerary_parser = PydanticOutputParser(pydantic_object=Itinerary)
budget_analysis_parser = PydanticOutputParser(pydantic_object=BudgetAnalysis)