"""人脸向量存储（Milvus）数据层。

原则：
- 只负责 512 维人脸向量的存取与检索，不含任何业务规则。
- 复用 core/milvus.py 的客户端（get_milvus_client），不复制初始化逻辑。
- 不判断"是不是同一个人"——那是上层 service 的事；这里只按相似度检索。

字段（与需求文档 9.3 节一致）：
- face_id: INT64 主键
- student_id: INT64
- embedding: FLOAT_VECTOR(512)
- created_at: INT64（Unix 秒级时间戳）
"""
import time

import numpy as np

from core.milvus import FACE_COLLECTION, get_milvus_client


class FaceVectorRepository:
    """人脸向量的写入 / 检索 / 删除。"""

    def __init__(self):
        # 不保存客户端实例，每次通过 get_milvus_client() 拿当前单例，
        # 避免持有过期/已关闭的引用。
        self.collection = FACE_COLLECTION

    def _client(self):
        client = get_milvus_client()
        if client is None:
            raise RuntimeError("Milvus 客户端尚未初始化，请先调用 init_milvus()")
        return client

    def insert(self, face_id: int, student_id: int, embedding: np.ndarray) -> None:
        """插入一条人脸向量。

        Args:
            face_id: 桥接 SQLite faces.face_id 的唯一 ID。
            student_id: 所属学生 id。
            embedding: 512 维 float32 向量（应已 L2 归一化，COSINE 度量下效果最佳）。
        """
        client = self._client()
        # 规整为 512 维 float32
        vec = np.asarray(embedding, dtype=np.float32).reshape(-1)
        if vec.shape[0] != 512:
            raise ValueError(f"embedding 维度应为 512，实际 {vec.shape[0]}")

        data = {
            "face_id": int(face_id),
            "student_id": int(student_id),
            "embedding": vec.tolist(),
            "created_at": int(time.time()),
        }
        client.insert(collection_name=self.collection, data=[data])

    def search(self, embedding: np.ndarray, top_k: int = 5, student_id: int | None = None):
        """按余弦相似度检索最相似的人脸。

        Args:
            embedding: 512 维查询向量。
            top_k: 返回最相似的条数。
            student_id: 可选，限定只在某个学生的人脸里搜（用于"该学生已有几张脸"）。

        Returns:
            list[dict]，每项形如：
                {"face_id": int, "student_id": int, "similarity": float}
            按相似度降序。空结果返回 []。
        """
        client = self._client()
        vec = np.asarray(embedding, dtype=np.float32).reshape(-1)
        if vec.shape[0] != 512:
            raise ValueError(f"embedding 维度应为 512，实际 {vec.shape[0]}")

        # 可选过滤：只在该学生范围内检索
        filter_expr = None
        if student_id is not None:
            filter_expr = f"student_id == {int(student_id)}"

        # 确保 collection 处于 loaded 状态：审计 get_all() 用完会 release，
        # 且 Milvus 重启/空闲后 collection 也可能回到 released，search 前必须 load。
        # load_collection 是幂等的（已 loaded 时无副作用）。
        client.load_collection(self.collection)

        results = client.search(
            collection_name=self.collection,
            data=[vec.tolist()],
            limit=top_k,
            filter=filter_expr,
            output_fields=["student_id"],
        )

        # results 是 list[list[Hit]]，第一层对应输入向量的条数（这里只有 1 条）
        hits = results[0] if results else []
        out = []
        for h in hits:
            # pymilvus 3.x Hit 结构：主键字段（face_id）在顶层，distance 是相似度，
            # 其余标量字段在 h["entity"] 里。
            out.append(
                {
                    "face_id": int(h["face_id"]),
                    "student_id": int(h["entity"]["student_id"]),
                    "similarity": float(h["distance"]),  # COSINE 度量下 distance 即余弦相似度
                }
            )
        return out

    def get_all(self) -> list[dict]:
        """全量拉取所有向量（用于脸库审计的相似度矩阵计算）。

        注意：pymilvus 的 query 要求 collection 处于 loaded 状态，
        否则报 code=101 "released"。这里 load → query → release，
        保证每次调用独立可用（审计接口是低频操作，不必常驻 load）。

        Returns:
            list[dict]，每项形如：
                {"face_id": int, "student_id": int, "embedding": np.ndarray(512)}
            按 face_id 升序。空库返回 []。
        """
        client = self._client()
        client.load_collection(self.collection)
        try:
            rows = client.query(
                collection_name=self.collection,
                filter="",
                output_fields=["face_id", "student_id", "embedding"],
            )
        finally:
            # 无论成败都释放，避免长期占用内存中的 loaded 集合
            client.release_collection(self.collection)

        out = []
        for r in rows:
            out.append(
                {
                    "face_id": int(r["face_id"]),
                    "student_id": int(r["student_id"]),
                    "embedding": np.asarray(r["embedding"], dtype=np.float32),
                }
            )
        return out

    def delete(self, face_id: int) -> None:
        """删除单条向量（按主键 face_id）。"""
        client = self._client()
        client.delete(collection_name=self.collection, filter=f"face_id == {int(face_id)}")

    def delete_by_student_id(self, student_id: int) -> None:
        """删除某学生的全部向量。"""
        client = self._client()
        client.delete(
            collection_name=self.collection,
            filter=f"student_id == {int(student_id)}",
        )
