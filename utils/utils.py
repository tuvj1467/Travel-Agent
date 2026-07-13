


"""
通用工具函数 - 旅行规划系统的公共工具

包含：
1. retry_on_rate_limit：重试装饰器，处理速率限制
2. PydanticListOutputParser：自定义列表解析器，支持解析 JSON 数组为 Pydantic 模型列表
"""


def retry_on_rate_limit(max_retries=3, delay=2):
    """重试装饰器，处理速率限制错误
    
    自动识别同步/异步函数：
    - 同步函数：使用 time.sleep 重试
    - 异步函数：使用 asyncio.sleep 重试
    """
    import time
    import asyncio
    import functools
    
    def decorator(func):
        # 判断被装饰的函数是否为异步函数
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                for attempt in range(max_retries):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        if "429" in str(e) or "速率限制" in str(e) or "1302" in str(e):
                            if attempt < max_retries - 1:
                                wait_time = delay * (attempt + 1)
                                print(f"[WARN] 遇到速率限制，等待 {wait_time} 秒后重试... (尝试 {attempt + 1}/{max_retries})")
                                await asyncio.sleep(wait_time)
                                continue
                        raise
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                for attempt in range(max_retries):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        if "429" in str(e) or "速率限制" in str(e) or "1302" in str(e):
                            if attempt < max_retries - 1:
                                wait_time = delay * (attempt + 1)
                                print(f"[WARN] 遇到速率限制，等待 {wait_time} 秒后重试... (尝试 {attempt + 1}/{max_retries})")
                                time.sleep(wait_time)
                                continue
                        raise
            return sync_wrapper
    return decorator


class PydanticListOutputParser:
    """自定义列表解析器 - 将 LLM 输出的 JSON 数组直接解析为 Pydantic 模型列表
    
    使用示例：
        parser = PydanticListOutputParser(SimplePOI)
        result = parser.parse('[{"name": "湄洲岛"}]')  # → List[SimplePOI]
    """
    
    def __init__(self, pydantic_type):
        """
        Args:
            pydantic_type: Pydantic 模型类型，如 SimplePOI、ScenicDetail
        """
        from typing import List
        from pydantic import TypeAdapter
        
        self._pydantic_type = pydantic_type
        self._adapter = TypeAdapter(List[pydantic_type])
    
    def parse(self, text: str) -> list:
        """将 JSON 字符串解析为 Pydantic 模型列表
        
        Args:
            text: LLM 输出的 JSON 字符串，支持数组或单个对象
            
        Returns:
            List[pydantic_type]: Pydantic 模型列表
        """
        import json
        
        # 先解析为 JSON
        json_obj = json.loads(text)
        
        # 如果是单个对象，包装为列表
        if isinstance(json_obj, dict):
            json_obj = [json_obj]
        
        # 使用 TypeAdapter 解析为 Pydantic 列表
        return self._adapter.validate_python(json_obj)
    
    def get_format_instructions(self) -> str:
        """返回格式说明，告诉 LLM 输出 JSON 数组格式
        
        Returns:
            str: 格式说明文本
        """
        return f"请直接输出 JSON 数组格式，无需额外包装。例如：\n[{{\"name\": \"景点名称\", \"poi_id\": \"xxx\"}}]"
