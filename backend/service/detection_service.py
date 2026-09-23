"""实时人脸检测业务层（P11）。

职责：编排「图片 → 检测器 → 检测结果」，返回结构化数据。

原则（与 face_service.py 一致）：
- 只做编排 + 组装，不碰 HTTP、不写 SQL。
- 检测器（core/yolo_detector.py）只做推理，本层负责把结果转成 DTO。

本阶段（P11）只做「检测」，不做识别/检索/考勤——那些是 P12 之后的事。
但这里把 Service 独立出来，就是为了将来 P12 在这个编排层继续加
「识别 + Milvus 检索」时，不用改 api 层。
"""
from __future__ import annotations

import time

import numpy as np

from core.exceptions import BusinessError
from core.yolo_detector import get_face_detector
from schemas.detection import DetectionBox, DetectionOut


class DetectionService:
    """人脸检测编排层。"""

    def detect(self, image: np.ndarray) -> DetectionOut:
        """检测一张图里的所有人脸。

        Args:
            image: BGR 格式图片（np.ndarray，uint8，HxWx3）。

        Returns:
            DetectionOut（face_count + faces + elapsed_ms）。

        Raises:
            BusinessError(5000): 检测器未初始化。
        """
        detector = get_face_detector()
        if detector is None:
            raise BusinessError(5000, "检测器尚未初始化，请先调用 init_face_detector()")

        t0 = time.time()
        detections = detector.detect(image)
        elapsed_ms = (time.time() - t0) * 1000

        faces = [
            DetectionBox(
                bbox=d.to_bbox_list(),
                confidence=d.confidence,
            )
            for d in detections
        ]

        return DetectionOut(
            face_count=len(faces),
            faces=faces,
            elapsed_ms=round(elapsed_ms, 1),
        )
