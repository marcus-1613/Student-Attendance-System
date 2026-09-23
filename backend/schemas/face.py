"""人脸相关的 Pydantic DTO。

当前阶段（P6）：
- FaceOut：脸照元数据查询返回体。
- FaceEnrollOut：人脸上传成功的返回体（含检测信息）。
上传失败统一走 BusinessError（code 非0），不在这里定义"失败"结构。
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FaceOut(BaseModel):
    """人脸元数据的查询返回体。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    face_id: int
    student_id: int
    image_path: str
    created_at: datetime


class FaceEnrollOut(BaseModel):
    """人脸上传成功后的返回体。

    detected 恒为 True（失败场景由 BusinessError 表达），
    total_faces 表示图上实际检测到的人脸数（含被舍弃的较小脸），
    便于前端反馈"检测到 N 张脸，只取了最大的一张"。
    """
    detected: bool
    face_id: int
    student_id: int
    image_path: str
    total_faces: int
