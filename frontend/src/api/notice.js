import request from './request'

// 公告管理 API 封装。
// 后端契约（对应 api/notices.py）：
// - GET    /notices       公告列表（分页，按时间倒序）
// - GET    /notices/{id}  公告详情
// - POST   /notices       发布公告（触发 WS 推送）
// - PUT    /notices/{id}  更新公告
// - DELETE /notices/{id}  删除公告

export function listNotices(params) {
  return request.get('/notices', { params })
}

export function getNotice(id) {
  return request.get(`/notices/${id}`)
}

export function createNotice(data) {
  return request.post('/notices', data)
}

export function updateNotice(id, data) {
  return request.put(`/notices/${id}`, data)
}

export function deleteNotice(id) {
  return request.delete(`/notices/${id}`)
}
