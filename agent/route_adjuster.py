"""
路线调整工具 - 允许手动修改规划路线

功能：
1. 添加景点到指定天数
2. 删除景点
3. 调整景点顺序
4. 调整景点时间安排
5. 重新生成某天的行程
"""
from typing import List, Optional, Dict, Any
from models.models import Itinerary, DayPlan, Activity, ScenicDetail


class RouteAdjuster:
    """路线调整器 - 提供路线修改功能"""

    def __init__(self, scenic_details: List[ScenicDetail]):
        """
        Args:
            scenic_details: 可用的景点详情列表
        """
        self.scenic_details = scenic_details
        self.poi_map = {poi.poi_id: poi for poi in scenic_details}

    def add_activity(
        self,
        itinerary: Itinerary,
        day: int,
        poi_id: str,
        time_slot: str = "afternoon",
        duration_hours: float = 2.0,
        cost: float = 0.0
    ) -> Itinerary:
        """添加景点到指定天数

        Args:
            itinerary: 当前行程
            day: 目标天数
            poi_id: 要添加的景点ID
            time_slot: 时段（morning/afternoon/evening）
            duration_hours: 游览时长
            cost: 费用

        Returns:
            修改后的行程
        """
        if poi_id not in self.poi_map:
            raise ValueError(f"景点ID {poi_id} 不在可用景点列表中")

        poi = self.poi_map[poi_id]

        # 找到对应的天
        day_plan = None
        for dp in itinerary.day_plans:
            if dp.day == day:
                day_plan = dp
                break

        if not day_plan:
            # 创建新的一天
            day_plan = DayPlan(
                day=day,
                activities=[],
                estimated_cost=0.0
            )
            itinerary.day_plans.append(day_plan)

        # 创建活动
        activity = Activity(
            name=poi.name,
            time_slot=time_slot,
            duration_hours=duration_hours,
            cost=cost if cost > 0 else poi.ticket_price
        )

        day_plan.activities.append(activity)
        day_plan.estimated_cost += activity.cost
        itinerary.total_estimated_cost += activity.cost

        return itinerary

    def remove_activity(
        self,
        itinerary: Itinerary,
        day: int,
        activity_index: int
    ) -> Itinerary:
        """删除指定天数的活动

        Args:
            itinerary: 当前行程
            day: 天数
            activity_index: 活动索引

        Returns:
            修改后的行程
        """
        day_plan = None
        for dp in itinerary.day_plans:
            if dp.day == day:
                day_plan = dp
                break

        if not day_plan:
            raise ValueError(f"第 {day} 天不存在")

        if activity_index < 0 or activity_index >= len(day_plan.activities):
            raise ValueError(f"活动索引 {activity_index} 超出范围")

        activity = day_plan.activities.pop(activity_index)
        day_plan.estimated_cost -= activity.cost
        itinerary.total_estimated_cost -= activity.cost

        return itinerary

    def reorder_activities(
        self,
        itinerary: Itinerary,
        day: int,
        new_order: List[int]
    ) -> Itinerary:
        """调整指定天数的活动顺序

        Args:
            itinerary: 当前行程
            day: 天数
            new_order: 新的活动顺序（索引列表）

        Returns:
            修改后的行程
        """
        day_plan = None
        for dp in itinerary.day_plans:
            if dp.day == day:
                day_plan = dp
                break

        if not day_plan:
            raise ValueError(f"第 {day} 天不存在")

        if len(new_order) != len(day_plan.activities):
            raise ValueError("新顺序长度与活动数量不匹配")

        # 重新排序
        activities = [day_plan.activities[i] for i in new_order]
        day_plan.activities = activities

        return itinerary

    def adjust_activity_time(
        self,
        itinerary: Itinerary,
        day: int,
        activity_index: int,
        time_slot: Optional[str] = None,
        duration_hours: Optional[float] = None
    ) -> Itinerary:
        """调整活动的时间安排

        Args:
            itinerary: 当前行程
            day: 天数
            activity_index: 活动索引
            time_slot: 新的时段
            duration_hours: 新的时长

        Returns:
            修改后的行程
        """
        day_plan = None
        for dp in itinerary.day_plans:
            if dp.day == day:
                day_plan = dp
                break

        if not day_plan:
            raise ValueError(f"第 {day} 天不存在")

        if activity_index < 0 or activity_index >= len(day_plan.activities):
            raise ValueError(f"活动索引 {activity_index} 超出范围")

        activity = day_plan.activities[activity_index]

        if time_slot:
            activity.time_slot = time_slot
        if duration_hours:
            activity.duration_hours = duration_hours

        return itinerary

    def regenerate_day(
        self,
        itinerary: Itinerary,
        day: int,
        selected_poi_ids: List[str]
    ) -> Itinerary:
        """重新生成某天的行程

        Args:
            itinerary: 当前行程
            day: 天数
            selected_poi_ids: 选中的景点ID列表

        Returns:
            修改后的行程
        """
        # 删除该天原有活动
        day_plan = None
        for dp in itinerary.day_plans:
            if dp.day == day:
                day_plan = dp
                break

        if day_plan:
            # 扣除原有费用
            itinerary.total_estimated_cost -= day_plan.estimated_cost
            day_plan.activities = []
            day_plan.estimated_cost = 0.0
        else:
            # 创建新的一天
            day_plan = DayPlan(
                day=day,
                activities=[],
                estimated_cost=0.0
            )
            itinerary.day_plans.append(day_plan)

        # 添加新活动
        for i, poi_id in enumerate(selected_poi_ids):
            if poi_id not in self.poi_map:
                continue

            poi = self.poi_map[poi_id]
            time_slot = "morning" if i == 0 else "afternoon"

            activity = Activity(
                name=poi.name,
                time_slot=time_slot,
                duration_hours=2.0,
                cost=poi.ticket_price
            )

            day_plan.activities.append(activity)
            day_plan.estimated_cost += activity.cost
            itinerary.total_estimated_cost += activity.cost

        return itinerary

    def get_available_pois(self) -> List[Dict[str, Any]]:
        """获取可用景点列表（用于展示）

        Returns:
            景点信息列表
        """
        return [
            {
                "poi_id": poi.poi_id,
                "name": poi.name,
                "district": poi.district,
                "category": poi.category,
                "ticket_price": poi.ticket_price,
                "opening_hours": poi.opening_hours
            }
            for poi in self.scenic_details
        ]

    def get_day_summary(self, itinerary: Itinerary, day: int) -> Dict[str, Any]:
        """获取某天的行程摘要

        Args:
            itinerary: 当前行程
            day: 天数

        Returns:
            行程摘要
        """
        day_plan = None
        for dp in itinerary.day_plans:
            if dp.day == day:
                day_plan = dp
                break

        if not day_plan:
            return {"day": day, "activities": [], "estimated_cost": 0.0}

        return {
            "day": day,
            "activities": [
                {
                    "index": i,
                    "name": act.name,
                    "time_slot": act.time_slot,
                    "duration_hours": act.duration_hours,
                    "cost": act.cost
                }
                for i, act in enumerate(day_plan.activities)
            ],
            "estimated_cost": day_plan.estimated_cost
        }


def create_route_adjuster(scenic_details: List[ScenicDetail]) -> RouteAdjuster:
    """创建路线调整器工厂函数

    Args:
        scenic_details: 可用的景点详情列表

    Returns:
        RouteAdjuster 实例
    """
    return RouteAdjuster(scenic_details)
