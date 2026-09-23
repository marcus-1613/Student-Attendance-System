"""人脸录入接口（控制层）。

职责：收请求、解码图片、调 FaceService、包统一响应。不写业务、不碰数据库。

接口（对应需求文档 10.1 节「人脸录入」）：
- POST   /api/students/{student_id}/faces   上传脸照（multipart 图片）
- GET    /api/students/{student_id}/faces   查询学生脸照列表
- DELETE /api/faces/{face_id}               删除单张脸照（三处级联）
"""
import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from core.db import get_db
from core.exceptions import BusinessError
from schemas.common import ok
from schemas.face import FaceEnrollOut, FaceOut
from service.face_service import FaceService

router = APIRouter(tags=["人脸录入"])


def _get_service(db: Session = Depends(get_db)) -> FaceService:
    return FaceService(db)


def _decode_image(content: bytes) -> np.ndarray:
    """把上传的图片字节解码成 BGR ndarray；失败抛 BusinessError。"""
    if not content:
        raise BusinessError(4000, "图片无效：文件内容为空")
    # cv2.imdecode 返回 None 表示无法解析（如传了个 txt）
    arr = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        raise BusinessError(4000, "图片格式无法解析（仅支持 jpg/png 等常见图片）")
    return arr


@router.post("/api/students/{student_id}/faces", summary="上传脸照")
def upload_face(
    student_id: int,
    file: UploadFile = File(..., description="脸照图片（jpg/png 等）"),
    svc: FaceService = Depends(_get_service),
):
    content = file.file.read()
    image = _decode_image(content)
    result = svc.create_face(student_id, image)
    face = result.face
    return ok(
        FaceEnrollOut(
            detected=True,
            face_id=face.face_id,
            student_id=face.student_id,
            image_path=face.image_path,
            total_faces=result.total_faces,
        ).model_dump()
    )


@router.get("/api/students/{student_id}/faces", summary="查询学生脸照列表")
def list_faces(student_id: int, svc: FaceService = Depends(_get_service)):
    faces = svc.list_faces(student_id)
    return ok([FaceOut.model_validate(f).model_dump() for f in faces])


@router.delete("/api/faces/{face_id}", summary="删除单张脸照")
def delete_face(face_id: int, svc: FaceService = Depends(_get_service)):
    svc.delete_face(face_id)
    return ok(message="删除成功")
