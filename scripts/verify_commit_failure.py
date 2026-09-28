"""验证（修复后）：commit 失败时，客户端实际收到的响应状态码。

直接调用 ASGI 应用并收集响应消息：
- 修复前：teardown commit 失败 → 响应消息是 200（成功响应已发出），随后应用抛错
- 修复后：Service 层 commit 失败 → 异常处理器产出 500 响应消息，客户端不会收到 200
"""
import asyncio
from typing import Any, Dict, List

from sqlmodel.ext.asyncio.session import AsyncSession

from app.main import app

_real_commit = AsyncSession.commit


async def _boom_commit(self):  # type: ignore[no-untyped-def]
    raise RuntimeError("simulated commit failure")


async def call_asgi(method: str, path: str, json_body: Dict[str, Any]) -> tuple[int, bytes, bool]:
    """裸调 ASGI 应用，返回（响应状态码， 响应体， 应用是否抛错）。"""
    body = __import__("json").dumps(json_body).encode()
    messages: List[Dict[str, Any]] = []

    async def receive() -> Dict[str, Any]:
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message: Dict[str, Any]) -> None:
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"content-type", b"application/json"),
            (b"x-forwarded-for", b"10.99.0.2"),
        ],
        "client": ("127.0.0.1", 12345),
        "server": ("test", 80),
        "app": app,
    }

    app_raised = False
    try:
        await app(scope, receive, send)
    except Exception:
        app_raised = True  # starlette 处理完异常后会重抛供服务器记录，属预期

    status = 0
    response_body = b""
    for m in messages:
        if m["type"] == "http.response.start" and status == 0:
            status = m["status"]
        elif m["type"] == "http.response.body":
            response_body += m.get("body", b"")
    return status, response_body, app_raised


async def main() -> None:
    AsyncSession.commit = _boom_commit  # type: ignore[method-assign]
    try:
        status, body, raised = await call_asgi(
            "POST",
            "/api/v1/auth/register",
            {"username": "committest01", "password": "Passw0rd123", "email": "c@t.com"},
        )
        print(f"commit-failure → HTTP {status} | body={body.decode('utf-8', 'ignore')} | app_raised={raised}")
        assert status == 500, f"客户端收到 {status} 而非 500，问题仍在"
        print("结论：commit 失败时客户端收到 500，不会误报成功")
    finally:
        AsyncSession.commit = _real_commit  # type: ignore[method-assign]
        status, body, _ = await call_asgi("GET", "/api/v1/auth/me", {})
        print(f"restored → /auth/me HTTP {status}（预期 401）")


asyncio.run(main())
