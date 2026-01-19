'use client'

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { useMutation } from "@tanstack/react-query"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import api from "@/lib/api"
import { setToken } from "@/lib/auth"

interface LoginResponse {
  access_token: string
  token_type: string
}

export function LoginForm({
  className,
  ...props
}: React.ComponentProps<"div">) {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const router = useRouter()

  // Mutation для логина
  const loginMutation = useMutation({
    mutationFn: async (data: { username: string; password: string }) => {
      const response = await api.post<LoginResponse>("/api/auth/login", data)
      return response.data
    },
    onSuccess: (data) => {
      // Сохраняем токен
      setToken(data.access_token)
      // Редирект на dashboard
      router.push("/dashboard")
    },
    onError: (error: any) => {
      console.error("Login error:", error)
      const errorMessage = error?.response?.data?.detail || 
                          error?.message || 
                          "Ошибка при входе. Проверьте подключение к серверу."
      alert(errorMessage)
    },
  })

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    console.log('Form submitted:', { username: email, password: '***' })
    console.log('API URL:', process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5537')
    loginMutation.mutate({ username: email, password })
  }

  return (
    <div className={cn("flex flex-col gap-6", className)} {...props}>
      <Card>
        <CardHeader>
          <CardTitle>Login to your account</CardTitle>
          <CardDescription>
            Enter your username and password to login
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit}>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="email">Username</FieldLabel>
                <Input
                  id="email"
                  type="text"
                  placeholder="admin"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={loginMutation.isPending}
                />
              </Field>
              <Field>
                <div className="flex items-center">
                  <FieldLabel htmlFor="password">Password</FieldLabel>
                  <span className="ml-auto inline-block text-sm text-muted-foreground">
                    Ask admin if you forgot it
                  </span>
                </div>
                <Input
                  id="password"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={loginMutation.isPending}
                />
              </Field>
              <Field>
                <Button type="submit" disabled={loginMutation.isPending}>
                  {loginMutation.isPending ? "Logging in..." : "Login"}
                </Button>
              </Field>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
