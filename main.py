"""
旅行规划助手 - 主程序入口（异步版本）
"""

import argparse
import asyncio
import json
from models.models import TravelDemand
from agent.graph_builder import build_travel_graph


def format_itinerary(result: dict) -> str:
    """
    将旅行规划结果格式化为可读的文本报告
    """

    report = []
    report.append('=' * 60)
    report.append('📋 旅行规划报告')
    report.append('=' * 60)
    report.append(f"\n📍 目的地：{result['destination']}")
    report.append(f"📅 天数：{result['days']}天")
    report.append(f"💰 预算：{result['budget']}元")
    report.append(f"🎯 兴趣：{result['interests']}")

    if result['research_result']:
        report.append(f"\n{'=' * 60}")
        report.append('🔍 目的地调研')
        report.append('=' * 60)
        research = result['research_result']
        report.append(f"最佳季节：{research.get('best_season', '')}")
        report.append("\n消费水平参考：")
        for item in research.get('cost_items', []):
            report.append(f"  - {item['name']}：¥{item['amount']} ({item['category']})")
        if research.get('notes'):
            report.append(f"\n注意事项：{research['notes']}")

    if result['budget_allocation']:
        report.append(f"\n{'=' * 60}")
        report.append('💵 预算分配方案')
        report.append('=' * 60)
        budget = result['budget_allocation']
        report.append(f"总预算：¥{budget.get('total_budget', 0)}")
        report.append("\n各项分配：")
        for cat in budget.get('categories', []):
            report.append(f"  - {cat['name']}：¥{cat['amount']} ({cat['category']})")
        report.append(f"\n备用金：¥{budget.get('remaining', 0)}")
        report.append(f"预算评估：{budget.get('assessment', '')}")

    if result['itinerary']:
        report.append(f"\n{'=' * 60}")
        report.append('🗓️ 详细行程规划')
        report.append('=' * 60)
        itinerary = result['itinerary']
        for day_plan in itinerary.get('day_plans', []):
            report.append(f"\n第{day_plan['day']}天（预计花费：¥{day_plan.get('estimated_cost', 0)}）")
            for activity in day_plan.get('activities', []):
                time_slot = activity.get('time_slot', '')
                duration = activity.get('duration_hours', 0)
                cost = activity.get('cost', 0)
                cost_str = f"¥{cost}" if cost > 0 else "免费"
                report.append(f"  [{time_slot:6s}] {activity['name']} ({duration}h) {cost_str}")
        report.append(f"\n全程预计：¥{itinerary.get('total_estimated_cost', 0)}")

    if result['budget_analysis']:
        report.append(f"\n{'=' * 60}")
        report.append('📊 预算分析')
        report.append('=' * 60)
        analysis = result['budget_analysis']
        report.append(f"预估总花费：¥{analysis.get('total_estimated', 0)}")
        report.append(f"是否超支：{'是' if analysis.get('is_over_budget') else '否'}")
        if analysis.get('is_over_budget'):
            report.append(f"超支金额：¥{analysis.get('over_amount', 0)}")
        if analysis.get('suggestions'):
            report.append("\n调整建议：")
            for suggestion in analysis['suggestions']:
                report.append(f"  - {suggestion}")

    report.append(f"\n{'=' * 60}")
    report.append(f"迭代次数：{result['iteration_count']}")
    report.append('=' * 60)

    if result['error']:
        report.append(f"\n⚠️  错误：{result['error']}")

    return '\n'.join(report)


async def main():
    parser = argparse.ArgumentParser(description="智能旅行规划助手")
    parser.add_argument("--destination", required=True, help="旅行目的地城市，完整名称")
    parser.add_argument("--days", type=int, required=True, help="旅行总天数，正整数")
    parser.add_argument("--budget", type=float, required=True, help="总预算上限，单位：元")
    parser.add_argument("--interests", required=True, help="旅行兴趣偏好，逗号分隔的标签")
    parser.add_argument("--output", choices=["text", "json"], default="text", help="输出格式：text(文本报告) 或 json(结构化数据)")
    args = parser.parse_args()

    print("=" * 60)
    print("✈️  智能旅行规划助手")
    print("=" * 60)
    print(f"📍 目的地：{args.destination}")
    print(f"📅 天数：{args.days}天")
    print(f"💰 预算：{args.budget}元")
    print(f"🎯 兴趣：{args.interests}")
    print("=" * 60)
    print("\n🔍 正在为你生成详细旅行方案，请稍候...\n")

    demand = TravelDemand(
        destination=args.destination,
        days=args.days,
        budget=args.budget,
        interests=args.interests
    )

    result = await build_travel_graph(demand)

    if args.output == "text":
        print(format_itinerary(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
