"""学生相关的 Pydantic DTO。

区分三类：
- StudentCreate：新增请求体（含学号）
- StudentUpdate：更新请求体（不含学号，学号禁止修改）
- StudentOut：查询返回体（含系统字段 id/face_status/时间戳）
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StudentCreate(BaseModel):
    """新增学生请求体。"""
    student_no: str = Field(..., min_length=1, max_length=20, description="学号（唯一）")
    name: str = Field(..., min_length=1, max_length=50, description="姓名")
    # gender 用 Literal 在 API 层做静态校验（Q-C 选项1）
    gender: Literal["男", "女"] | None = Field(default=None, description="性别")
    class_name: str | None = Field(default=None, max_length=50, description="班级")
    major: str | None = Field(default=None, max_length=50, description="专业")
    enroll_year: int | None = Field(
        default=None, ge=1900, le=2100, description="入学年份（1900-2100）"
    )
    phone: str | None = Field(default=None, max_length=20, description="联系方式")


class StudentUpdate(BaseModel):
    """更新学生请求体（不含学号——学号禁止修改，Q-B 选项1）。"""
    name: str | None = Field(default=None, min_length=1, max_length=50, description="姓名")
    gender: Literal["男", "女"] | None = Field(default=None, description="性别")
    class_name: str | None = Field(default=None, max_length=50, description="班级")
    major: str | None = Field(default=None, max_length=50, description="专业")
    enroll_year: int | None = Field(
        default=None, ge=1900, le=2100, description="入学年份（1900-2100）"
    )
    phone: str | None = Field(default=None, max_length=20, description="联系方式")


class StudentOut(BaseModel):
    """查询返回的学生对象。"""
    model_config = ConfigDict(from_attributes=True)  # 允许从 ORM 对象直接转

    id: int
    student_no: str
    name: str
    gender: str | None
    class_name: str | None
    major: str | None
    enroll_year: int | None
    phone: str | None
    face_status: int
    created_at: datetime
    updated_at: datetime


class StudentPage(BaseModel):
    """分页返回体。"""
    total: int
    page: int
    page_size: int
    items: list[StudentOut]


class ImportRowError(BaseModel):
    """批量导入时，某一行失败的错误明细。"""
    row: int = Field(description="文件中的行号（从 1 开始，含表头）")
    student_no: str = Field(default="", description="该行的学号（可能为空）")
    reason: str = Field(description="失败原因")


class ImportResult(BaseModel):
    """批量导入结果。"""
    total: int = Field(description="文件中的数据行总数（不含表头）")
    success: int = Field(description="成功写入的条数")
    failed: int = Field(description="失败的条数")
    errors: list[ImportRowError] = Field(default_factory=list, description="失败明细")
