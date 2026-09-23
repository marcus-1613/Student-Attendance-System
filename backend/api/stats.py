"""统计接口（控制层）。

职责：收请求、调 Service、包统一响应。不写业务、不碰数据库。
对应需求文档 4.4 节的三个统计接口。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.db import get_db
from repository.stats_repo import StatsRepository
from schemas.common import ok
from service.stats_service import StatsService

router = APIRouter(prefix="/api/stats", tags=["数据统计"])


def _get_service(db: Session = Depends(get_db)) -> StatsService:
    return StatsService(StatsRepository(db))


@router.get("/summary", summary="学生信息汇总（总人数 + 班级/性别/专业分布）")
def summary(svc: StatsService = Depends(_get_service)):
    return ok(svc.summary().model_dump())


@router.get("/face-coverage", summary="脸照覆盖率（已录/未录/比例）")
def face_coverage(svc: StatsService = Depends(_get_service)):
    return ok(svc.coverage().model_dump())


@router.get("/face-count", summary="脸照数量分布（0 张 / 1 张 / 多张）")
def face_count(svc: StatsService = Depends(_get_service)):
    return ok(svc.face_count().model_dump())
