"""
聚合数据（Juhe）MCP 工具 - 通过 MCP Server 获取航班查询功能

设计原则：
1. 使用 MultiServerMCPClient 连接聚合数据 MCP Server
2. 添加连接异常捕获和降级逻辑，避免单点失败
3. 与高德 MCP 工具统一管理，共享同一工具节点
"""
import os
from typing import List, Any
from dotenv import load_dotenv

try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
    MCP_AVAILABLE = True
except ImportError as e:
    print(f"[WARN] MCP 依赖未安装或版本不兼容，跳过聚合 MCP 初始化: {e}")
    MCP_AVAILABLE = False

load_dotenv()

# 聚合 MCP Server 地址（token 已嵌入 URL）
JUHE_BASE_URL = os.getenv("JUHE_BASE_URL", "")
# 备用：如需独立管理 token，可通过 JUHE_API_KEY 拼接
JUHE_API_KEY = os.getenv("JUHE_API_KEY", "")


async def get_juhe_tools() -> List[Any]:
    """获取聚合数据 MCP 工具列表，连接失败时返回空列表"""
    if not MCP_AVAILABLE:
        print("[INFO] MCP 依赖未安装，跳过聚合 MCP 工具")
        return []

    if not JUHE_BASE_URL:
        print("[WARN] 未配置 JUHE_BASE_URL，跳过聚合 MCP 工具")
        return []

    try:
        juhe_config = {
            "juhe-flight": {
                "url": JUHE_BASE_URL,
                "transport": "sse"
            }
        }
        print(f"[TOOL_REGISTER] 正在连接聚合 MCP Server: {JUHE_BASE_URL[:80]}...")

        client = MultiServerMCPClient(juhe_config)
        tools = await client.get_tools()

        print(f"[TOOL_REGISTER] 聚合 MCP 工具加载成功: {[tool.name for tool in tools]}")
        for tool in tools:
            desc = getattr(tool, 'description', '无描述')
            print(f"  ├─ {tool.name}: {desc[:100]}")
        return tools

    except Exception as e:
        print(f"[WARN] 聚合 MCP 连接失败，跳过: {e}")
        return []


# 全局工具列表（初始为空，在运行时通过 init_juhe_tools 加载）
juhe_tools: List[Any] = []


async def init_juhe_tools() -> None:
    """初始化聚合数据 MCP 工具（异步版本），应在图构建前调用"""
    global juhe_tools
    juhe_tools = await get_juhe_tools()
