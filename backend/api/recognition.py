"""人脸识别 + 考勤接口（控制层，第二阶段 P12-P14）。

接口：
- POST /api/recognize            一帧图片 → 识别所有脸 + 落考勤 + 代刷预警
- GET  /api/attendances          分页查询考勤记录（可按 student_id 过滤）
"""
import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from core.db import get_db
from core.exceptions import BusinessError
from schemas.common import ok
from schemas.recognition import AttendancePage, RecognizeOut
from service.attendance_service import AttendanceService
from service.recognition_service import RecognitionService

router = APIRouter(tags=["人脸识别与考勤"])


def _decode_image(content: bytes) -> np.ndarray:
    """把上传的图片字节解码成 BGR ndarray；失败抛 BusinessError。"""
    if not content:
        raise BusinessError(4000, "图片无效：文件内容为空")
    arr = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        raise BusinessError(4000, "图片格式无法解析（仅支持 jpg/png 等常见图片）")
    return arr


@router.post("/api/recognize", summary="识别一帧并打卡")
def recognize(
    file: UploadFile = File(..., description="实时帧图片（jpg）"),
    db: Session = Depends(get_db),
):
    content = file.file.read()
    image = _decode_image(content)
    svc = RecognitionService(db)
    result = svc.recognize(image)
    return ok(result.model_dump())


@router.get("/api/attendances", summary="分页查询考勤记录")
def list_attendances(
    student_id: int | None = Query(None, description="按学生过滤（可选）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    svc = AttendanceService(db)
    total, items = svc.list_page(student_id, page, page_size)
    return ok(
        AttendancePage(
            total=total,
            page=page,
            page_size=page_size,
            items=[i.model_dump() for i in items],
        ).model_dump()
    )
