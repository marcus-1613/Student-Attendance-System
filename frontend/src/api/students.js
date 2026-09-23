import request from './request'

// 学生管理 API 封装。
// 复用 request.js 的 Axios 实例，拦截器已统一解包 {code,message,data}，
// 所以这里每个函数返回的 Promise 直接 resolve 成后端 data。

export function listStudents(params) {
  return request.get('/students', { params })
}

export function createStudent(data) {
  return request.post('/students', data)
}

export function getStudent(id) {
  return request.get(`/students/${id}`)
}

export function updateStudent(id, data) {
  return request.put(`/students/${id}`, data)
}

export function deleteStudent(id) {
  return request.delete(`/students/${id}`)
}

// 批量导入学生（multipart 上传 .csv / .xlsx）。
// 后端契约：POST /api/students/import，参数是 UploadFile（字段名 file），
// 返回 ImportResult { total, success, failed, errors:[{row,student_no,reason}] }。
// 注意：axios 传 FormData 时不要手动设 Content-Type，让 axios 自动带上
// multipart/form-data 的 boundary，否则后端解析不出文件。
export function importStudents(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/students/import', formData)
}
