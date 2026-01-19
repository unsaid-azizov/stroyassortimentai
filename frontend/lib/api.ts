import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { getToken, removeToken } from './auth'

// Создаем axios instance с базовым URL
// - SSR (внутри Docker): ходим напрямую в api по API_URL
// - Browser: используем same-origin и путь /api/* (Nginx или Next rewrites проксируют на backend)
const baseURL =
  typeof window === 'undefined'
  ? (process.env.API_URL || 'http://api:5537') 
    : undefined;

const api = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000, // 10 секунд таймаут
})

// Request interceptor - добавляет токен в заголовки
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getToken()
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor - обрабатывает ошибки
api.interceptors.response.use(
  (response) => {
    return response
  },
  (error: AxiosError) => {
    // Если получили 401 (неавторизован), удаляем токен
    if (error.response?.status === 401) {
      removeToken()
      // Редирект на login будет в компонентах
    }
    return Promise.reject(error)
  }
)

export default api

