"""统计数据层：只用 SQL 聚合查询，不含任何业务规则。

原则（与其它 repo 一致）：
- 只负责"怎么查"，不判断任何业务口径。
- 用 SQL 的 GROUP BY 聚合，而不是把数据拉到内存再用 Pandas 算。
  这是数据库的本职工作，一行 SQL 就能完成。
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.face import Face
from models.student import Student


class StatsRepository:
    """统计聚合查询。"""

    def __init__(self, db: Session):
        self.db = db

    def count_students(self) -> int:
        return self.db.scalar(select(func.count()).select_from(Student)) or 0

    def count_enrolled(self) -> int:
        """已录脸学生数（face_status == 1）。"""
        stmt = (
            select(func.count())
            .select_from(Student)
            .where(Student.face_status == 1)
        )
        return self.db.scalar(stmt) or 0

    def group_by_column(self, column) -> list[tuple[str, int]]:
        """按某列分组计数，返回 [(值, 数量), ...]；值为 NULL 的归入「未填写」。

        column 是 ORM 列对象（如 Student.class_name），不是字符串列名。
        """
        stmt = (
            select(column, func.count())
            .select_from(Student)
            .group_by(column)
        )
        rows = self.db.execute(stmt).all()
        result = []
        for value, count in rows:
            # NULL 值在界面上统一显示为「未填写」
            result.append((value if value is not None else "未填写", count))
        return result

    def count_students_by_face_count(self) -> dict[str, int]:
        """按每个学生拥有的脸照数量，统计 0 张 / 1 张 / 多张 三档学生数。

        用 LEFT JOIN：没有脸照的学生也保留（face 计数为 0）。
        """
        stmt = (
            select(
                Student.id,
                func.count(Face.id).label("face_cnt"),
            )
            .select_from(Student)
            .outerjoin(Face, Face.student_id == Student.id)
            .group_by(Student.id)
        )
        rows = self.db.execute(stmt).all()

        zero = one = multiple = 0
        for _, face_cnt in rows:
            if face_cnt == 0:
                zero += 1
            elif face_cnt == 1:
                one += 1
            else:
                multiple += 1
        return {"zero_face": zero, "one_face": one, "multiple_faces": multiple}
