"""公告相关的 Pydantic DTO。

对应需求文档 4.5 节公告管理接口：
- NoticeCreate / NoticeUpdate：新增/更新请求体（title/content/publisher）
- NoticeOut：查询返回体（含系统字段 id/created_at）
- NoticePage：分页返回体
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NoticeCreate(BaseModel):
    """发布公告请求体。"""
    title: str = Field(..., min_length=1, max_length=100, description="标题")
    content: str | None = Field(default=None, description="内容")
    publisher: str | None = Field(default=None, max_length=50, description="发布人")


class NoticeUpdate(BaseModel):
    """更新公告请求体（全部可选，只更新传入字段）。"""
    title: str | None = Field(default=None, min_length=1, max_length=100, description="标题")
    content: str | None = Field(default=None, description="内容")
    publisher: str | None = Field(default=None, max_length=50, description="发布人")


class NoticeOut(BaseModel):
    """查询返回的公告对象。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str | None
    publisher: str | None
    created_at: datetime


class NoticePage(BaseModel):
    """分页返回体。"""
    total: int
    page: int
    page_size: int
    items: list[NoticeOut]
