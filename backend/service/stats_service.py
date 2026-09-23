"""统计业务层：组装统计结果，处理除零等边界。

原则：
- 统计口径（覆盖率先用 face_status、脸照数分布用 faces 表聚合）在这里体现。
- 除零保护：空库时 coverage_rate 必须返回 0，而不是抛异常。
"""
from schemas.stats import CoverageOut, DistributionItem, FaceCountOut, SummaryOut
from repository.stats_repo import StatsRepository
from models.student import Student


class StatsService:
    """学生信息统计。"""

    def __init__(self, stats_repo: StatsRepository):
        self.repo = stats_repo

    def summary(self) -> SummaryOut:
        total = self.repo.count_students()
        by_class = [DistributionItem(name=n, count=c) for n, c in self.repo.group_by_column(Student.class_name)]
        by_gender = [DistributionItem(name=n, count=c) for n, c in self.repo.group_by_column(Student.gender)]
        by_major = [DistributionItem(name=n, count=c) for n, c in self.repo.group_by_column(Student.major)]
        return SummaryOut(
            total_students=total,
            by_class=by_class,
            by_gender=by_gender,
            by_major=by_major,
        )

    def coverage(self) -> CoverageOut:
        total = self.repo.count_students()
        enrolled = self.repo.count_enrolled()
        not_enrolled = total - enrolled
        # 除零保护：空库时覆盖率为 0
        rate = (enrolled / total) if total > 0 else 0.0
        return CoverageOut(
            total_students=total,
            enrolled=enrolled,
            not_enrolled=not_enrolled,
            coverage_rate=round(rate, 4),
        )

    def face_count(self) -> FaceCountOut:
        d = self.repo.count_students_by_face_count()
        return FaceCountOut(**d)
