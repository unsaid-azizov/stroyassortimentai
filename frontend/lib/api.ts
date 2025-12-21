import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { getToken, removeToken } from './auth'

// Создаем axios instance с базовым URL
// Используем полный URL для всех запросов (клиент и SSR)
// В браузере localhost:5537 будет работать, т.к. запрос идет с машины пользователя
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5537',
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

