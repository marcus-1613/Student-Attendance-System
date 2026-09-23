"""
枚举接口。

GET /api/enums 返回班级/专业列表，供前端表单下拉框使用。
数据来自 core.enums 的内存缓存（启动时已从 CSV 加载）。
"""
from fastapi import APIRouter

from core import enums
from schemas.common import ok

router = APIRouter(prefix="/api", tags=["枚举"])


@router.get("/enums")
def get_enums():
    """返回 {classes: [...], majors: [...]}。"""
    return ok({
        "classes": enums.get_classes(),
        "majors": enums.get_majors(),
    })
