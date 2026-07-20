"""
预算检查节点 - 对比行程实际预估费用与预算，判断是否超支

设计原则：
1. 用 itinerary.total_estimated_cost 直接对比 budget（代码计算，不靠 LLM）
2. 超支时才调用 LLM 生成调整建议
3. 未超支时跳过 LLM，直接通过
"""
from langchain_core.prompts import ChatPromptTemplate

from models.models import TravelState
from models.models import budget_analysis_parser, BudgetAnalysis
from config.config import llm
from utils.utils import retry_on_rate_limit


@retry_on_rate_limit(max_retries=3, delay=2)
async def budget_check_node(state: TravelState) -> TravelState:
    """预算检查节点 - 验证行程是否超预算"""
    print(f"[DEBUG] 执行 budget_check_node，当前迭代次数: {state['iteration_count']}")

    itinerary = state.get("itinerary")
    budget = state.get("budget", 0)
    budget_allocation = state.get("budget_allocation")
    tolerance = budget * 0.1  # 10% 容忍度

    if not itinerary:
        print(f"[WARN] 无行程数据，跳过预算检查")
        state["needs_adjustment"] = False
        return state

    # 代码层直接对比，不靠 LLM
    estimated_total = itinerary.total_estimated_cost
    over_amount = estimated_total - budget

    print(f"[DEBUG] 行程预估: ¥{estimated_total:.2f}, 预算: ¥{budget:.2f}, "
          f"差值: ¥{over_amount:.2f}, 容忍度: ¥{tolerance:.2f}")

    if over_amount <= 0:
        # 未超支
        state["needs_adjustment"] = False
        state["budget_analysis"] = BudgetAnalysis(
            total_estimated=estimated_total,
            is_over_budget=False,
            over_amount=0,
            suggestions=[]
        )
        print(f"[DEBUG] 未超支，无需调整")
    elif over_amount <= tolerance:
        # 在容忍度内
        state["needs_adjustment"] = False
        state["budget_analysis"] = BudgetAnalysis(
            total_estimated=estimated_total,
            is_over_budget=True,
            over_amount=over_amount,
            suggestions=[f"超支 ¥{over_amount:.0f} 在容忍度 {tolerance:.0f} 元内，暂不调整"]
        )
        print(f"[DEBUG] 超支 ¥{over_amount:.2f}，但在容忍度内，不调整")
    else:
        # 超支，用 LLM 生成调整建议
        state["needs_adjustment"] = True
        state["iteration_count"] += 1
        print(f"[DEBUG] 超支 ¥{over_amount:.2f}，需要调整，迭代次数: {state['iteration_count']}")

        # 生成调整建议
        if state["iteration_count"] <= 3:
            itinerary_text = itinerary.model_dump_json(indent=2)
            allocation_text = (
                budget_allocation.model_dump_json(indent=2) if budget_allocation else "无"
            )

            prompt = ChatPromptTemplate.from_messages([
                ("system", """你是旅行预算顾问。

行程规划（实际花费 {estimated_total} 元，超预算 {budget} 元）：
{itinerary}

当前预算分配：
{allocation}

【任务】：生成具体的调整建议，使行程控制在 {budget} 元以内。

【调整优先级】：
1. 优先：替换高价景点为同片区平价替代
2. 次要：调整餐饮预算（降低餐标）
3. 最后：住宿降级（经济型 → 青旅）
4. 不要：建议"取消机票"——往返交通是刚性支出

{format_instructions}"""),
                ("human", f"行程超支 ¥{over_amount:.0f}，请给出具体调整建议")
            ]).partial(format_instructions=budget_analysis_parser.get_format_instructions())

            chain = prompt | llm
            response = await chain.ainvoke({
                "estimated_total": estimated_total,
                "budget": budget,
                "itinerary": itinerary_text,
                "allocation": allocation_text
            })

            try:
                budget_analysis = budget_analysis_parser.parse(response.content)
                # 确保字段正确
                budget_analysis.total_estimated = estimated_total
                budget_analysis.is_over_budget = True
                budget_analysis.over_amount = over_amount
                state["budget_analysis"] = budget_analysis
            except Exception as e:
                print(f"[WARN] 解析调整建议失败: {e}")
                state["budget_analysis"] = BudgetAnalysis(
                    total_estimated=estimated_total,
                    is_over_budget=True,
                    over_amount=over_amount,
                    suggestions=[f"建议减少 ¥{over_amount:.0f} 的开支"]
                )
        else:
            # 超过 3 次迭代，强制通过
            print(f"[DEBUG] 已达最大迭代次数 3，强制通过")
            state["needs_adjustment"] = False
            state["budget_analysis"] = BudgetAnalysis(
                total_estimated=estimated_total,
                is_over_budget=True,
                over_amount=over_amount,
                suggestions=["已达最大调整次数，请手动调整预算"]
            )

    print(f"[DEBUG] 是否需要调整: {state['needs_adjustment']}")
    print(f"[DEBUG] budget_check_node 完成")
    return state
