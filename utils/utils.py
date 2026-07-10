


def retry_on_rate_limit(max_retries=3, delay=2):
    """重试装饰器，处理速率限制错误"""
    import time
    def decorator(func):
        def wrapper(*args, **kwargs):
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
        return wrapper
    return decorator
