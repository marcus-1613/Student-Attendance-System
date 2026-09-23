"""人脸引擎封装（insightface 单例）。

职责：
1. 初始化 buffalo_l 模型（检测 + 识别 + 关键点）。
2. 模型只加载一次，进程内全局复用，避免每次请求重复加载（300MB 模型加载很慢）。
3. 对外提供清晰、简单的公共方法，供 Service 层调用。

单例实现：
    与 core/milvus.py 保持一致风格——模块级变量 + init_face_engine() / get_face_engine()。
    - 应用启动时（lifespan）调 init_face_engine() 加载一次；
    - 业务代码（service）通过 get_face_engine() 拿到同一个实例；
    - 未初始化时 get_face_engine() 返回 None，调用方需先初始化。

模型路径：
    从 core.config 的 settings.face_model_root 读取，不硬编码在业务代码里。
    insightface 的 FaceAnalysis 用 root=settings.face_model_root 定位模型，
    实际模型文件在 <face_model_root>/models/buffalo_l/ 下。

注意：
    本文件只做「引擎封装」，不含任何业务规则（阈值、错误码、三存储落库都不在这里）。
    业务层（service/face_service.py）后续会决定怎么使用这里的返回值。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from core.config import settings

# insightface 的 import 放在函数里延迟加载，理由：
# 1. 模块被 import 时不应触发 onnxruntime 等重依赖的加载；
# 2. 未装模型/依赖时，import face_engine 本身不应该报错，便于单元测试注入假引擎。
_insightface_app = None  # 类型: insightface.app.FaceAnalysis


@dataclass
class FaceResult:
    """extract() 的返回结构：一张图上检测出的「最大人脸」的提取结果。

    设计说明（对齐需求文档"只取最大脸"）：
    - detected=False 表示「没检测到人脸」，此时 bbox/embedding/landmark 均为空。
    - total_faces 表示图上实际检测到的人脸数量（含被舍弃的较小脸），
      便于业务层反馈"检测到 N 张脸，只取最大的一张"。
    """

    detected: bool
    # 人脸框 [x1, y1, x2, y2]，detected=False 时为 None
    bbox: np.ndarray | None = None
    # 512 维人脸特征向量（float32），detected=False 时为 None
    embedding: np.ndarray | None = None
    # 5 点关键点 (5, 2)，detected=False 时为 None
    landmark: np.ndarray | None = None
    # 检测到的人脸总数（>=1 时 detected 才为 True）
    total_faces: int = 0
    # 检测得分（det_10g 的置信度），可选，供后续质量把关用
    det_score: float = 0.0


@dataclass
class FaceInstance:
    """extract_all() 中单张人脸的提取结果（用于实时识别的多脸场景）。

    与 FaceResult 的区别：FaceResult 只保留面积最大的那张脸（录入场景），
    FaceInstance 是 extract_all 返回的「每一张脸」，供识别阶段逐个比对身份。
    """

    bbox: np.ndarray  # [x1, y1, x2, y2]
    embedding: np.ndarray  # 512 维 float32
    det_score: float


class FaceEngine:
    """insightface buffalo_l 的人脸检测 + 特征提取封装。"""

    def __init__(self, model_root: str):
        """初始化引擎。

        Args:
            model_root: 模型根目录（如 D:\\...\\Student\\buffalo），
                        insightface 会在 <model_root>/models/buffalo_l/ 下找模型。
        """
        # insightface 是重依赖，延迟到真正初始化时 import
        from insightface.app import FaceAnalysis

        self._app = FaceAnalysis(name="buffalo_l", root=model_root)
        # 本机无 GPU，用 CPU（ctx_id=-1）。det_size 保持 insightface 默认的 640x640。
        self._app.prepare(ctx_id=-1, det_size=(640, 640))

    def extract(self, image: np.ndarray) -> FaceResult:
        """对一张图片做检测 + 特征提取，返回最大人脸的结果。

        Args:
            image: BGR 格式的图片（numpy.ndarray，uint8，HxWx3），
                   与 opencv 的 cv2.imread 输出、以及后续 Service 解码约定一致。

        Returns:
            FaceResult：无论是否检测到人脸都返回该结构，不抛异常。
            - 无人脸：detected=False，其余字段为空。
            - 有多张脸：只返回面积最大的那张，total_faces 记录总数。
        """
        # insightface 的 get() 返回 list[Face]，每个 Face 含 bbox / embedding / kps / det_score
        faces = self._app.get(image)

        if not faces:
            return FaceResult(detected=False, total_faces=0)

        # 只取面积最大的脸（需求文档：只取最大脸）
        def _area(f) -> float:
            x1, y1, x2, y2 = f.bbox
            return max(0.0, (x2 - x1) * (y2 - y1))

        best = max(faces, key=_area)

        return FaceResult(
            detected=True,
            bbox=np.asarray(best.bbox, dtype=np.float32),
            # insightface 的 embedding 默认是 L2 归一化后的 512 维向量
            embedding=np.asarray(best.embedding, dtype=np.float32),
            landmark=np.asarray(best.kps, dtype=np.float32) if best.kps is not None else None,
            total_faces=len(faces),
            det_score=float(getattr(best, "det_score", 0.0)),
        )

    def extract_all(self, image: np.ndarray) -> list[FaceInstance]:
        """对一张图片做检测 + 特征提取，返回「所有」人脸（不挑最大脸）。

        用于第二阶段实时识别：一帧画面可能有多张脸，需要逐张比对身份。

        Args:
            image: BGR 格式的图片（numpy.ndarray，uint8，HxWx3）。

        Returns:
            list[FaceInstance]，按人脸面积从大到小排序。无人脸时返回空列表。
        """
        faces = self._app.get(image)
        if not faces:
            return []

        instances = [
            FaceInstance(
                bbox=np.asarray(f.bbox, dtype=np.float32),
                embedding=np.asarray(f.embedding, dtype=np.float32),
                det_score=float(getattr(f, "det_score", 0.0)),
            )
            for f in faces
        ]

        # 按面积从大到小排，让主脸（最可能是被考勤的人）排在前面
        def _area(inst: FaceInstance) -> float:
            x1, y1, x2, y2 = inst.bbox
            return max(0.0, (x2 - x1) * (y2 - y1))

        instances.sort(key=_area, reverse=True)
        return instances


# ---------- 单例管理 ----------
_engine: FaceEngine | None = None


def init_face_engine() -> FaceEngine:
    """初始化并缓存人脸引擎。在 lifespan 启动事件里调用一次。"""
    global _engine
    if _engine is None:
        _engine = FaceEngine(model_root=settings.face_model_root)
    return _engine


def get_face_engine() -> FaceEngine | None:
    """获取人脸引擎单例；未初始化时返回 None。"""
    return _engine
