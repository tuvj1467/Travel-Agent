"""
工具执行节点 - 使用 LangGraph 内置 ToolNode

设计原则：
1. 使用 LangGraph 预构建的 ToolNode 处理工具调用
2. 工具列表集中管理，便于扩展新增工具
3. 添加工具注册快照日志，便于调试工具调用问题
4. 支持异步工具初始化（MCP 工具需要异步加载）
"""
from typing import List, Any, Callable
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage, ToolMessage

from tools.api.travily import tavily_search
from tools.mcp.gaode_mcp import gaode_tools, init_gaode_tools
from tools.mcp.juhe_mcp import juhe_tools, init_juhe_tools


# 基础工具列表（始终可用）
base_tools = [tavily_search]

# 全局工具节点（在 init_tools 后初始化）
tool_node = None


"""获取当前所有已注册的工具列表（需在 init_tools() 之后调用）"""
def get_tools() -> List[Any]:
    from tools.mcp.gaode_mcp import gaode_tools
    from tools.mcp.juhe_mcp import juhe_tools
    return base_tools + gaode_tools + juhe_tools


"""截断文本，超出部分用 ... 表示"""
def _truncate(text: str, max_len: int = 2000) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n... (已截断，总长度 {len(text)} 字符)"


"""打印待执行的工具调用信息"""
def _log_tool_calls(state: dict) -> None:
    messages = state.get("messages", [])
    if not messages:
        return
    last_msg = messages[-1]
    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        for tc in last_msg.tool_calls:
            print(f"\n{'='*60}")
            print(f"[TOOL_CALL] 调用工具: {tc['name']}")
            print(f"[TOOL_CALL] 参数: {tc.get('args', {})}")
            print(f"{'='*60}")


"""打印工具执行结果"""
def _log_tool_results(result: dict) -> None:
    messages = result.get("messages", [])
    for msg in messages:
        if isinstance(msg, ToolMessage):
            print(f"\n{'='*60}")
            print(f"[TOOL_RESULT] 工具: {msg.name}")
            print(f"[TOOL_RESULT] tool_call_id: {msg.tool_call_id}")
            content = str(msg.content)
            print(f"[TOOL_RESULT] 结果长度: {len(content)} 字符")
            print(f"[TOOL_RESULT] 内容预览:\n{_truncate(content)}")
            print(f"{'='*60}\n")


"""带日志输出的工具节点，继承 LangGraph 内置 ToolNode"""
class LoggingToolNode(ToolNode):
    
    _MAX_RESULT_LEN = 2000  # 单次工具结果最大字符数
    
    """截断 ToolMessage 内容，防止 token 超限"""
    def _truncate_messages(self, result: dict) -> dict:
        messages = result.get("messages", [])
        for msg in messages:
            if isinstance(msg, ToolMessage):
                content = str(msg.content)
                if len(content) > self._MAX_RESULT_LEN:
                    msg.content = content[:self._MAX_RESULT_LEN] + "\n... (已截断)"
        return result
    
    """异步调用工具节点"""
    async def ainvoke(self, state: dict, config=None, **kwargs):
        _log_tool_calls(state)
        result = await super().ainvoke(state, config=config, **kwargs)
        result = self._truncate_messages(result)
        _log_tool_results(result)
        return result
    
    """同步调用工具节点"""
    def invoke(self, state: dict, config=None, **kwargs):
        _log_tool_calls(state)
        result = super().invoke(state, config=config, **kwargs)
        result = self._truncate_messages(result)
        _log_tool_results(result)
        return result


"""获取当前的工具节点（需在 init_tools() 之后调用）"""
def get_tool_node() -> Any:
    if tool_node is None:
        raise RuntimeError("工具节点未初始化，请先调用 init_tools()")
    return tool_node


"""初始化所有工具（异步版本），应在图构建前调用"""
async def init_tools() -> None:
    global tool_node
    
    await init_gaode_tools()
    await init_juhe_tools()
    
    tools = get_tools()
    
    print(f"[TOOL_REGISTER] 已注册工具列表: {[tool.name for tool in tools]}")
    for tool in tools:
        desc = getattr(tool, 'description', '无描述')
        print(f"  ├─ {tool.name}: {desc[:80]}..." if len(desc) > 80 else f"  ├─ {tool.name}: {desc}")
    
    tool_node = LoggingToolNode(tools)