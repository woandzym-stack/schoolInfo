import json
import time
import uuid

from loguru import logger
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Receive, Scope, Send


class LogMiddleware:
    """
    纯 ASGI 实现的全局日志中间件
    完全规避 BaseHTTPMiddleware 的 Body 读取 Bug
    """

    def __init__(self, app: ASGIApp):
        self.app = app
        self.MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
        # 改为前缀匹配，忽略所有 AI 相关接口的 Body 日志，避免大量文本/文件数据污染日志
        # 路由前缀与 router.py 保持一致，核心网关 + 本地调试接口
        self.IGNORE_BODY_PREFIXES = (
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        # 1. 只处理 HTTP 请求
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 2. 提取或生成 Request ID 
        # 优先读取调用方传来的 x-trace-id，让日志中间件和业务层的 trace_id 完全统一
        headers = MutableHeaders(scope=scope)
        x_trace_id = headers.get("x-trace-id")
        request_id = x_trace_id if x_trace_id else str(uuid.uuid4())[:8]
        
        # 3. 预处理 Body (核心逻辑)
        # 我们需要先读取 Body，然后创建一个新的 receive 函数传给后续应用
        body_bytes = b""
        
        # 定义一个新的 receive 函数，用于后续 App 读取
        # 使用闭包来缓存已读取的 body
        receive_called = False
        original_receive = receive
        async def wrapped_receive():
            nonlocal body_bytes, receive_called
            if not receive_called:
                receive_called = True
                return {"type": "http.request", "body": body_bytes, "more_body": False}
            return await original_receive()

        path = scope.get("path", "")

        try:
            # 只有在需要记录 Body 时才去读取
            # 简单的 Content-Type 检查
            content_type = headers.get("content-type", "").lower()
            content_length = int(headers.get("content-length", 0))

            need_log_body = False
            if content_length < self.MAX_LOG_SIZE and not path.startswith(self.IGNORE_BODY_PREFIXES):
                if "application/json" in content_type or "application/x-www-form-urlencoded" in content_type:
                    need_log_body = True

            if need_log_body:
                # --- 核心：在这里彻底读取流 ---
                # 原理：循环读取直到 more_body=False
                more_body = True
                while more_body:
                    message = await receive()
                    body_bytes += message.get("body", b"")
                    more_body = message.get("more_body", False)
                
                # 此时 body_bytes 已经是完整数据了
                # 我们将 receive 替换为 wrapped_receive，后续 App 读到的就是内存里的这份
                receive = wrapped_receive

        except Exception as e:
            logger.warning(f"日志中间件读取 Body 失败: {e}")

        # 4. 记录请求日志
        # 使用 logger.contextualize 绑定 request_id
        with logger.contextualize(request_id=request_id):
            start_time = time.time()
            self._log_request(scope, headers, body_bytes)

            status_code = 500
            # 5. 定义 Send 包装器 (用于拦截响应状态码)
            async def wrapped_send(message):
                nonlocal status_code
                if message["type"] == "http.response.start":
                    status_code = message["status"]
                    # 注入 Header
                    headers = MutableHeaders(scope=message)
                    headers["X-Request-ID"] = request_id
                
                await send(message)

            # 6. 执行后续应用
            try:
                await self.app(scope, receive, wrapped_send)
            except Exception as e:
                logger.error(f"请求处理崩溃: {e}")
                raise e
            finally:
                process_time = (time.time() - start_time) * 1000
                logger.info(f"请求结束 | Status: {status_code} | Cost: {process_time:.2f}ms")

    def _log_request(self, scope, headers, body_bytes):
        try:
            path = scope.get("path")
            method = scope.get("method")
            client = scope.get("client")
            client_ip = client[0] if client else "unknown"
            query_string = scope.get("query_string", b"").decode()

            log_content = f"{method} {path} | IP: {client_ip}"
            if query_string:
                log_content += f" | Query: {query_string}"
            
            if body_bytes:
                try:
                    # 尝试解析 JSON
                    body_str = body_bytes.decode("utf-8")
                    if body_str:
                        body_json = json.loads(body_str)
                        # 脱敏：键名小写后包含敏感词即打码（子串匹配，覆盖 password/old_password/*_token 等）
                        SENSITIVE_WORDS = ("password", "api_key", "secret", "token", "authorization")
                        for field in list(body_json):
                            if any(w in field.lower() for w in SENSITIVE_WORDS):
                                body_json[field] = "******"
                            
                        log_content += f" | Body: {json.dumps(body_json, ensure_ascii=False)}"
                except:
                    # 解析失败或者是 Form，直接打印前200字符
                    log_content += f" | Body: {body_bytes.decode('utf-8')[:200]}"
            
            logger.info(f"收到请求: {log_content}")
        except Exception as e:
            logger.error(f"日志格式化错误: {e}")
