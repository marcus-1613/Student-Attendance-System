"""脸库审计接口（控制层）。

职责：收请求、调 Service、包统一响应。不写业务、不碰数据库。
对应需求文档 10.1 节 + 规划文档 13 节的 /api/audit/duplicates 接口。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.db import get_db
from schemas.common import ok
from service.cluster_service import ClusterService

router = APIRouter(prefix="/api/audit", tags=["脸库审计"])


def _get_service(db: Session = Depends(get_db)) -> ClusterService:
    return ClusterService(db)


@router.get("/duplicates", summary="脸库审计（疑似重复登记 + 脏录入 + 可疑团伙）")
def audit_duplicates(svc: ClusterService = Depends(_get_service)):
    result = svc.audit_faces()
    return ok(result.model_dump())
