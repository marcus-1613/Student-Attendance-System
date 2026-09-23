"""脸库审计业务层（无监督 ML：人脸嵌入聚类）。

职责：从 Milvus 全量拉取向量 → 算两两余弦相似度矩阵 → 判定脏录入/重复登记
→ 层次聚类聚出可疑团伙。这是需求文档第 5 节的 ML 落地点。

判定规则（规划文档 13 节，阈值是经验值，非硬判决）：
- 规则 A · 脏录入：同一 student_id 的两张脸相似度 < DIRTY_THRESHOLD(0.6)
    含义：同一个人录的两张脸差异极大，大概率录错人了。
- 规则 B · 疑似重复登记：不同 student_id 的两张脸相似度 > DUP_THRESHOLD(0.85)
    含义：两个不同学号的人脸几乎一样，疑似一人多号/冒名录入。

算法要点：
- 先 L2 归一化 embedding，此时向量点积 == 余弦相似度，S = X @ X.T 一步算完整个矩阵。
- 相似度矩阵是 N×N 对称阵，只取上三角（i < j），避免重复计算和自己比自己的 1.0。
- 层次聚类用 sklearn AgglomerativeClustering（metric=precomputed，距离 = 1 - 相似度，
  distance_threshold = 1 - DUP_THRESHOLD），把两两高相似的聚成团伙。

性能预期：N 张脸 → O(N²)。N 到几千都毫秒~秒级；N 上万才需要改成 Milvus 近邻查询
（第一阶段不做，但要知道这个坎在哪，见规划文档 13 节）。

依赖注入：构造函数接收 vector_repo（默认 FaceVectorRepository），测试可注入假 repo
返回固定向量，无需跑真 Milvus。student_repo 用于批量补学生姓名/学号（避免 N+1）。
"""
from __future__ import annotations

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sqlalchemy.orm import Session

from repository.face_vector_repo import FaceVectorRepository
from repository.student_repo import StudentRepository
from schemas.audit import (
    AuditOut,
    ClusterItem,
    DirtyFaceItem,
    DuplicateItem,
    StudentBrief,
)

# 阈值（经验值，规划文档 13 节）
DIRTY_THRESHOLD = 0.6   # 同一人两张脸低于此值 → 疑似录错人
DUP_THRESHOLD = 0.85    # 不同人两张脸高于此值 → 疑似一人多号


class ClusterService:
    """人脸嵌入聚类审计。"""

    def __init__(
        self,
        db: Session,
        vector_repo: FaceVectorRepository | None = None,
    ):
        self.db = db
        self.vector_repo = vector_repo if vector_repo is not None else FaceVectorRepository()
        self.student_repo = StudentRepository(db)

    # ==================== 主入口 ====================

    def audit_faces(self) -> AuditOut:
        """执行完整审计，返回可疑清单。"""
        records = self.vector_repo.get_all()  # [{face_id, student_id, embedding}]
        n = len(records)

        # 空库 / 单张脸：无可比对对象，返回空结果不报错
        if n < 2:
            return AuditOut(
                total_faces=n,
                total_students=len({r["student_id"] for r in records}),
                duplicates=[],
                dirty_faces=[],
                clusters=[],
            )

        # 1. 归一化 + 相似度矩阵
        face_ids = [r["face_id"] for r in records]
        student_ids = [r["student_id"] for r in records]
        X = np.stack([r["embedding"] for r in records]).astype(np.float32)
        X = X / np.linalg.norm(X, axis=1, keepdims=True)
        S = X @ X.T  # N×N 余弦相似度矩阵

        # 2. 两条规则判定（只扫上三角 i < j）
        duplicate_pairs = []   # (i, j, sim)
        dirty_pairs = []       # (i, j, sim)
        for i in range(n):
            for j in range(i + 1, n):
                sim = float(S[i, j])
                if student_ids[i] == student_ids[j]:
                    # 同一学生两张脸差异极大 → 脏录入
                    if sim < DIRTY_THRESHOLD:
                        dirty_pairs.append((i, j, sim))
                else:
                    # 不同学生两张脸几乎一样 → 疑似重复登记
                    if sim > DUP_THRESHOLD:
                        duplicate_pairs.append((i, j, sim))

        # 3. 批量查学生信息（一次 IN 查询，避免 N+1）
        student_map = self._load_students(set(student_ids))

        # 4. 层次聚类（只对"不同学生两两高相似"的人脸，用 1 - S 作为距离）
        clusters = self._cluster(S, face_ids, student_ids, student_map)

        # 5. 组装结果
        duplicates = []
        for i, j, sim in duplicate_pairs:
            duplicates.append(
                DuplicateItem(
                    student_a=self._brief(student_map[student_ids[i]]),
                    student_b=self._brief(student_map[student_ids[j]]),
                    similarity=round(sim, 4),
                )
            )

        dirty_faces = []
        for i, j, sim in dirty_pairs:
            dirty_faces.append(
                DirtyFaceItem(
                    student=self._brief(student_map[student_ids[i]]),
                    face_a_id=face_ids[i],
                    face_b_id=face_ids[j],
                    similarity=round(sim, 4),
                )
            )

        return AuditOut(
            total_faces=n,
            total_students=len(set(student_ids)),
            duplicates=duplicates,
            dirty_faces=dirty_faces,
            clusters=clusters,
        )

    # ==================== 内部辅助 ====================

    def _load_students(self, student_ids: set[int]) -> dict[int, object]:
        """批量加载学生 ORM 对象，返回 {id: Student}。"""
        if not student_ids:
            return {}
        return self.student_repo.get_by_ids(list(student_ids))

    @staticmethod
    def _brief(student) -> StudentBrief:
        """把 Student ORM 转成 StudentBrief（审计结果里引用的简要信息）。"""
        return StudentBrief(
            id=student.id,
            name=student.name,
            student_no=student.student_no,
        )

    def _cluster(self, S, face_ids, student_ids, student_map) -> list[ClusterItem]:
        """层次聚类：把两两高相似（不同学生）的人脸聚成可疑团伙。

        用 1 - S 作为距离矩阵（距离越小越相似），distance_threshold = 1 - DUP_THRESHOLD。
        """
        # 只对"高相似"的关系聚类；若没有任何相似度超过阈值的跨学生对，直接返回空。
        # 判断方式：是否存在 i<j、student_id 不同、S[i,j] > DUP_THRESHOLD。
        has_cross_high = False
        n = S.shape[0]
        for i in range(n):
            for j in range(i + 1, n):
                if student_ids[i] != student_ids[j] and S[i, j] > DUP_THRESHOLD:
                    has_cross_high = True
                    break
            if has_cross_high:
                break
        if not has_cross_high:
            return []

        # 距离矩阵（对称），距离 = 1 - 相似度
        dist = 1.0 - S

        # 层次聚类（precomputed 距离，average linkage）
        model = AgglomerativeClustering(
            n_clusters=None,
            metric="precomputed",
            linkage="average",
            distance_threshold=1.0 - DUP_THRESHOLD,
        )
        labels = model.fit_predict(dist)

        # 按簇分组，只保留"成员数 >= 2"的簇（单点簇无意义）
        clusters: dict[int, list[dict]] = {}
        for idx, label in enumerate(labels):
            clusters.setdefault(int(label), []).append(
                {
                    "face_id": face_ids[idx],
                    "student_id": student_ids[idx],
                    "student_name": student_map[student_ids[idx]].name
                    if student_ids[idx] in student_map else None,
                    "student_no": student_map[student_ids[idx]].student_no
                    if student_ids[idx] in student_map else None,
                }
            )

        result = []
        for members in clusters.values():
            if len(members) >= 2:
                result.append(ClusterItem(faces=members))
        return result
