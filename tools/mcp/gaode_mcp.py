"""
高德地图 MCP 工具 - 通过 MCP Server 获取地图相关功能

设计原则：
1. 使用 MultiServerMCPClient 连接高德 MCP Server
2. 添加连接异常捕获和降级逻辑，避免单点失败
3. 工具列表集中管理，便于扩展
"""
import os
from typing import List, Any, Optional
from dotenv import load_dotenv

# 尝试导入 MCP 相关依赖，失败时不报错（降级处理）
try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
    MCP_AVAILABLE = True
except ImportError as e:
    print(f"[WARN] MCP 依赖未安装或版本不兼容，跳过高德 MCP 初始化: {e}")
    MCP_AVAILABLE = False

load_dotenv()

# 高德 MCP Server 需要 AMAP_MAPS_API_KEY 环境变量
AMAP_MAPS_API_KEY = os.getenv("AMAP_MAPS_API_KEY") or os.getenv("GAODE_API_KEY")


"""获取高德地图 MCP 工具列表，连接失败时返回空列表"""
async def get_gaode_tools() -> List[Any]:
    if not MCP_AVAILABLE:
        print("[INFO] MCP 依赖未安装，跳过高德 MCP 工具")
        return []
    
    if not AMAP_MAPS_API_KEY:
        print("[WARN] 未配置 AMAP_MAPS_API_KEY，跳过高德 MCP 工具")
        return []
    
    try:
        gaode_config = {
            "amap-maps": {
                "url": f"https://mcp.amap.com/mcp?key={AMAP_MAPS_API_KEY}",
                "transport": "streamable_http"
            }
        }
        
        client = MultiServerMCPClient(gaode_config)
        tools = await client.get_tools()
        
        print(f"[TOOL_REGISTER] 高德 MCP 工具加载成功: {[tool.name for tool in tools]}")
        return tools
    
    except Exception as e:
        print(f"[WARN] 高德 MCP 连接失败，跳过: {e}")
        return []


# 全局工具列表（初始为空，在运行时通过 init_gaode_tools 加载）
gaode_tools: List[Any] = []


"""初始化高德 MCP 工具（异步版本），应在图构建前调用"""
async def init_gaode_tools() -> None:
    global gaode_tools
    gaode_tools = await get_gaode_tools()