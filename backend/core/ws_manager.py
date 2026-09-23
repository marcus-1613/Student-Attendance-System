"""WebSocket 连接池管理器。

职责：
- 维护所有在线的 WebSocket 连接（公告推送通道 /ws/notices）。
- 提供 broadcast() 广播方法：把一条消息推给所有在线客户端。
- 广播必须容错：某个客户端连接已死时，send 会抛异常，此时把它从
  连接池剔除，不影响其他客户端正常接收（否则一个卡死的连接会阻断整个广播）。

设计要点：
- 用模块级单例（全局一个连接池），因为 WebSocket 端点和公告发布接口
  是两条不同的路由，需要通过同一个连接池共享"谁在线"这个状态。
- 只保存连接对象和它的 send 方法；不做任何业务判断（推什么内容、什么格式
  由调用方决定）。
"""
import asyncio
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """WebSocket 连接池管理器（单例）。"""

    def __init__(self):
        self._connections: set[WebSocket] = set()
        # 串行化对连接池的增删，避免并发广播时集合被边迭代边修改
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """接受连接，把客户端加入连接池。"""
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        """客户端断开，从连接池移除。"""
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """向所有在线客户端广播一条消息（JSON dict）。

        容错：逐个发送，失败的连接（已死/异常）从池中剔除，
        不阻断其他客户端。
        """
        # 先快照一份，避免发送过程中集合变化
        async with self._lock:
            targets = list(self._connections)

        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:
                # 该连接已死，剔除
                async with self._lock:
                    self._connections.discard(ws)

    async def send_personal(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        """只给单个连接发消息（如心跳 pong 回给发起 ping 的那一个）。"""
        try:
            await websocket.send_json(message)
        except Exception:
            async with self._lock:
                self._connections.discard(websocket)


# 模块级单例：全进程共享同一个连接池
manager = ConnectionManager()
