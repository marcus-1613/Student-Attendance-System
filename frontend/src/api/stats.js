import request from './request'

// 数据统计 API 封装。
// 后端契约（对应 api/stats.py）：
// - GET /stats/summary       学生信息汇总（总人数 + 班级/性别/专业分布）
// - GET /stats/face-coverage 脸照覆盖率（已录/未录/比例）
// - GET /stats/face-count    脸照数量分布（0 张 / 1 张 / 多张）

export function getSummary() {
  return request.get('/stats/summary')
}

export function getFaceCoverage() {
  return request.get('/stats/face-coverage')
}

export function getFaceCount() {
  return request.get('/stats/face-count')
}
