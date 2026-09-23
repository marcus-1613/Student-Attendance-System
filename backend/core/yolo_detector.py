"""人脸检测器封装（SCRFD / det_10g，P11 实时检测专用）。

职责：
1. 独立加载 buffalo_l 模型包里的 det_10g.onnx（SCRFD 检测器），
   只做「人脸检测框 + 置信度」，不做识别/关键点（那是 FaceEngine 的事）。
2. 模型只加载一次，进程内全局复用（与 face_engine.py 同一套单例模式）。
3. 对外提供 detect(image) -> list[Detection]，返回所有人脸的 bbox + 置信度。

为什么单独封装，而不是复用 FaceEngine.extract()？
- FaceEngine.extract() 走 insightface 的 FaceAnalysis 完整流水线，
  会同时跑「检测 + 关键点 + 512D 识别」，且只返回「面积最大的一张脸」。
- 实时检测只需要「所有脸的框」，跑完整流水线会白白浪费 CPU 算识别向量，
  且丢掉多脸信息。所以这里用 SCRFD 单独加载，只做检测。

为什么用 SCRFD 而不是单独下载 YOLO？
- det_10g.onnx 就是 SCRFD（InsightFace 默认检测器），是人脸检测 SOTA 轻量模型，
  已随 buffalo_l 就位，零新增依赖。需求里的"YOLO 实时检测"用 SCRFD 满足即可。

模型加载方式：
    直接 SCRFD(model_file=路径) 加载 onnx，prepare(ctx_id=-1) 用 CPU 推理。
    复用 insightface 内置的 SCRFD 类（含 anchor 解码 + NMS 后处理），
    不手写任何后处理，避免重复造轮子。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core.config import settings

# SCRFD 的 import 延迟到真正初始化时（与 face_engine.py 保持一致的理由：
# 模块被 import 时不应触发 onnxruntime 重依赖加载）。
_detector = None


@dataclass
class Detection:
    """单张人脸的检测结果。

    - bbox: [x1, y1, x2, y2]，原图像素坐标（float）。
    - confidence: 检测置信度（0~1）。
    """

    bbox: np.ndarray
    confidence: float

    def to_bbox_list(self) -> list[float]:
        """转成 [x1, y1, x2, y2] 的 Python list（供 JSON 序列化）。"""
        return [float(v) for v in self.bbox]


class FaceDetector:
    """SCRFD 人脸检测器封装（只检测，不识别）。"""

    def __init__(self, model_file: str):
        """初始化检测器。

        Args:
            model_file: det_10g.onnx 的绝对路径。
        """
        # 延迟 import，避免模块加载时就触发 onnxruntime
        from insightface.model_zoo.scrfd import SCRFD

        self._det = SCRFD(model_file=model_file)
        self._det.prepare(
            ctx_id=-1,
            input_size=settings.face_detector_input_size,
            det_thresh=settings.face_detector_thresh,
            nms_thresh=settings.face_detector_nms_thresh,
        )

    def detect(self, image: np.ndarray) -> list[Detection]:
        """检测一张图里的所有人脸，返回 bbox + 置信度。

        Args:
            image: BGR 格式图片（np.ndarray，uint8，HxWx3）。

        Returns:
            list[Detection]，按置信度降序排列。无人脸返回 []，不抛异常。
        """
        bboxes, _kpss = self._det.detect(image, input_size=settings.face_detector_input_size)
        if bboxes is None or len(bboxes) == 0:
            return []

        out = []
        for b in bboxes:
            out.append(
                Detection(
                    bbox=np.asarray(b[:4], dtype=np.float32),
                    confidence=float(b[4]),
                )
            )
        return out


# ---------- 单例管理 ----------
_detector: FaceDetector | None = None


def init_face_detector() -> FaceDetector:
    """初始化并缓存检测器。在 lifespan 启动事件里调用一次。"""
    global _detector
    if _detector is None:
        _detector = FaceDetector(model_file=settings.face_detector_model)
    return _detector


def get_face_detector() -> FaceDetector | None:
    """获取检测器单例；未初始化时返回 None。"""
    return _detector
