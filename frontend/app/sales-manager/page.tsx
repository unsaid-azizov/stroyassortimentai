'use client'

import { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import Editor from '@monaco-editor/react'
import { AppSidebar } from "@/components/app-sidebar"
import { SiteHeader } from "@/components/site-header"
import {
  SidebarInset,
  SidebarProvider,
} from "@/components/ui/sidebar"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Skeleton } from "@/components/ui/skeleton"
import { toast } from "sonner"
import api from '@/lib/api'

// Хук для определения темы
function useTheme() {
  const [theme, setTheme] = useState<'light' | 'dark'>('light')

  useEffect(() => {
    const checkTheme = () => {
      const isDark = document.documentElement.classList.contains('dark') ||
                    window.matchMedia('(prefers-color-scheme: dark)').matches
      setTheme(isDark ? 'dark' : 'light')
    }

    checkTheme()

    // Отслеживаем изменения темы
    const observer = new MutationObserver(checkTheme)
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class']
    })

    // Отслеживаем системные изменения темы
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    mediaQuery.addEventListener('change', checkTheme)

    return () => {
      observer.disconnect()
      mediaQuery.removeEventListener('change', checkTheme)
    }
  }, [])

  return theme
}

export default function SalesManagerPage() {
  const router = useRouter()
  const [promptContent, setPromptContent] = useState('')
  const [knowledgeBaseContent, setKnowledgeBaseContent] = useState('')
  const theme = useTheme()

  // Загрузка промпта
  const { data: promptData, isLoading: isLoadingPrompt } = useQuery({
    queryKey: ['settings', 'prompt'],
    queryFn: async () => {
      try {
        const response = await api.get('/api/settings/prompt')
        return response.data
      } catch (error: any) {
        if (error.response?.status === 404) {
          return null
        }
        throw error
      }
    },
  })

  // Загрузка базы знаний
  const { data: kbData, isLoading: isLoadingKB } = useQuery({
    queryKey: ['settings', 'knowledge-base'],
    queryFn: async () => {
      const response = await api.get('/api/settings/knowledge-base')
      return response.data
    },
  })

  // Обновление промпта
  const updatePromptMutation = useMutation({
    mutationFn: async (content: string) => {
      const response = await api.put('/api/settings/prompt', {
        content,
        name: 'default'
      })
      return response.data
    },
    onSuccess: () => {
      toast.success('Промпт успешно обновлен')
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Ошибка при обновлении промпта')
    },
  })

  // Обновление базы знаний
  const updateKBMutation = useMutation({
    mutationFn: async (content: any) => {
      const response = await api.put('/api/settings/knowledge-base', { content })
      return response.data
    },
    onSuccess: () => {
      toast.success('База знаний успешно обновлена')
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Ошибка при обновлении базы знаний')
    },
  })

  // Инициализация содержимого при загрузке
  useEffect(() => {
    if (promptData?.content) {
      setPromptContent(promptData.content)
    }
  }, [promptData])

  useEffect(() => {
    if (kbData?.content && !knowledgeBaseContent) {
      setKnowledgeBaseContent(JSON.stringify(kbData.content, null, 2))
    }
  }, [kbData])

  const handleSavePrompt = () => {
    updatePromptMutation.mutate(promptContent)
  }

  const handleSaveKB = () => {
    try {
      const parsed = JSON.parse(knowledgeBaseContent)
      updateKBMutation.mutate(parsed)
    } catch (error) {
      toast.error('Неверный формат JSON')
    }
  }

  return (
    <SidebarProvider
      style={
        {
          "--sidebar-width": "calc(var(--spacing) * 72)",
          "--header-height": "calc(var(--spacing) * 12)",
        } as React.CSSProperties
      }
    >
      <AppSidebar variant="inset" />
      <SidebarInset>
        <SiteHeader />
        <div className="flex flex-1 flex-col">
          <div className="@container/main flex flex-1 flex-col gap-2">
            <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
              <div className="px-4 lg:px-6">
                <h1 className="text-2xl font-bold">Менеджер продаж</h1>
                <p className="text-muted-foreground">
                  Настройка параметров AI агента
                </p>
              </div>
              <div className="px-4 lg:px-6">
                <Tabs defaultValue="prompt" className="w-full">
                  <TabsList>
                    <TabsTrigger value="prompt">Промпт агента</TabsTrigger>
                    <TabsTrigger value="knowledge-base">База знаний</TabsTrigger>
                  </TabsList>
                  <TabsContent value="prompt">
                    <Card>
                      <CardHeader>
                        <CardTitle>Редактор промпта</CardTitle>
                        <CardDescription>
                          Измените инструкции для AI агента. Изменения применяются сразу после сохранения.
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        {isLoadingPrompt ? (
                          <Skeleton className="h-[500px] w-full" />
                        ) : (
                          <>
                            <div className="mb-4">
                              <Editor
                                height="500px"
                                defaultLanguage="markdown"
                                value={promptContent || promptData?.content || ''}
                                onChange={(value) => setPromptContent(value || '')}
                                theme={theme === 'dark' ? 'vs-dark' : 'light'}
                                options={{
                                  minimap: { enabled: false },
                                  fontSize: 14,
                                  wordWrap: 'on',
                                  automaticLayout: true,
                                }}
                              />
                            </div>
                            <div className="flex gap-2">
                              <Button
                                onClick={handleSavePrompt}
                                disabled={updatePromptMutation.isPending}
                              >
                                {updatePromptMutation.isPending ? 'Сохранение...' : 'Сохранить промпт'}
                              </Button>
                            </div>
                          </>
                        )}
                      </CardContent>
                    </Card>
                  </TabsContent>
                  <TabsContent value="knowledge-base">
                    <Card>
                      <CardHeader>
                        <CardTitle>Редактор базы знаний</CardTitle>
                        <CardDescription>
                          Обновите информацию о компании (цены, адреса, контакты и т.д.)
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        {isLoadingKB ? (
                          <Skeleton className="h-[500px] w-full" />
                        ) : (
                          <>
                            <div className="mb-4">
                              <Editor
                                height="500px"
                                defaultLanguage="json"
                                value={knowledgeBaseContent || JSON.stringify(kbData?.content || {}, null, 2)}
                                onChange={(value) => setKnowledgeBaseContent(value || '')}
                                theme={theme === 'dark' ? 'vs-dark' : 'light'}
                                options={{
                                  minimap: { enabled: false },
                                  fontSize: 14,
                                  wordWrap: 'on',
                                  automaticLayout: true,
                                }}
                              />
                            </div>
                            <div className="flex gap-2">
                              <Button
                                onClick={handleSaveKB}
                                disabled={updateKBMutation.isPending}
                              >
                                {updateKBMutation.isPending ? 'Сохранение...' : 'Сохранить базу знаний'}
                              </Button>
                            </div>
                          </>
                        )}
                      </CardContent>
                    </Card>
                  </TabsContent>
                </Tabs>
              </div>
            </div>
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}

