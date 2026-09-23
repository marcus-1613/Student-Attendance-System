import request from './request'

// 脸库审计 API 封装。
// 后端契约（对应 api/audit.py）：
// - GET /audit/duplicates  脸库审计（疑似重复登记 + 脏录入 + 可疑团伙）

export function getAuditDuplicates() {
  return request.get('/audit/duplicates')
}
