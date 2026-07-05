"""
数据模型定义
"""
from typing import TypedDict, Optional
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser


# ========== LangGraph 状态定义 ==========
class TravelState(TypedDict):
    """旅行规划状态"""
    destination: str  # 目的地
    days: int  # 出行天数
    budget: float  # 预算
    interests: str  # 兴趣
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
