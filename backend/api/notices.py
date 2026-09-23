"""公告管理接口（控制层）+ WebSocket 推送端点。

职责：收请求、校验、调 Service、包统一响应。不写业务、不碰数据库。

包含两类端点：
1. REST CRUD（前缀 /api/notices）
2. WebSocket 推送通道（/ws/notices）——心跳 ping/pong 维持连接，
   服务端在发布公告时通过 core.ws_manager 广播 type=notice 消息。
"""
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from core.db import get_db
from core.ws_manager import manager
from schemas.common import ok
from schemas.notice import NoticeCreate, NoticeOut, NoticeUpdate
from service.notice_service import NoticeService

router = APIRouter(prefix="/api/notices", tags=["公告管理"])

# WebSocket 端点单独用一个无前缀的 router 挂载。
# 原因：需求文档约定推送通道路径是 /ws/notices（不在 /api 前缀下）。
# 若用 @router.websocket 挂在 /api/notices 前缀的 router 上，路径会变成
# /api/notices/ws/notices，与前端约定不一致。
ws_router = APIRouter(tags=["公告推送"])


def _get_service(db: Session = Depends(get_db)) -> NoticeService:
    return NoticeService(db)


@router.post("", summary="发布公告（落库后广播给所有在线客户端）")
async def create_notice(payload: NoticeCreate, svc: NoticeService = Depends(_get_service)):
    notice = await svc.create_notice(payload)
    return ok(NoticeOut.model_validate(notice).model_dump(mode="json"))


@router.get("", summary="分页查询公告列表（按发布时间倒序）")
def list_notices(
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数，1-100"),
    svc: NoticeService = Depends(_get_service),
):
    data = svc.list_notices(page, page_size)
    return ok(data)


@router.get("/{notice_id}", summary="查询公告详情")
def get_notice(notice_id: int, svc: NoticeService = Depends(_get_service)):
    notice = svc.get_notice(notice_id)
    return ok(NoticeOut.model_validate(notice).model_dump(mode="json"))


@router.put("/{notice_id}", summary="更新公告")
def update_notice(
    notice_id: int,
    payload: NoticeUpdate,
    svc: NoticeService = Depends(_get_service),
):
    notice = svc.update_notice(notice_id, payload)
    return ok(NoticeOut.model_validate(notice).model_dump(mode="json"))


@router.delete("/{notice_id}", summary="删除公告")
def delete_notice(notice_id: int, svc: NoticeService = Depends(_get_service)):
    svc.delete_notice(notice_id)
    return ok(message="删除成功")


# ==================== WebSocket 端点 ====================
# 注意：WebSocket 端点不放在 /api 前缀下，走 /ws/notices。
# 前端通过 Vite 代理连接 ws://127.0.0.1:5173/ws/notices（vite.config.js 已配 ws:true）。

@ws_router.websocket("/ws/notices")
async def notices_ws(websocket: WebSocket):
    """公告推送通道。

    生命周期：
    - 建立连接 → 加入连接池
    - 循环接收客户端消息：
        type=ping → 回 type=pong（应用层心跳，维持连接）
        其他       → 忽略
    - 断开（WebSocketDisconnect）→ 从连接池移除

    说明：服务端不主动发心跳，由客户端每 30s 发 ping，服务端回 pong。
    这样能可靠地判断"假连接"（笔记本休眠唤醒后的死连接）。
    """
    await manager.connect(websocket)
    try:
        while True:
            msg = await websocket.receive_json()
            if msg.get("type") == "ping":
                await manager.send_personal(websocket, {"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:
        # 客户端异常断开或收到非法 JSON，都走到这里
        pass
    finally:
        await manager.disconnect(websocket)
