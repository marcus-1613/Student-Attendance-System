"""识别 + 考勤相关的 Pydantic DTO（第二阶段 P12-P14）。

识别结果（RecognizeOut）：
- faces：每张脸的识别结果（bbox + 命中学生 + 相似度）。
- warning：代刷预警信息（多人同框且识别出多个不同学生时触发）。
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RecognizedFace(BaseModel):
    """一张脸的识别结果。"""

    bbox: list[float]  # [x1, y1, x2, y2]
    confidence: float  # 检测置信度
    # 命中结果：matched=True 时以下字段有效
    matched: bool
    student_id: int | None = None
    student_no: str | None = None
    name: str | None = None
    similarity: float | None = None  # 识别相似度（0~1），未命中时为 None


class AntiCheatWarning(BaseModel):
    """代刷预警。"""

    triggered: bool
    # 触发原因说明（如「画面中检测到多个不同学生，疑似代刷」）
    reason: str | None = None
    # 涉及的学号列表
    student_nos: list[str] = []


class RecognizeOut(BaseModel):
    """一帧识别 + 考勤落库的整体结果。"""

    frame_id: int  # 时间戳，前端用于对齐/去重
    face_count: int
    faces: list[RecognizedFace]
    warning: AntiCheatWarning
    elapsed_ms: float


class AttendanceOut(BaseModel):
    """考勤记录返回体。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    student_no: str | None = None
    name: str | None = None
    face_id: int
    similarity: float
    check_time: datetime


class AttendancePage(BaseModel):
    """考勤分页返回体。"""

    total: int
    page: int
    page_size: int
    items: list[AttendanceOut]
