"""实时人脸检测（P11）相关的 Pydantic DTO。

- DetectionBox：单张人脸的检测框 + 置信度。
- DetectionOut：一次检测的返回体（人脸数量 + 所有人脸 + 耗时）。
"""
from pydantic import BaseModel


class DetectionBox(BaseModel):
    """单张人脸的检测结果。

    bbox 为原图像素坐标 [x1, y1, x2, y2]（float），前端据此绘制。
    """

    bbox: list[float]
    confidence: float


class DetectionOut(BaseModel):
    """一次检测的返回体。

    - face_count: 检测到的人脸数量（0 表示无人脸，是正常结果不是错误）。
    - faces: 所有人脸的框 + 置信度（按置信度降序）。
    - elapsed_ms: 推理耗时（毫秒），调试用，便于前端展示性能。
    """

    face_count: int
    faces: list[DetectionBox]
    elapsed_ms: float
