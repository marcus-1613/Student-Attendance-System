"""
业务异常 + 全局异常处理器。

设计要点：
1. 业务错误（如"学号已存在"）用 BusinessError 抛出，带一个业务错误码。
2. 全局处理器把它转成统一响应 {"code":..., "message":..., "data":null}，
   这样 api 层不需要写满 try/except，代码干净。
3. 对"未预期的异常"，也兜底转成统一响应（code=5000），而不是让
   FastAPI 返回默认的 {"detail": ...}——保证前端永远拿到同一结构。
4. RequestValidationError 单独处理：这是 FastAPI 参数校验失败时抛的，
   默认返回格式和我们的信封不一致，这里统一掉。
"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from schemas.common import fail


class BusinessError(Exception):
    """业务异常。code 为业务错误码，message 给用户看的提示。"""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    """在 main.py 里调用，把各类异常挂到 app 上。"""

    @app.exception_handler(BusinessError)
    async def business_error_handler(request: Request, exc: BusinessError):
        return JSONResponse(
            status_code=200,  # 业务错误用 200 + 非0 code 表达，前端统一看 code
            content=fail(exc.code, exc.message),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        # 404 等 HTTP 错误也统一成信封结构，避免前端拿到 {"detail": ...}
        return JSONResponse(
            status_code=exc.status_code,
            content=fail(exc.status_code, str(exc.detail)),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        # 提取第一条校验错误，拼成易读的提示
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(x) for x in first.get("loc", []) if x != "body")
        msg = first.get("msg", "参数校验失败")
        detail = f"{loc}: {msg}" if loc else msg
        return JSONResponse(
            status_code=200,
            content=fail(4000, f"参数校验失败：{detail}"),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        # 兜底：未预期异常。生产环境应记日志，这里先简单返回。
        return JSONResponse(
            status_code=200,
            content=fail(5000, f"服务器内部错误：{exc}"),
        )
