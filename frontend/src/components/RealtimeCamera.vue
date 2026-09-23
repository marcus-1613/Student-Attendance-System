<script setup>
import { ref, nextTick, onBeforeUnmount } from 'vue'
import { VideoCamera, VideoPlay, VideoPause, WarningFilled } from '@element-plus/icons-vue'
import { recognizeFrame } from '../api/recognition'

// 实时人脸识别组件（第二阶段 P12-P14）。
//
// 职责：
// 1. 打开摄像头，实时预览（video 元素，镜像显示）。
// 2. 定时抽帧（默认 5 FPS），把当前帧 JPEG 发送给后端 /api/recognize。
// 3. 收到识别结果后，在 canvas overlay 上绘制 bounding box + 身份标签：
//    - 命中学生：绿色框 + 「姓名 相似度%」
//    - 陌生人：黄色框 + 「未识别」
// 4. 代刷预警：多人同框识别出多个学生时，顶部弹红色警示条。
//
// 关键设计：
// - 抽帧 + 跳帧：setInterval 定时抽帧，若上一帧请求未返回就跳过（天然背压）。
// - 镜像：预览 CSS scaleX(-1)，后端 bbox 是原始帧坐标，canvas 绘制时对 x 翻转。
// - 释放：组件卸载时 stop 摄像头 + 清空定时器 + 清空 canvas。

const emit = defineEmits(['recognized']) // 每次识别完成回调（父组件可用于展示最新识别结果列表）

const videoRef = ref(null)
const canvasRef = ref(null)
const streaming = ref(false)
const detecting = ref(false)
const errorMsg = ref('')
const starting = ref(false)
const warning = ref(null) // 代刷预警对象 { triggered, reason, student_nos }

const CAPTURE_INTERVAL = 200 // 200ms → 5 FPS
const JPEG_QUALITY = 0.75

let stream = null
let captureTimer = null
let pending = false

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

async function openCamera() {
  errorMsg.value = ''
  starting.value = true
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false,
    })
    streaming.value = true
    await nextTick()
    const video = videoRef.value
    video.srcObject = stream
    await video.play()
    await nextTick()
    _initCanvas()
    _startCaptureLoop()
  } catch (e) {
    streaming.value = false
    errorMsg.value = friendlyError(e)
  } finally {
    starting.value = false
  }
}

function _initCanvas() {
  const video = videoRef.value
  const canvas = canvasRef.value
  if (!video || !canvas) return
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
}

function _startCaptureLoop() {
  _stopCaptureLoop()
  captureTimer = setInterval(() => _captureAndRecognize(), CAPTURE_INTERVAL)
}

function _stopCaptureLoop() {
  if (captureTimer) {
    clearInterval(captureTimer)
    captureTimer = null
  }
}

async function _captureAndRecognize() {
  const video = videoRef.value
  if (!video || !streaming.value || video.readyState < 2) return
  if (pending) return
  pending = true
  detecting.value = true

  try {
    const offCanvas = document.createElement('canvas')
    offCanvas.width = video.videoWidth
    offCanvas.height = video.videoHeight
    offCanvas.getContext('2d').drawImage(video, 0, 0, offCanvas.width, offCanvas.height)

    const blob = await new Promise((resolve) => {
      offCanvas.toBlob(resolve, 'image/jpeg', JPEG_QUALITY)
    })
    if (!blob) return

    const data = await recognizeFrame(blob)
    warning.value = data.warning || null
    _drawFaces(data.faces || [])
    emit('recognized', data)
  } catch (e) {
    warning.value = null
    _drawFaces([])
  } finally {
    pending = false
    detecting.value = false
  }
}

// 绘制 bbox + 身份标签（canvas 不镜像，对 x 做水平翻转对齐镜像画面）
function _drawFaces(faces) {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  if (!faces || faces.length === 0) return

  ctx.lineWidth = Math.max(2, canvas.width / 300)
  ctx.font = `bold ${Math.max(13, canvas.width / 45)}px sans-serif`

  for (const f of faces) {
    const [x1, y1, x2, y2] = f.bbox
    const mx1 = canvas.width - x2
    const mx2 = canvas.width - x1
    const w = mx2 - mx1
    const h = y2 - y1

    // 命中 → 绿色框；陌生人 → 黄色框
    if (f.matched) {
      ctx.strokeStyle = '#00e676'
      ctx.fillStyle = '#00e676'
      ctx.strokeRect(mx1, y1, w, h)
      const label = `${f.name} ${(f.similarity * 100).toFixed(0)}%`
      _drawLabel(ctx, mx1, y1, label, '#00c853')
    } else {
      ctx.strokeStyle = '#ffc107'
      ctx.fillStyle = '#ffc107'
      ctx.strokeRect(mx1, y1, w, h)
      _drawLabel(ctx, mx1, y1, '未识别', '#ff8f00')
    }
  }
}

// 在框上方画一个带背景的标签
function _drawLabel(ctx, x, y, text, bg) {
  const metrics = ctx.measureText(text)
  const padX = 4
  const labelH = 20
  const labelW = metrics.width + padX * 2
  const labelY = y - labelH - 2 >= 0 ? y - labelH - 2 : y + 2
  ctx.fillStyle = bg
  ctx.fillRect(x, labelY, labelW, labelH)
  ctx.fillStyle = '#fff'
  ctx.fillText(text, x + padX, labelY + labelH - 5)
}

function stopCamera() {
  _stopCaptureLoop()
  if (stream) {
    stream.getTracks().forEach((track) => track.stop())
    stream = null
  }
  if (videoRef.value) videoRef.value.srcObject = null
  streaming.value = false
  detecting.value = false
  pending = false
  warning.value = null
  const canvas = canvasRef.value
  if (canvas) canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height)
}

onBeforeUnmount(() => stopCamera())

defineExpose({ openCamera, stopCamera })
</script>

<template>
  <div class="realtime-camera">
    <div v-if="!streaming" class="camera-placeholder">
      <el-icon :size="48" color="#c0c4cc"><video-camera /></el-icon>
      <p v-if="errorMsg" class="camera-error">{{ errorMsg }}</p>
      <p v-else class="camera-tip">点击下方按钮开启摄像头，实时识别并自动打卡</p>
      <el-button type="primary" :loading="starting" :icon="VideoPlay" @click="openCamera">
        开启摄像头
      </el-button>
    </div>

    <div v-else class="camera-live">
      <div class="camera-frame">
        <video ref="videoRef" class="camera-video" playsinline muted></video>
        <canvas ref="canvasRef" class="camera-overlay"></canvas>

        <!-- 代刷预警条 -->
        <div v-if="warning && warning.triggered" class="anti-cheat-warning">
          <el-icon><warning-filled /></el-icon>
          <span>{{ warning.reason }}</span>
        </div>

        <div v-if="detecting" class="detecting-badge">识别中…</div>
      </div>
      <div class="camera-actions">
        <el-button type="danger" :icon="VideoPause" @click="stopCamera">关闭</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.realtime-camera {
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
.camera-frame {
  position: relative;
  width: 100%;
  border-radius: 6px;
  overflow: hidden;
  background-color: #000;
}
.camera-video {
  display: block;
  width: 100%;
  max-height: 480px;
  transform: scaleX(-1);
}
.camera-overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.anti-cheat-warning {
  position: absolute;
  top: 8px;
  left: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  background-color: rgba(245, 108, 108, 0.92);
  color: #fff;
  font-size: 13px;
  padding: 6px 12px;
  border-radius: 4px;
  max-width: calc(100% - 16px);
}
.detecting-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  background-color: rgba(0, 0, 0, 0.6);
  color: #00e676;
  font-size: 12px;
  padding: 3px 8px;
  border-radius: 4px;
}
.camera-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
}
</style>
