// Константа для ключа в localStorage
const TOKEN_KEY = 'auth_token'

// Функция для получения токена из localStorage
export function getToken(): string | null {
  // Проверяем, что мы в браузере (localStorage доступен только в браузере)
  if (typeof window === 'undefined') {
    return null
  }
  
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch (error) {
    console.error('Error getting token:', error)
    return null
  }
}

// Функция для сохранения токена в localStorage и cookies
export function setToken(token: string): void {
  // Проверяем, что мы в браузере
  if (typeof window === 'undefined') {
    return
  }
  
  try {
    // Сохраняем в localStorage
    localStorage.setItem(TOKEN_KEY, token)
    // Сохраняем в cookies для middleware
    document.cookie = `${TOKEN_KEY}=${token}; path=/; max-age=604800; SameSite=Lax` // 7 дней
  } catch (error) {
    console.error('Error setting token:', error)
  }
}

// Функция для удаления токена
export function removeToken(): void {
  if (typeof window === 'undefined') {
    return
  }
  
  try {
    localStorage.removeItem(TOKEN_KEY)
    // Удаляем из cookies
    document.cookie = `${TOKEN_KEY}=; path=/; max-age=0`
  } catch (error) {
    console.error('Error removing token:', error)
  }
}

// Функция для проверки, авторизован ли пользователь
export function isAuthenticated(): boolean {
  const token = getToken()
  return token !== null && token !== ''
}

