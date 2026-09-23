"""公告业务层。

职责：业务规则 + 事务边界 + 编排 Repository + 触发广播。
不写 SQL，不读 HTTP 请求对象。

关键顺序（需求文档 12 节明确要求）：
- 创建公告时，先落库（commit 成功），再调 ws_manager 广播。
  顺序不能反：如果先广播再落库，落库失败时客户端已经收到了一条
  不存在的公告，造成"幽灵通知"。
"""
from sqlalchemy.orm import Session

from core.exceptions import BusinessError
from core.ws_manager import manager
from models.notice import Notice
from repository.notice_repo import NoticeRepository
from schemas.notice import NoticeCreate, NoticeOut, NoticeUpdate


class NoticeService:
    """公告业务逻辑。"""

    def __init__(self, db: Session):
        self.db = db
        self.repo = NoticeRepository(db)

    async def create_notice(self, payload: NoticeCreate) -> Notice:
        """发布公告：落库成功后广播给所有在线客户端。"""
        notice = Notice(
            title=payload.title,
            content=payload.content,
            publisher=payload.publisher,
        )
        self.repo.create(notice)
        self.db.commit()  # 必须先落库成功
        self.db.refresh(notice)  # 重新加载，拿到数据库生成的时间戳

        # 落库成功后广播（异步）
        await manager.broadcast(
            {"type": "notice", "data": NoticeOut.model_validate(notice).model_dump(mode="json")}
        )
        return notice

    def get_notice(self, notice_id: int) -> Notice:
        notice = self.repo.get_by_id(notice_id)
        if notice is None:
            raise BusinessError(4104, "公告不存在")
        return notice

    def list_notices(self, page: int, page_size: int) -> dict:
        total, items = self.repo.list_page(page, page_size)
        return {"total": total, "page": page, "page_size": page_size, "items": items}

    def update_notice(self, notice_id: int, payload: NoticeUpdate) -> Notice:
        notice = self.get_notice(notice_id)

        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(notice, field, value)

        self.db.commit()
        self.db.refresh(notice)
        return notice

    def delete_notice(self, notice_id: int) -> None:
        notice = self.get_notice(notice_id)
        self.repo.delete(notice)
        self.db.commit()
