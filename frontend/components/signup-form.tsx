'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useMutation } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import api from '@/lib/api'
import { setToken } from '@/lib/auth'

interface SignupResponse {
  access_token: string
  token_type: string
  user: {
    id: string
    username: string
    email: string
    full_name: string | null
  }
}

export function SignupForm({ ...props }: React.ComponentProps<typeof Card>) {
  const [username, setUsername] = useState('')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const router = useRouter()

  const signupMutation = useMutation({
    mutationFn: async (data: {      username: string
      email: string
      password: string
      full_name?: string
    }) => {
      const response = await api.post<SignupResponse>('/api/auth/signup', data)
      return response.data
    },
    onSuccess: (data) => {
      setToken(data.access_token)
      router.push('/dashboard')
    },
    onError: (error: any) => {
      console.error('Signup error:', error)
      const errorMessage =
        error?.response?.data?.detail ||
        error?.message ||
        'Ошибка при регистрации'
      alert(errorMessage)
    },
  })

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()

    // Валидация
    if (password !== confirmPassword) {
      alert('Пароли не совпадают')
      return
    }

    if (password.length < 8) {
      alert('Пароль должен быть не менее 8 символов')
      return
    }

    signupMutation.mutate({
      username,
      email,
      password,
      full_name: name || undefined,
    })
  }

  return (
    <Card {...props}>
      <CardHeader>
        <CardTitle>Create an account</CardTitle>
        <CardDescription>
          Enter your information below to create your account
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit}>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="username">Username</FieldLabel>
              <Input
                id="username"
                type="text"
                placeholder="johndoe"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={signupMutation.isPending}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="name">Full Name</FieldLabel>
              <Input
                id="name"
                type="text"
                placeholder="John Doe"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={signupMutation.isPending}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="email">Email</FieldLabel>
              <Input
                id="email"
                type="email"
                placeholder="m@example.com"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={signupMutation.isPending}
              />
              <FieldDescription>
                We&apos;ll use this to contact you. We will not share your email
                with anyone else.
              </FieldDescription>
            </Field>
            <Field>
              <FieldLabel htmlFor="password">Password</FieldLabel>
              <Input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={signupMutation.isPending}
              />
              <FieldDescription>
                Must be at least 8 characters long.
              </FieldDescription>
            </Field>
            <Field>
              <FieldLabel htmlFor="confirm-password">
                Confirm Password
              </FieldLabel>
              <Input
                id="confirm-password"
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                disabled={signupMutation.isPending}
              />
              <FieldDescription>Please confirm your password.</FieldDescription>
            </Field>
            <FieldGroup>
              <Field>
                <Button type="submit" disabled={signupMutation.isPending}>
                  {signupMutation.isPending ? 'Creating...' : 'Create Account'}
                </Button>
                <FieldDescription className="px-6 text-center">
                  Already have an account?{' '}
                  <Link href="/login" className="underline">
                    Sign in
                  </Link>
                </FieldDescription>
              </Field>
            </FieldGroup>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  )
}
