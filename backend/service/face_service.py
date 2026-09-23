"""人脸录入业务层（编排层）。

职责：把「人脸录入」这条链路串起来，协调各数据/引擎模块：
    StudentRepository  → 查学生是否存在
    FaceEngine         → 检测人脸 + 提取 512 维特征
    FaceStorage        → 保存人脸图片文件
    FaceVectorRepository → 写入 Milvus 向量
    FaceRepository     → 写入 SQLite 元数据

原则（与 student_service.py 一致）：
- 只做业务规则 + 编排 + 事务边界，不写 SQL、不碰 HTTP。
- Repository 只负责自己的存储；FaceEngine 只做推理；FaceStorage 只管文件。
- 本阶段只实现「正常成功路径」+ 最基本错误，不做三存储回滚补偿。

TODO(P6 后续阶段)：
    三存储一致性尚未处理。若出现「图片保存成功 → Milvus 成功 → SQLite 失败」
    会留下脏数据（孤儿图片 / 孤儿向量）。后续阶段统一设计失败补偿/回滚机制，
    本阶段先不引入复杂事务系统。
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

import cv2
import numpy as np
from sqlalchemy.orm import Session

from core.exceptions import BusinessError
from core.face_engine import get_face_engine
from core.face_storage import FaceStorage
from models.face import Face
from models.student import Student
from repository.face_repo import FaceRepository
from repository.face_vector_repo import FaceVectorRepository
from repository.student_repo import StudentRepository

# 负占位计数器：给 Face.face_id 一个「单进程内保证唯一」的临时负值，
# flush 拿到自增 id 后立刻回填为正式 id（见 _new_face 内注释）。
# 用负数可以规避与真实正 id 冲突，也避免 UNIQUE 约束在两次录入间相撞。
_placeholder_seq = 0


def _next_placeholder() -> int:
    """返回一个单调递减的负占位值，单进程内唯一。"""
    global _placeholder_seq
    _placeholder_seq -= 1
    return _placeholder_seq


@dataclass
class FaceEnrollResult:
    """create_face 的返回结构：录入结果 + 检测元信息。

    - face：新创建的 Face ORM 记录（face_id 已与 id 一致）。
    - total_faces：图上实际检测到的人脸数（含被舍弃的较小脸），供前端反馈。
    """

    face: Face
    total_faces: int


class FaceService:
    """人脸录入业务逻辑。"""

    def __init__(
        self,
        db: Session,
        storage: FaceStorage | None = None,
    ):
        self.db = db
        self.student_repo = StudentRepository(db)
        self.face_repo = FaceRepository(db)
        # 向量仓库无状态，每次拿当前 Milvus 单例客户端
        self.vector_repo = FaceVectorRepository()
        # 文件存储可注入（测试用临时目录），默认用 config 的 face_storage_dir
        self.storage = storage if storage is not None else FaceStorage()

    # ==================== 人脸录入 ====================

    def create_face(self, student_id: int, image: np.ndarray) -> FaceEnrollResult:
        """录入一张人脸：检测 + 保存图片 + 写 Milvus + 写 SQLite。

        Args:
            student_id: 学生主键 id（students.id）。
            image: BGR 格式图片（np.ndarray，uint8，HxWx3）。

        Returns:
            FaceEnrollResult（含新 Face 记录 + 检测到的人脸总数）。

        Raises:
            BusinessError:
                - 4004 学生不存在
                - 4000 图片无效 / 未检测到人脸
        """
        # 1. 学生必须存在
        student = self._get_student_or_raise(student_id)

        # 2. 图片有效性检查（None / 非 ndarray / 空图）
        if image is None or not isinstance(image, np.ndarray):
            raise BusinessError(4000, "图片无效：传入的不是有效图片数据")
        if image.size == 0:
            raise BusinessError(4000, "图片无效：图片数据为空")

        # 3. 人脸检测 + 特征提取
        engine = get_face_engine()
        if engine is None:
            raise BusinessError(5000, "人脸引擎尚未初始化，请先调用 init_face_engine()")

        result = engine.extract(image)

        # 4. 未检测到人脸 → 明确业务错误
        if not result.detected:
            raise BusinessError(4000, "未检测到人脸")

        # 4.5 跨学号查重（防「一人多号」作弊）：
        # 在全库检索与这张脸最相似的底库向量，若相似度达到阈值、且属于「其他学号」，
        # 说明同一个人的脸已经被登记在别的学号下，直接拒绝录入。
        # 必须在任何落库动作（建 Face 行/存图/写 Milvus）之前执行，
        # 否则会先产生孤儿数据再抛错。
        self._check_duplicate_across_students(student_id, result.embedding)

        # 5. 生成唯一 face_id：先落 SQLite 拿自增 id，再用 id 作为 face_id 回填
        face = self._create_face_row(student_id)

        # 6. 保存人脸图片（用 face_id 命名文件名，便于追溯）
        filename = self._image_filename(face.face_id)
        image_bytes = self._encode_image(image)
        relative_path = self.storage.save(student_id, filename, image_bytes)

        # 7. 写 Milvus 向量（512D embedding）
        self.vector_repo.insert(
            face_id=face.face_id,
            student_id=student_id,
            embedding=result.embedding,
        )

        # 8. 回填 image_path + 维护 face_status + 提交 SQLite 元数据
        face.image_path = relative_path
        # 冗余字段：录入了脸照，标记该学生"已录脸"
        student.face_status = 1
        self.db.commit()
        self.db.refresh(face)
        return FaceEnrollResult(face=face, total_faces=result.total_faces)

    # ==================== 查询 / 删除 ====================

    def list_faces(self, student_id: int) -> list[Face]:
        """查询某学生的全部脸照（按录入时间倒序）。"""
        # 先确认学生存在（复用统一的学生不存在错误）
        self._get_student_or_raise(student_id)
        return self.face_repo.list_by_student_id(student_id)

    def delete_face(self, face_id: int) -> None:
        """删除单张脸照（三处级联：Milvus 向量 + 磁盘文件 + SQLite 元数据）。

        顺序遵循「先删外部附件，再删权威记录」：
        1. 删 Milvus 向量（按 face_id）
        2. 删磁盘图片文件（按 image_path）
        3. 删 SQLite faces 行（权威）
        4. 若该学生已无脸照，face_status 回 0
        """
        face = self.face_repo.get_by_face_id(face_id)
        if face is None:
            raise BusinessError(4004, f"脸照（face_id={face_id}）不存在")

        student_id = face.student_id

        # 1. 删外部附件（Milvus 向量 + 磁盘文件）
        self.vector_repo.delete(face_id=face_id)
        self.storage.delete_by_relative_path(face.image_path)

        # 2. 删 SQLite 权威记录
        self.face_repo.delete(face)

        # 3. 维护 face_status：删完后若该学生已无脸照，回 0
        self._sync_face_status(student_id)

        self.db.commit()

    def delete_faces_by_student(self, student_id: int) -> None:
        """删除某学生的全部脸照（三处级联），供「删学生」时复用。

        返回前不 commit，事务边界由调用方（StudentService.delete_student）收口。
        """
        faces = self.face_repo.list_by_student_id(student_id)
        if not faces:
            return

        # 1. 删 Milvus 向量（按 student_id 批量删）
        self.vector_repo.delete_by_student_id(student_id)

        # 2. 删磁盘文件 + 整个学号目录
        for f in faces:
            self.storage.delete_by_relative_path(f.image_path)
        self.storage.delete_student_dir(student_id)

        # 3. 删 SQLite faces 行（注意：这里用 delete_by_student_id，flush 不 commit）
        self.face_repo.delete_by_student_id(student_id)

    # ==================== 内部辅助 ====================

    def _get_student_or_raise(self, student_id: int) -> Student:
        """查学生，不存在抛 BusinessError(4004)。"""
        student = self.student_repo.get_by_id(student_id)
        if student is None:
            raise BusinessError(4004, f"学生（id={student_id}）不存在")
        return student

    def _check_duplicate_across_students(self, student_id: int, embedding: np.ndarray) -> None:
        """跨学号查重：同一张脸是否已登记在「其他学号」名下。

        防作弊背景：把同一个人的脸登记到两个学号下，这个人往镜头前一站
        两个学号都能打卡。这里在录入入口就拦截，从源头堵死「一人多号」。

        判定：全库检索 top-1，若相似度 >= face_duplicate_threshold 且
        属于别的 student_id，抛 BusinessError(4002) 拒绝录入。

        Raises:
            BusinessError(4002)：疑似与某学号重复登记。
        """
        hits = self.vector_repo.search(embedding, top_k=1)
        if not hits:
            return  # 底库为空，无重复可能

        top = hits[0]
        # 属于同一个学生本人（该学生已有别的脸照）→ 不算跨学号重复，放行
        if int(top["student_id"]) == int(student_id):
            return

        similarity = float(top["similarity"])
        threshold = self._duplicate_threshold()
        if similarity >= threshold:
            # 命中别的学号：查出对方信息，给用户一个可操作的提示
            other = self.student_repo.get_by_id(int(top["student_id"]))
            other_label = f"{other.name}（{other.student_no}）" if other else f"学号 {top['student_id']}"
            raise BusinessError(
                4002,
                f"该人脸疑似已登记在 {other_label} 名下（相似度 {similarity:.0%}），"
                f"请勿将同一人的脸重复登记到多个学号",
            )

    @staticmethod
    def _duplicate_threshold() -> float:
        """查重阈值（从配置读取，便于测试/环境覆盖）。"""
        from core.config import settings
        return float(settings.face_duplicate_threshold)

    def _sync_face_status(self, student_id: int) -> None:
        """根据 faces 表实际记录，回写 students.face_status 冗余字段。

        口径：有脸照 → 1，无脸照 → 0。
        """
        remaining = self.face_repo.list_by_student_id(student_id)
        student = self._get_student_or_raise(student_id)
        student.face_status = 1 if remaining else 0

    # ==================== 内部辅助 ====================

    def _create_face_row(self, student_id: int) -> Face:
        """创建 Face 记录并分配自增 id，同时把 face_id 设为与 id 一致。

        设计说明（face_id 一致性）：
        - SQLite faces.id 是自增主键，只有 INSERT（flush）后才有值。
        - faces.face_id 是 nullable=False 且 unique 的桥接字段，用于和 Milvus 对齐。
        - 第一阶段约定：face_id == id。

        实现：先给 face_id 一个「负占位值」（单进程内唯一，不与任何正 id 冲突，
        也满足 UNIQUE 约束），flush 拿到自增 id 后，立刻把 face.face_id 回填为 id。
        commit 时 SQLAlchemy 会把回填后的 face_id 一并写入，最终 face_id == id。
        """
        face = Face(
            face_id=_next_placeholder(),
            student_id=student_id,
            # image_path 先占位，保存图片后再回填真实相对路径
            image_path="",
        )
        face = self.face_repo.create(face)  # flush → 此刻 face.id 已分配
        face.face_id = face.id  # 回填，保证 face_id == id
        return face

    @staticmethod
    def _image_filename(face_id: int) -> str:
        """生成图片文件名：<face_id>_<uuid前8位>.jpg，保证唯一且可追溯。"""
        return f"{face_id}_{uuid.uuid4().hex[:8]}.jpg"

    @staticmethod
    def _encode_image(image: np.ndarray) -> bytes:
        """把 BGR ndarray 编码为 JPEG 字节流。"""
        ok, buf = cv2.imencode(".jpg", image)
        if not ok:
            raise BusinessError(4000, "图片编码失败：无法将图片转为 JPEG")
        return buf.tobytes()
