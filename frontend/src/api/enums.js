import request from './request'

// 枚举 API：班级/专业下拉数据。
// 后端 GET /api/enums 返回 {classes: [], majors: []}，拦截器已解包成 data。

export function getEnums() {
  return request.get('/enums')
}
