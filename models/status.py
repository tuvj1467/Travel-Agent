from enum import Enum


class FlowStatus(str, Enum):
    """工作流状态枚举 - v2.0 匹配需求文档"""

    # 偏好收集阶段
    COLLECTING = "collecting"           # 收集偏好中

    # 搜索阶段
    SEARCHING_POIS = "searching_pois"         # 搜索景点中
    SEARCHING_WEATHER = "searching_weather"   # 查询天气中
    SEARCHING_FLIGHTS = "searching_flights"   # 搜索航班中
    SEARCHING_HOTELS = "searching_hotels"     # 搜索酒店中

    # 规划阶段
    GENERATING = "generating"           # 生成行程中

    # 预算阶段
    BUDGETING = "budgeting"             # 预算分析中
    CHECKING = "checking"               # 预算校验中

    # 交互阶段
    PRESENTING = "presenting"           # 呈现行程中
    REFINING = "refining"               # 优化行程中

    # 终态
    FINALIZED = "finalized"             # 已完成
    FAILED = "failed"                   # 失败
