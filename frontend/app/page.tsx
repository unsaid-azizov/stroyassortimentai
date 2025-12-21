'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { isAuthenticated } from '@/lib/auth'

export default function HomePage() {
  const router = useRouter()

  useEffect(() => {
    // Проверяем авторизацию и редиректим
    if (isAuthenticated()) {
      router.push('/dashboard')
    } else {
      router.push('/login')
    }
  }, [router])

  // Показываем загрузку во время редиректа
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-center">
        <p className="text-muted-foreground">Загрузка...</p>
      </div>
    </div>
  )
}
