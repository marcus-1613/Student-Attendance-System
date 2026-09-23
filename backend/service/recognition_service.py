"""人脸识别 + 考勤业务层（第二阶段 P12-P14）。

职责（编排层，不写 SQL、不碰 HTTP、不做推理）：
1. 对一帧图片提取所有脸的 embedding（FaceEngine.extract_all）。
2. 逐张脸在 Milvus 底库里检索最相似的身份（FaceVectorRepository.search）。
3. 按相似度阈值判定是否命中（threshold，默认 0.5）。
4. 命中则写入考勤（AttendanceService，含同分钟去重）。
5. 多人同框且识别出多个不同学生 → 触发代刷预警。

依赖注入：
- db: Session
- 识别阈值、去重窗口等通过构造参数传入（便于测试注入不同值）。
"""
from __future__ import annotations

import time

import numpy as np
from sqlalchemy.orm import Session

from core.exceptions import BusinessError
from core.face_engine import get_face_engine
from repository.face_vector_repo import FaceVectorRepository
from repository.student_repo import StudentRepository
from schemas.recognition import (
    AntiCheatWarning,
    RecognizedFace,
    RecognizeOut,
)
from service.attendance_service import AttendanceService


class RecognitionService:
    """人脸识别 + 考勤编排。"""

    # 识别阈值：相似度低于此值视为「陌生人」，不落考勤
    DEFAULT_THRESHOLD = 0.5
    # 检索 top_k：从底库拿最相似的候选
    DEFAULT_TOP_K = 1

    def __init__(
        self,
        db: Session,
        threshold: float = DEFAULT_THRESHOLD,
        attendance_service: AttendanceService | None = None,
    ):
        self.db = db
        self.threshold = threshold
        self.student_repo = StudentRepository(db)
        self.vector_repo = FaceVectorRepository()
        self.attendance = attendance_service or AttendanceService(db)

    def recognize(self, image: np.ndarray) -> RecognizeOut:
        """对一帧图片做识别 + 考勤落库。

        Args:
            image: BGR 格式图片（np.ndarray，uint8，HxWx3）。

        Returns:
            RecognizeOut（每张脸的识别结果 + 代刷预警 + 耗时）。

        Raises:
            BusinessError(5000): 引擎未初始化。
        """
        t0 = time.time()

        engine = get_face_engine()
        if engine is None:
            raise BusinessError(5000, "人脸引擎尚未初始化，请先调用 init_face_engine()")

        # 1. 提取所有脸
        instances = engine.extract_all(image)
        faces: list[RecognizedFace] = []
        hit_students: dict[int, str] = {}  # student_id -> student_no，用于代刷判定

        # 2. 逐脸识别
        for inst in instances:
            face_result = self._recognize_one(inst)
            faces.append(face_result)
            if face_result.matched:
                hit_students[face_result.student_id] = face_result.student_no

        # 3. 代刷预警：多人同框且识别出 >=2 个不同学生
        warning = self._detect_anti_cheat(hit_students)

        elapsed = (time.time() - t0) * 1000
        return RecognizeOut(
            frame_id=int(time.time() * 1000),
            face_count=len(faces),
            faces=faces,
            warning=warning,
            elapsed_ms=round(elapsed, 1),
        )

    def _recognize_one(self, inst) -> RecognizedFace:
        """识别单张脸：Milvus 检索 → 阈值判定 → 命中则写考勤。"""
        bbox = [float(v) for v in inst.bbox]
        confidence = float(inst.det_score)

        # 检索最相似底库人脸
        hits = self.vector_repo.search(inst.embedding, top_k=self.DEFAULT_TOP_K)

        if not hits:
            # 底库为空或检索无结果 → 陌生人
            return RecognizedFace(
                bbox=bbox, confidence=confidence, matched=False
            )

        top = hits[0]
        similarity = float(top["similarity"])

        if similarity < self.threshold:
            # 相似度不足 → 陌生人，不落考勤
            return RecognizedFace(
                bbox=bbox, confidence=confidence, matched=False, similarity=similarity
            )

        # 命中：查学生信息
        student = self.student_repo.get_by_id(int(top["student_id"]))
        if student is None:
            # 底库向量指向了已删除的学生（脏数据），当作陌生人处理
            return RecognizedFace(
                bbox=bbox, confidence=confidence, matched=False, similarity=similarity
            )

        # 写考勤（同分钟去重，重复打卡静默忽略）
        self.attendance.record(
            student_id=student.id,
            face_id=int(top["face_id"]),
            similarity=similarity,
        )

        return RecognizedFace(
            bbox=bbox,
            confidence=confidence,
            matched=True,
            student_id=student.id,
            student_no=student.student_no,
            name=student.name,
            similarity=similarity,
        )

    def _detect_anti_cheat(self, hit_students: dict[int, str]) -> AntiCheatWarning:
        """代刷预警：同一帧里识别出多个不同学生。"""
        if len(hit_students) >= 2:
            student_nos = list(hit_students.values())
            return AntiCheatWarning(
                triggered=True,
                reason=f"画面中识别出 {len(student_nos)} 个不同学生，疑似代刷",
                student_nos=student_nos,
            )
        return AntiCheatWarning(triggered=False)
