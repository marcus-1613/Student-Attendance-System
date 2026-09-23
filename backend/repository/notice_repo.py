"""公告数据层（纯 CRUD，不含任何业务判断）。"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.notice import Notice


class NoticeRepository:
    """公告表的增删改查。"""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, notice_id: int) -> Notice | None:
        return self.db.get(Notice, notice_id)

    def create(self, notice: Notice) -> Notice:
        """新增。flush 以获取自增 id，但不 commit（事务由 Service 收口）。"""
        self.db.add(notice)
        self.db.flush()
        return notice

    def list_page(self, page: int, page_size: int):
        """分页查询，按发布时间倒序（最新在前），返回 (total, items)。"""
        total = self.db.scalar(select(func.count()).select_from(Notice)) or 0
        items = self.db.scalars(
            select(Notice)
            .order_by(Notice.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return total, list(items)

    def delete(self, notice: Notice) -> None:
        self.db.delete(notice)
        self.db.flush()
