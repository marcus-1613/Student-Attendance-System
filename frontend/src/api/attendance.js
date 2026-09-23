import request from './request'

// 考勤查询 API 封装（第二阶段 P13）。
// 后端契约（对应 api/recognition.py）：
// - GET /attendances   分页查询考勤记录，可选 student_id 过滤。
// 返回 data：{ total, page, page_size, items: [{ id, student_id, student_no, name, face_id, similarity, check_time }] }

export function listAttendances(params = {}) {
  return request.get('/attendances', { params })
}
