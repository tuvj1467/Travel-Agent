import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch

load_dotenv()

# QIANFANG配置
QIANFANG_API_KEY = os.getenv("QIANFANG_API_KEY")
QIANFANG_BASE_URL = os.getenv("QIANFANG_BASE_URL")
QIANFANG_MODEL = os.getenv("QIANFANG_MODEL")
QIANFANG_EMBEDDING_MODEL = os.getenv("QIANFANG_EMBEDDING_MODEL") or QIANFANG_MODEL

# ZHIPU配置
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
ZHIPU_BASE_URL = os.getenv("ZHIPU_BASE_URL")
ZHIPU_MODEL = os.getenv("ZHIPU_MODEL")
ZHIPU_EMBEDDING_MODEL = os.getenv("ZHIPU_EMBEDDING_MODEL") or ZHIPU_MODEL

# 初始化LLM
llm = ChatOpenAI(
    model=QIANFANG_MODEL,
    base_url=QIANFANG_BASE_URL,
    api_key=QIANFANG_API_KEY,
    temperature=0.4
)

