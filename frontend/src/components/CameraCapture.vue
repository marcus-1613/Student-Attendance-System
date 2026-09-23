<script setup>
import { ref, nextTick, onBeforeUnmount } from 'vue'
import { VideoCamera, Camera } from '@element-plus/icons-vue'

// 摄像头采集组件。
//
// 职责：打开摄像头、实时预览、拍照（canvas 取原始帧）。
// 不负责上传——拍照得到的 Blob 通过 emit('captured', blob) 交给父组件。
//
// 镜像策略（规划 Q3）：预览用 CSS scaleX(-1) 镜像显示给用户看，
// 但 canvas 截取的是「原始帧」（不做翻转），保证录入与将来识别一致。

const emit = defineEmits(['captured'])

const videoRef = ref(null) // <video> 元素
const streaming = ref(false) // 摄像头是否已启动
const errorMsg = ref('') // 启动失败的错误提示
const starting = ref(false) // 正在申请摄像头权限

let stream = null // 当前 MediaStream

// 根据错误类型返回友好提示（规划 R9：区分不同失败原因）
function friendlyError(err) {
  if (!err) return '无法访问摄像头'
  switch (err.name) {
    case 'NotAllowedError':
    case 'SecurityError':
      return '摄像头权限被拒绝，请在浏览器地址栏允许访问摄像头'
    case 'NotFoundError':
    case 'DevicesNotFoundError':
      return '未检测到摄像头设备'
    case 'NotReadableError':
    case 'TrackStartError':
      return '摄像头被其他程序占用，请关闭后重试'
    default:
      return `摄像头启动失败：${err.message || err.name}`
  }
}

// 打开摄像头
async function openCamera() {
  errorMsg.value = ''
  starting.value = true
  try {
    // 1. 先申请摄像头（失败会走 catch 给友好提示，此时还没碰 DOM）
    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: 'user',
        width: { ideal: 640 },
        height: { ideal: 480 },
      },
      audio: false,
    })

    // 2. 先把 streaming 置 true，让 v-else 分支里的 <video> 渲染进 DOM。
    //    ⚠️ 时序关键：<video> 在 v-else 里，streaming=false 时它还不存在，
    //    直接 videoRef.value.srcObject 会报 "Cannot set properties of null"。
    streaming.value = true
    await nextTick() // 等 Vue 完成 DOM 渲染，videoRef.value 才有值

    // 3. 挂视频流并播放
    const video = videoRef.value
    video.srcObject = stream
    await video.play()
  } catch (e) {
    // 若已切到预览态但后续失败，回滚到占位态，避免卡在黑屏
    streaming.value = false
    errorMsg.value = friendlyError(e)
  } finally {
    starting.value = false
  }
}

// 拍照：canvas 从 video 取当前帧（原始帧，不镜像），转成 JPEG Blob
function capture() {
  const video = videoRef.value
  if (!video || !streaming.value) return

  const canvas = document.createElement('canvas')
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  const ctx = canvas.getContext('2d')
  // 直接画原始帧，不做水平翻转
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

  canvas.toBlob(
    (blob) => {
      if (blob) emit('captured', blob)
    },
    'image/jpeg',
    0.9,
  )
}

// 关闭摄像头：停止所有 tracks、释放流、清空预览
function stopCamera() {
  if (stream) {
    stream.getTracks().forEach((track) => track.stop())
    stream = null
  }
  if (videoRef.value) {
    videoRef.value.srcObject = null
  }
  streaming.value = false
}

// 组件销毁时释放摄像头（避免浏览器标签还亮着摄像头灯）
onBeforeUnmount(() => {
  stopCamera()
})

// 暴露给父组件手动调用（例如「重拍」）
defineExpose({ openCamera, stopCamera })
</script>

<template>
  <div class="camera-capture">
    <!-- 未启动 / 启动失败时显示占位 + 启动按钮 -->
    <div v-if="!streaming" class="camera-placeholder">
      <el-icon :size="48" color="#c0c4cc"><video-camera /></el-icon>
      <p v-if="errorMsg" class="camera-error">{{ errorMsg }}</p>
      <p v-else class="camera-tip">点击下方按钮开启摄像头</p>
      <el-button
        type="primary"
        :loading="starting"
        :icon="Camera"
        @click="openCamera"
      >
        开启摄像头
      </el-button>
    </div>

    <!-- 已启动：预览（CSS 镜像）+ 快门 -->
    <div v-else class="camera-live">
      <!-- 镜像显示给用户看，但底层是原始帧 -->
      <video ref="videoRef" class="camera-video" playsinline muted></video>
      <div class="camera-actions">
        <el-button type="success" :icon="Camera" @click="capture">拍照</el-button>
        <el-button @click="stopCamera">关闭</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.camera-capture {
  width: 100%;
}
.camera-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: 260px;
  background-color: #f5f7fa;
  border: 1px dashed #dcdfe6;
  border-radius: 6px;
  padding: 24px;
}
.camera-error {
  color: #f56c6c;
  font-size: 13px;
  margin: 0;
}
.camera-tip {
  color: #909399;
  font-size: 13px;
  margin: 0;
}
.camera-live {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.camera-video {
  width: 100%;
  max-height: 360px;
  border-radius: 6px;
  background-color: #000;
  /* 镜像显示给用户看，视觉上像照镜子；原始帧保持不变 */
  transform: scaleX(-1);
}
.camera-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
}
</style>
