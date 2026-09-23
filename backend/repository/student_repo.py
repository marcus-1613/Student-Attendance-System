"""学生数据层（纯 CRUD，不含任何业务判断）。

原则：这里只负责"怎么查、怎么存"，不判断"学号是否重复"这类业务规则。
"""
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from models.student import Student


class StudentRepository:
    """学生表的增删改查。"""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, student_id: int) -> Student | None:
        return self.db.get(Student, student_id)

    def get_by_student_no(self, student_no: str) -> Student | None:
        stmt = select(Student).where(Student.student_no == student_no)
        return self.db.scalar(stmt)

    def get_by_ids(self, student_ids: list[int]) -> dict[int, Student]:
        """批量查询学生（一次 IN 查询），返回 {id: Student}。

        用于审计等需要给一批 id 补学生信息的场景，避免 N+1 查询。
        """
        if not student_ids:
            return {}
        stmt = select(Student).where(Student.id.in_(student_ids))
        rows = self.db.scalars(stmt).all()
        return {s.id: s for s in rows}

    def create(self, student: Student) -> Student:
        """新增。flush 以获取自增 id，但不 commit（事务由 Service 收口）。"""
        self.db.add(student)
        self.db.flush()
        return student

    def list_page(self, keyword: str | None, page: int, page_size: int):
        """分页查询，返回 (total, items)。

        keyword 模糊匹配 姓名 / 学号 / 班级 三者之一。
        """
        stmt = select(Student)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    Student.name.like(like),
                    Student.student_no.like(like),
                    Student.class_name.like(like),
                )
            )

        # 总数：用 func.count 统计，复用同一个 where 条件
        count_stmt = select(func.count()).select_from(Student)
        if stmt.whereclause is not None:
            count_stmt = count_stmt.where(stmt.whereclause)
        total = self.db.scalar(count_stmt) or 0

        items = self.db.scalars(
            stmt.order_by(Student.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()

        return total, list(items)

    def delete(self, student: Student) -> None:
        self.db.delete(student)
        self.db.flush()
