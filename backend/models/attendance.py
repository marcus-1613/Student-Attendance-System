"""考勤记录 ORM 实体（第二阶段 P13）。

设计说明：
- 一次「识别成功」产生一条考勤记录（check_time 为打卡时刻）。
- student_id 关联学生；face_id 记录命中的底库脸照（用于追溯「用哪张脸打的卡」）。
- similarity 记录识别时的余弦相似度，便于后续审计「临界命中」。
- 同一天同一学生允许多次打卡（迟到/补卡等场景），去重逻辑在 service 层控制
  （默认同一学生同一分钟内只记一次，防止实时流连续帧重复写入）。
"""
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class Attendance(Base):
    __tablename__ = "attendances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 被识别的学生
    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 命中的底库脸照 id（追溯依据）
    face_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # 识别相似度（余弦相似度，0~1）
    similarity: Mapped[float] = mapped_column(Float, nullable=False)
    # 打卡时间（识别成功的时刻）
    check_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), index=True
    )
    # 记录创建时间（冗余，与 check_time 基本一致，保留以备后续审计）
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<Attendance id={self.id} student_id={self.student_id} "
            f"face_id={self.face_id} sim={self.similarity:.3f}>"
        )
