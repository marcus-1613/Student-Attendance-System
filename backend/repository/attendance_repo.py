"""考勤数据层（纯 CRUD + 查询，不含业务规则）。"""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.attendance import Attendance
from models.student import Student


class AttendanceRepository:
    """考勤记录表的读写。"""

    def __init__(self, db: Session):
        self.db = db

    def create(self, attendance: Attendance) -> Attendance:
        """新增一条考勤记录。flush 拿自增 id，不 commit（事务由 service 收口）。"""
        self.db.add(attendance)
        self.db.flush()
        return attendance

    def find_recent(
        self,
        student_id: int,
        since: datetime,
    ) -> Attendance | None:
        """查该学生在 since 之后的最近一条考勤记录（用于去重）。"""
        stmt = (
            select(Attendance)
            .where(
                Attendance.student_id == student_id,
                Attendance.check_time >= since,
            )
            .order_by(Attendance.check_time.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def list_page(
        self,
        student_id: int | None,
        page: int,
        page_size: int,
    ):
        """分页查询考勤记录，返回 (total, items)。items 已联表带出学生姓名/学号。

        student_id 为空时查全部；否则只查该学生。
        """
        stmt = (
            select(Attendance, Student)
            .join(Student, Attendance.student_id == Student.id)
        )
        if student_id is not None:
            stmt = stmt.where(Attendance.student_id == student_id)

        count_stmt = select(func.count()).select_from(Attendance)
        if student_id is not None:
            count_stmt = count_stmt.where(Attendance.student_id == student_id)
        total = self.db.scalar(count_stmt) or 0

        rows = self.db.execute(
            stmt.order_by(Attendance.check_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()

        # 组装成 (attendance, student) 元组列表
        return total, [(a, s) for a, s in rows]
