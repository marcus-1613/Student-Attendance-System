import request from './request'

// 实时人脸识别 + 考勤 API 封装（第二阶段 P12-P14）。
// 后端契约（对应 api/recognition.py）：
// - POST /recognize   上传一帧图片，识别所有脸 + 落考勤 + 返回代刷预警。
// 返回 data 结构：
//   {
//     frame_id, face_count,
//     faces: [{ bbox, confidence, matched, student_id, student_no, name, similarity }],
//     warning: { triggered, reason, student_nos },
//     elapsed_ms
//   }
// 无人脸时 face_count=0（code 仍为 0，不是错误）。

export function recognizeFrame(blob) {
  const formData = new FormData()
  const file = blob instanceof File ? blob : new File([blob], `frame_${Date.now()}.jpg`, { type: 'image/jpeg' })
  formData.append('file', file)
  return request.post('/recognize', formData)
}
