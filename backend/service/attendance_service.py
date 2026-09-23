"""考勤业务层（第二阶段 P13）。

职责：
- record()：写一条考勤，带「同分钟去重」——同一学生在一分钟内重复打卡只记一次，
  防止实时流连续帧对同一个人反复写入。
- list_page()：分页查询考勤记录，联表带出学生姓名/学号。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from models.attendance import Attendance
from repository.attendance_repo import AttendanceRepository
from schemas.recognition import AttendanceOut


class AttendanceService:
    """考勤业务逻辑。"""

    # 去重窗口：同一学生在此时间窗内重复打卡只记一次
    DEDUP_WINDOW_SECONDS = 60

    def __init__(self, db: Session, dedup_window_seconds: int = DEDUP_WINDOW_SECONDS):
        self.db = db
        self.dedup_window = dedup_window_seconds
        self.repo = AttendanceRepository(db)

    def record(self, student_id: int, face_id: int, similarity: float) -> Attendance | None:
        """写一条考勤记录（带去重）。

        Returns:
            新写入的 Attendance；若因去重被跳过则返回 None。
        """
        now = datetime.now()
        since = now - timedelta(seconds=self.dedup_window)

        # 去重：同一学生在此窗口内已有记录 → 跳过
        if self.repo.find_recent(student_id, since) is not None:
            return None

        attendance = Attendance(
            student_id=student_id,
            face_id=face_id,
            similarity=similarity,
            check_time=now,
        )
        self.repo.create(attendance)
        self.db.commit()
        return attendance

    def list_page(self, student_id: int | None, page: int, page_size: int):
        """分页查询，返回 AttendanceOut 列表（联表带出学生姓名/学号）。"""
        total, rows = self.repo.list_page(student_id, page, page_size)
        items = [
            AttendanceOut(
                id=a.id,
                student_id=a.student_id,
                student_no=s.student_no,
                name=s.name,
                face_id=a.face_id,
                similarity=a.similarity,
                check_time=a.check_time,
            )
            for a, s in rows
        ]
        return total, items
