import axios from 'axios'

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 65000,
})

request.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

request.interceptors.response.use(
  (resp) => {
    const body = resp.data
    if (body && body.code !== undefined && body.code !== 200) {
      return Promise.reject(new Error(body.msg || '请求失败'))
    }
    return body
  },
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      if (!location.pathname.startsWith('/login')) location.href = '/login'
    }
    const msg = err.response?.data?.msg || err.message || '网络错误'
    return Promise.reject(new Error(msg))
  },
)

export default request
