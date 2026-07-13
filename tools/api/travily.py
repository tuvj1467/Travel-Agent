from langchain_tavily import TavilySearch
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 初始化搜索工具
tavily_search = TavilySearch(max_results=3)