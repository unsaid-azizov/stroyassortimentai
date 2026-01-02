'use client'

import { useEffect } from 'react'
import { LoginForm } from "@/components/login-form"

export default function Page() {
  useEffect(() => {
    // Проверяем API URL в консоли для отладки
    console.log('API URL:', process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5537')
  }, [])

  return (
    <div className="flex min-h-svh w-full items-center justify-center p-6 md:p-10">
      <div className="w-full max-w-sm">
        <LoginForm />
      </div>
    </div>
  )
}
