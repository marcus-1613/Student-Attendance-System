import request from './request'

// 实时人脸检测 API 封装（P11）。
// 后端契约（对应 api/detect.py）：
// - POST /detect   上传一帧图片（multipart，字段名 file），返回人脸框列表。
// 返回 data 结构：{ face_count, faces: [{ bbox, confidence }], elapsed_ms }
// 无人脸时 face_count=0（code 仍为 0，不是错误）。

export function detectFaces(blob) {
  const formData = new FormData()
  // blob 转 File：后端 UploadFile 读的是 file 字段
  const file = blob instanceof File ? blob : new File([blob], `frame_${Date.now()}.jpg`, { type: 'image/jpeg' })
  formData.append('file', file)
  // 同 uploadFace：不手动设 Content-Type，让 axios 自动带 boundary
  return request.post('/detect', formData)
}
