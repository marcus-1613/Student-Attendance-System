import request from './request'

// 人脸录入 API 封装。
// 后端契约（对应 api/faces.py）：
// - POST   /students/{studentId}/faces   上传脸照（multipart，字段名 file）
// - GET    /students/{studentId}/faces   查询学生脸照列表
// - DELETE /faces/{faceId}               删除单张脸照
// 上传失败（无人脸/图片无效/学生不存在）统一走 code 非0，拦截器已抛错。

export function uploadFace(studentId, file) {
  const formData = new FormData()
  formData.append('file', file)
  // 与 importStudents 同理：axios 传 FormData 不手动设 Content-Type，
  // 让 axios 自动带 multipart/form-data 的 boundary。
  return request.post(`/students/${studentId}/faces`, formData)
}

export function listFaces(studentId) {
  return request.get(`/students/${studentId}/faces`)
}

export function deleteFace(faceId) {
  return request.delete(`/faces/${faceId}`)
}
