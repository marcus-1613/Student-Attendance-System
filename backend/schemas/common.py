"""
统一响应信封 + 帮助函数。

需求文档约定所有响应格式为：
    {"code": 0, "message": "ok", "data": {...}}
    code == 0 表示成功，非 0 表示失败。

设计要点：
1. 不用中间件"魔法"去包响应——那会让响应在接口层变得不可见，
   排查问题时得先搞清楚中间件做了什么。改用显式的 ok() / fail()
   帮助函数，接口里一眼能看懂返回了什么。
2. Pydantic 模型 ApiResponse 用于 Swagger 文档里展示响应结构；
   实际运行时直接返回普通 dict 即可（FastAPI 会序列化它）。
"""
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一响应信封（泛型，用于 Swagger 文档标注）。"""
    code: int = 0
    message: str = "ok"
    data: T | None = None


def ok(data: Any = None, message: str = "ok") -> dict:
    """成功响应。"""
    return {"code": 0, "message": message, "data": data}


def fail(code: int, message: str, data: Any = None) -> dict:
    """失败响应（业务错误码）。"""
    return {"code": code, "message": message, "data": data}
