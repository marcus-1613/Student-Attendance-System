"""实时人脸检测接口（P11 控制层）。

职责：收图片、解码、调 DetectionService、包统一响应。不写业务、不碰数据库。

接口：
- POST /api/detect   上传一帧图片，返回检测到的人脸框 + 置信度。

说明：
    P11 第一版用 HTTP 逐帧 POST（前端抽帧 5-8 FPS），把「摄像头→检测→画框」
    闭环先跑通。帧传输是否升级为 WebSocket 帧流，属于后续性能优化阶段
    （P11-7）再评估，本阶段不引入，避免过度设计。
"""
import cv2
import numpy as np
from fastapi import APIRouter, File, UploadFile

from core.exceptions import BusinessError
from schemas.common import ok
from schemas.detection import DetectionOut
from service.detection_service import DetectionService

router = APIRouter(tags=["实时检测"])


def _decode_image(content: bytes) -> np.ndarray:
    """把上传的图片字节解码成 BGR ndarray；失败抛 BusinessError。

    与 api/faces.py 里的 _decode_image 逻辑一致（空内容 / 无法解析两种情况）。
    """
    if not content:
        raise BusinessError(4000, "图片无效：文件内容为空")
    arr = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        raise BusinessError(4000, "图片格式无法解析（仅支持 jpg/png 等常见图片）")
    return arr


@router.post("/api/detect", summary="检测一帧图片中的人脸")
def detect_faces(
    file: UploadFile = File(..., description="视频帧图片（jpg/png）"),
):
    content = file.file.read()
    image = _decode_image(content)

    svc = DetectionService()
    result = svc.detect(image)

    return ok(DetectionOut(
        face_count=result.face_count,
        faces=result.faces,
        elapsed_ms=result.elapsed_ms,
    ).model_dump())
