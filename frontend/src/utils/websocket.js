// WebSocket 客户端封装：心跳 + 指数退避自动重连。

// 设计要点（对应需求文档 12 节 WebSocket 连接生命周期）：
// 1. 前端主动发心跳：每 HEARTBEAT_INTERVAL 秒发一次 {"type":"ping"}，
//    服务端回 {"type":"pong"}。这样能可靠发现"假连接"（如笔记本休眠唤醒后的死连接）。
// 2. 指数退避重连：断开后 1s → 2s → 4s → 8s ... 封顶 10s，无限重试。
//    每次成功连上就重置退避计数。
// 3. 回调注册：外部通过 onMessage 注册消息处理（如公告 store 监听 type=notice）。

const HEARTBEAT_INTERVAL = 30000 // 30 秒发一次心跳
const RECONNECT_BASE = 1000 // 重连起始间隔 1s
const RECONNECT_MAX = 10000 // 重连封顶 10s

class NoticeWebSocket {
  constructor() {
    this.ws = null
    this.heartbeatTimer = null
    this.reconnectAttempts = 0
    this.manualClosed = false // 是否主动关闭（主动关则不重连）

    // 消息回调列表（可注册多个监听器）
    this.listeners = []
    // 状态变化回调（用于 UI 显示连接状态）
    this.onStatusChange = null
  }

  // 判断当前是否已连接
  get connected() {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
  }

  // 注册消息监听器，返回取消注册函数
  onMessage(fn) {
    this.listeners.push(fn)
    return () => {
      this.listeners = this.listeners.filter((f) => f !== fn)
    }
  }

  // 连接（会自动根据当前协议选择 ws/wss，走 Vite 代理的同源路径）
  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return
    }

    // ws://host/ws/notices —— 同源，走 Vite 代理转发到后端 8000
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws/notices`

    this.ws = new WebSocket(url)

    this.ws.onopen = () => {
      // 连接成功：重置退避计数，启动心跳
      this.reconnectAttempts = 0
      this._startHeartbeat()
      this._setStatus('open')
    }

    this.ws.onmessage = (event) => {
      let message
      try {
        message = JSON.parse(event.data)
      } catch (e) {
        // 非 JSON 消息，忽略
        return
      }
      this.listeners.forEach((fn) => {
        try {
          fn(message)
        } catch (e) {
          console.error('[ws] 消息监听器执行出错:', e)
        }
      })
    }

    this.ws.onclose = () => {
      this._stopHeartbeat()
      this._setStatus('closed')
      this.ws = null
      // 非主动关闭才重连
      if (!this.manualClosed) {
        this._scheduleReconnect()
      }
    }

    this.ws.onerror = (e) => {
      // onerror 后通常会紧跟 onclose，这里只记录，交给 onclose 统一处理重连
      console.error('[ws] 连接错误:', e)
    }
  }

  // 主动关闭（不再重连）
  close() {
    this.manualClosed = true
    this._stopHeartbeat()
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this._setStatus('closed')
  }

  _startHeartbeat() {
    this._stopHeartbeat()
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, HEARTBEAT_INTERVAL)
  }

  _stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  _scheduleReconnect() {
    // 指数退避：1s → 2s → 4s → 8s → 10s（封顶）
    const delay = Math.min(RECONNECT_BASE * 2 ** this.reconnectAttempts, RECONNECT_MAX)
    this.reconnectAttempts += 1
    this._setStatus('reconnecting', delay)
    setTimeout(() => {
      // 延迟期间可能被主动关闭了
      if (!this.manualClosed) {
        this.connect()
      }
    }, delay)
  }

  _setStatus(status, delay) {
    if (this.onStatusChange) {
      this.onStatusChange({ status, delay })
    }
  }
}

// 单例：全局只维护一条公告 WebSocket 连接
export const noticeSocket = new NoticeWebSocket()
