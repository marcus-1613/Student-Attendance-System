// 公告状态管理（Pinia store）。

// 职责：
// 1. 维护未读公告数（铃铛红点）。
// 2. 监听 WebSocket 推送（type=notice），收到新公告时未读数 +1 并弹窗提醒。
// 3. 断线重连后补拉历史公告（避免错过离线期间的公告）。

import { defineStore } from 'pinia'
import { listNotices } from '../api/notice'
import { noticeSocket } from '../utils/websocket'

export const useNoticeStore = defineStore('notice', {
  state: () => ({
    unreadCount: 0, // 未读公告数（铃铛红点）
    latestNotice: null, // 最新一条公告（用于弹窗展示）
  }),

  actions: {
    // 应用启动时调用：连接 WebSocket + 初始补拉（作为基准，不累加未读数）
    init() {
      // 注册消息监听：收到公告推送
      noticeSocket.onMessage((message) => {
        if (message.type === 'notice' && message.data) {
          this.unreadCount += 1
          this.latestNotice = message.data
        }
      })

      // 监听连接状态：重连成功后补拉
      noticeSocket.onStatusChange = ({ status }) => {
        if (status === 'open') {
          // 连上后补拉一次历史公告，作为基准（不直接累加未读数，
          // 未读数由推送驱动；补拉主要是让公告列表页数据完整）
          this.sync()
        }
      }

      // 建立连接
      noticeSocket.connect()
    },

    // 补拉历史公告列表（供公告页和重连后使用）
    async sync() {
      try {
        // 只拉第一页作为基准即可，实际展示在公告页另行分页加载
        await listNotices({ page: 1, page_size: 20 })
      } catch (e) {
        // 补拉失败静默处理，不打断用户（下次重连还会再补）
        console.warn('[notice] 补拉公告失败:', e)
      }
    },

    // 用户点了铃铛 / 进入公告页，清除未读数
    clearUnread() {
      this.unreadCount = 0
    },
  },
})
