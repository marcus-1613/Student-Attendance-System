"""人脸元数据 ORM 实体（对应需求文档 9.2 节 faces 表）。

设计说明：
- 一个 Student 对应多个 Face（1:N），通过 student_id 外键关联。
- face_id 是桥接 Milvus 的全局 ID（第一阶段数值上等于本表自增 id），
  由 SQLite 权威分配；Milvus 里的向量用同一个 face_id 关联。
- image_path 存的是图片在文件系统中的「相对路径」，例如 /faces/202301001/xxx.jpg。
- 外键 ON DELETE CASCADE：删学生时，该学生的 faces 行由数据库自动级联删除，
  （Milvus 向量和磁盘图片需要上层业务手动清理，不在这里处理）。
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


class Face(Base):
    __tablename__ = "faces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 桥接 Milvus 的全局脸照 ID（第一阶段 = id）
    face_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    # 所属学生（外键，删学生级联删脸照元数据）
    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 脸照图片在文件系统中的相对路径（如 /202301001/xxx.jpg，相对 face_storage_dir）
    image_path: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # 可选的关系定义：便于将来通过 face.student 拿到所属学生（当前阶段不强制使用）
    student = relationship("Student", back_populates=None)

    def __repr__(self) -> str:
        return f"<Face id={self.id} face_id={self.face_id} student_id={self.student_id}>"
