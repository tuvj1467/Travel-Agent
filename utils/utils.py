


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
