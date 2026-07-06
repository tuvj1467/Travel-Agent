"""
旅行规划助手 - 主程序入口
"""

import json
from chat_consultant import DemandChatConsultant
from graph_builder import build_travel_graph

def format_itinerary(result: dict) -> str:
    """格式化行程输出（CLI模式）"""
    return f"""
{'='*60}
📋 旅行规划报告
{'='*60}

📍 目的地：{result['destination']}
📅 天数：{result['days']}天
💰 预算：{result['budget']}元
🎯 兴趣：{result['interests']}

{'='*60}
🔍 目的地调研
{'='*60}
{result['research_result']}

{'='*60}
💵 预算分配方案
{'='*60}
{result['budget_allocation']}

{'='*60}
🗓️ 详细行程规划
{'='*60}
{result['itinerary']}

{'='*60}
📊 预算分析
{'='*60}
{result['budget_analysis']}

{'='*60}
迭代次数：{result['iteration_count']}
{'='*60}
"""

def main():
    print("=" * 60)
    print("✈️  智能旅行规划助手")
    print("告诉我你的旅行想法，我会帮你逐步完善并生成详细行程")
    print("输入 quit 可随时退出")
    print("=" * 60 + "\n")

    consultant = DemandChatConsultant()

    while True:
        user_input = input("你: ").strip()
        if user_input.lower() in ["quit", "exit", "q"]:
            print("助手: 期待下次为你规划旅行，再见！")
            break

        if not user_input:
            continue

        reply, demand = consultant.chat(user_input)
        print(f"\n助手: {reply}\n")

        # 参数收集完成且用户确认后，启动规划
        if consultant.is_demand_complete(demand):
            confirm = input("确认以上需求并生成详细行程吗？(yes/no): ").strip().lower()
            if confirm in ["yes", "y", "确认"]:
                print("\n🔍 正在为你生成详细旅行方案，请稍候...\n")
                result = build_travel_graph(demand)
                # CLI模式：格式化输出
                print(format_itinerary(result))
                # API模式：可以直接返回result字典或json.dumps(result)
                break
            else:
                print("\n助手: 好的，你可以告诉我需要调整的地方~")

    # parser = argparse.ArgumentParser(description="Travel Planner Agent")
    # parser.add_argument("--destination", default="Tokyo, Japan", help="Travel destination")
    # parser.add_argument("--days", type=int, default=7, help="Number of days")
    # parser.add_argument("--budget", type=float, default=3000, help="Total budget in USD")
    # parser.add_argument("--interests", default="food, culture, history", help="Traveler interests")
    # args = parser.parse_args()
    #
    # print(f"\n✈️  Planning {args.days}-day trip to {args.destination} (Budget: ${args.budget})\n")
    # itinerary = build_travel_crew(args.destination, args.days, args.budget, args.interests)
    #
    # print("=" * 60)
    # print("🗺️  TRAVEL ITINERARY")
    # print("=" * 60)
    # print(itinerary)
#900去莆田旅游3天,自然风光

if __name__ == "__main__":
    main()
