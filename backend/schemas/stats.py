"""统计相关的 Pydantic DTO。

对应需求文档 4.4 节的三个统计接口：
- GET /api/stats/summary       总人数 + 班级/性别/专业分布
- GET /api/stats/face-coverage 覆盖率（已录/未录/比例）
- GET /api/stats/face-count    脸照数量分布（0 张 / 1 张 / 多张）

这里只定义 API 返回的数据结构，不涉及任何数据库操作。
"""
from pydantic import BaseModel


class DistributionItem(BaseModel):
    """分布聚合的一项，例如 {name: "男", count: 6}。"""
    name: str
    count: int


class SummaryOut(BaseModel):
    """学生信息汇总。"""
    total_students: int
    by_class: list[DistributionItem]
    by_gender: list[DistributionItem]
    by_major: list[DistributionItem]


class CoverageOut(BaseModel):
    """脸照覆盖率。"""
    total_students: int
    enrolled: int
    not_enrolled: int
    coverage_rate: float  # 0.0 ~ 1.0，空库时为 0


class FaceCountOut(BaseModel):
    """脸照数量分布。"""
    zero_face: int
    one_face: int
    multiple_faces: int
