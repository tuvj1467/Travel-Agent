from enum import Enum

# 定义所有流程状态
class FlowStatus(str, Enum):
    # 初始
    INIT = "init"
    # 检索阶段
    RESEARCHER = "researcher"
    # 调用工具
    TOOL_CALLING = "tool_calling"
    # 规划行程
    PLANNER = "planner"
    # 达到工具调用上限
    MAX_TOOL_LIMIT = "max_tool_limit"
    # 流程正常结束
    FINISHED = "finished"
    # 流程异常结束
    FAILED = "failed"
    # 异常
    ERROR = "error"
