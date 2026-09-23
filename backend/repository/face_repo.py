"""人脸元数据数据层（纯 CRUD，不含任何业务判断）。

原则（与 student_repo.py 一致）：
- 只负责 SQLite 中 faces 表的增删改查。
- 不调用 FaceEngine、不调用 Milvus、不删磁盘文件。
- 不包含业务规则（如"学号是否重复"、"是不是同一个人"都不在这里）。
"""
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from models.face import Face


class FaceRepository:
    """faces 表的增删改查。"""

    def __init__(self, db: Session):
        self.db = db

    def create(self, face: Face) -> Face:
        """新增。flush 以获取自增 id（及由业务层写入的 face_id），不 commit。"""
        self.db.add(face)
        self.db.flush()
        return face

    def get_by_id(self, face_id: int) -> Face | None:
        """按主键 id 查询。"""
        return self.db.get(Face, face_id)

    def get_by_face_id(self, face_id: int) -> Face | None:
        """按桥接字段 face_id 查询（Milvus 那边用 face_id 关联）。"""
        stmt = select(Face).where(Face.face_id == face_id)
        return self.db.scalar(stmt)

    def list_by_student_id(self, student_id: int) -> list[Face]:
        """查询某个学生的全部脸照记录，按录入时间倒序（新的在前）。"""
        stmt = (
            select(Face)
            .where(Face.student_id == student_id)
            .order_by(Face.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def delete(self, face: Face) -> None:
        """删除单条记录（flush 不 commit，事务由上层收口）。"""
        self.db.delete(face)
        self.db.flush()

    def delete_by_student_id(self, student_id: int) -> int:
        """删除某学生的全部脸照记录，返回删除条数。

        注意：这里只删 SQLite 元数据；Milvus 向量和磁盘图片需上层另行处理。
        """
        stmt = delete(Face).where(Face.student_id == student_id)
        result = self.db.execute(stmt)
        self.db.flush()
        return result.rowcount or 0
