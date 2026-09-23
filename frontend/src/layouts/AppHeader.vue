<script setup>
// 顶部 Header：系统标题 + 公告通知铃铛（红点 + 弹窗提醒）。
import { ref, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElNotification } from 'element-plus'
import { Bell } from '@element-plus/icons-vue'
import { useNoticeStore } from '../stores/notice'

const router = useRouter()
const noticeStore = useNoticeStore()

// 是否显示公告下拉面板
const popoverVisible = ref(false)

// 应用启动时初始化公告 store（建立 WebSocket + 注册推送监听）
onMounted(() => {
  noticeStore.init()
})

// 收到新公告（latestNotice 变化）时弹窗提醒
watch(
  () => noticeStore.latestNotice,
  (notice) => {
    if (notice) {
      ElNotification({
        title: '新公告',
        message: notice.title,
        type: 'info',
        duration: 5000,
      })
    }
  },
)

// 点击铃铛按钮：切换下拉面板
function handleBellClick() {
  popoverVisible.value = !popoverVisible.value
}

// 跳转到公告页
function goNotices() {
  popoverVisible.value = false
  noticeStore.clearUnread()
  router.push('/notices')
}

// 格式化时间：后端返回 "YYYY-MM-DD HH:MM:SS"，截取到分钟
function formatTime(datetime) {
  if (!datetime) return ''
  return String(datetime).slice(0, 16)
}
</script>

<template>
  <el-header class="app-header" height="60px">
    <div class="header-title">学生刷脸考勤系统</div>
    <div class="header-right">
      <el-popover
        v-model:visible="popoverVisible"
        placement="bottom-end"
        :width="300"
        trigger="click"
      >
        <template #reference>
          <el-badge
            :value="noticeStore.unreadCount"
            :hidden="noticeStore.unreadCount === 0"
            :max="99"
          >
            <el-button circle @click="handleBellClick">
              <el-icon><Bell /></el-icon>
            </el-button>
          </el-badge>
        </template>
        <div class="notice-panel">
          <div v-if="noticeStore.latestNotice" class="latest-notice">
            <div class="latest-title">{{ noticeStore.latestNotice.title }}</div>
            <div class="latest-meta">
              {{ noticeStore.latestNotice.publisher || '未知' }} ·
              {{ formatTime(noticeStore.latestNotice.created_at) }}
            </div>
            <div class="latest-content">
              {{ noticeStore.latestNotice.content || '（无内容）' }}
            </div>
          </div>
          <div v-else class="empty-notice">暂无公告</div>
          <div class="panel-footer">
            <el-button text type="primary" size="small" @click="goNotices">
              查看全部公告
            </el-button>
          </div>
        </div>
      </el-popover>
    </div>
  </el-header>
</template>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background-color: #ffffff;
  border-bottom: 1px solid #e4e7ed;
}
.header-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.notice-panel {
  display: flex;
  flex-direction: column;
}
.latest-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}
.latest-meta {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
}
.latest-content {
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
  word-break: break-all;
  max-height: 120px;
  overflow-y: auto;
}
.empty-notice {
  color: #909399;
  font-size: 13px;
  padding: 12px 0;
  text-align: center;
}
.panel-footer {
  margin-top: 12px;
  text-align: center;
  border-top: 1px solid #f0f0f0;
  padding-top: 8px;
}
</style>
