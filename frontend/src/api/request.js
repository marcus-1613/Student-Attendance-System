import axios from 'axios'

// Axios 基础封装。
// 只做最基础的配置和拦截处理，不包含任何具体业务 API。
// 具体业务接口（students/faces/stats/notices）在后续阶段分别建立自己的 api 模块。

// 创建 Axios 实例：
// - baseURL：后端所有接口都在 /api 前缀下，这里统一写死，调用时只写相对路径。
// - timeout：请求超时时间（毫秒），10 秒是普通增删改查的合理默认值。
const request = axios.create({
  baseURL: 'http://127.0.0.1:8000/api',
  timeout: 10000,
})

// ---------- 请求拦截器 ----------
// 目前只做"透传"，保留这个钩子是为了将来在这里统一加认证头（token）等。
request.interceptors.request.use(
  (config) => {
    // 将来如需登录态，在这里统一注入，例如：
    // config.headers.Authorization = `Bearer ${token}`
    return config
  },
  (error) => {
    return Promise.reject(error)
  },
)

// ---------- 响应拦截器 ----------
// 后端统一响应格式：{ code, message, data }。
// 这里做基础解包：
// - code === 0：成功，直接返回 data，调用方拿到的就是纯业务数据。
// - code !== 0：业务失败，抛出带 message 的错误，调用方 catch 到。
request.interceptors.response.use(
  (response) => {
    const res = response.data
    if (res && typeof res === 'object' && 'code' in res) {
      if (res.code === 0) {
        return res.data
      }
      // 业务错误：把 message 放进去，方便调用方提示用户
      const err = new Error(res.message || '请求失败')
      err.code = res.code
      return Promise.reject(err)
    }
    // 不是统一信封（比如文件下载、异常响应），原样返回
    return res
  },
  (error) => {
    // 网络错误 / 超时 / HTTP 4xx/5xx 走到这里
    // 这里只做最基础的错误透传，不做全局弹窗提示（那是后续阶段的事）
    return Promise.reject(error)
  },
)

export default request
