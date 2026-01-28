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

// Функция для форматирования времени в МСК
function formatMoscowTime(isoString: string): string {
  const date = new Date(isoString)
  // Добавляем 3 часа для МСК
  const moscowDate = new Date(date.getTime() + (3 * 60 * 60 * 1000))
  return moscowDate.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// Функция для расчета времени следующего обновления
function getNextSyncTime(lastSyncTime: string): string {
  const lastSync = new Date(lastSyncTime)
  // Добавляем 1 час для следующей синхронизации + 3 часа для МСК
  const nextSync = new Date(lastSync.getTime() + (4 * 60 * 60 * 1000))
  return nextSync.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

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

  // Загрузка статуса синхронизации каталога
  const { data: catalogSyncStatus, isLoading: isLoadingCatalogStatus, refetch: refetchCatalogStatus } = useQuery({
    queryKey: ['catalog', 'sync-status'],
    queryFn: async () => {
      const response = await api.get('/api/catalog/sync/status')
      return response.data
    },
    refetchInterval: 10000, // Обновляем каждые 10 секунд
  })

  // Мутация для запуска синхронизации
  const triggerSyncMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post('/api/catalog/sync')
      return response.data
    },
    onSuccess: () => {
      toast.success('Синхронизация каталога запущена')
      // Обновляем статус через 2 секунды
      setTimeout(() => refetchCatalogStatus(), 2000)
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Ошибка при запуске синхронизации')
    },
  })

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
    mutationFn: async (content: string) => {
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
      // KB теперь в текстовом формате
      setKnowledgeBaseContent(kbData.content)
    }
  }, [kbData])

  const handleSavePrompt = () => {
    updatePromptMutation.mutate(promptContent)
  }

  const handleSaveKB = () => {
    // Просто сохраняем текст как есть
    updateKBMutation.mutate(knowledgeBaseContent)
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
                    <TabsTrigger value="catalog">Каталог 1C</TabsTrigger>
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
                          Добавьте информацию о компании в простом текстовом формате.
                          Разделяйте разделы с помощью "---". Первая строка каждого раздела - заголовок.
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
                                defaultLanguage="markdown"
                                value={knowledgeBaseContent || kbData?.content || ''}
                                onChange={(value) => setKnowledgeBaseContent(value || '')}
                                theme={theme === 'dark' ? 'vs-dark' : 'light'}
                                options={{
                                  minimap: { enabled: false },
                                  fontSize: 14,
                                  wordWrap: 'on',
                                  automaticLayout: true,
                                  lineNumbers: 'on',
                                }}
                              />
                            </div>
                            <div className="mb-4 text-sm text-muted-foreground">
                              <p className="font-medium mb-2">Формат:</p>
                              <code className="block bg-muted p-2 rounded">
                                Заголовок раздела<br/>
                                <br/>
                                Содержимое раздела...<br/>
                                <br/>
                                ---<br/>
                                <br/>
                                Следующий раздел<br/>
                                <br/>
                                Еще содержимое...
                              </code>
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
                  <TabsContent value="catalog">
                    <Card>
                      <CardHeader>
                        <CardTitle>Синхронизация каталога 1C</CardTitle>
                        <CardDescription>
                          Информация о синхронизации товаров из 1C. Каталог обновляется автоматически каждый час.
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        {isLoadingCatalogStatus ? (
                          <Skeleton className="h-[300px] w-full" />
                        ) : (
                          <div className="space-y-6">
                            {/* Статус синхронизации */}
                            <div className="rounded-lg border p-4">
                              <h3 className="font-semibold mb-4">Статус синхронизации</h3>
                              <div className="grid gap-3">
                                <div className="flex justify-between items-center">
                                  <span className="text-sm text-muted-foreground">Статус:</span>
                                  <span className={`text-sm font-medium ${
                                    catalogSyncStatus?.is_syncing
                                      ? 'text-blue-600'
                                      : catalogSyncStatus?.last_sync_success
                                        ? 'text-green-600'
                                        : 'text-red-600'
                                  }`}>
                                    {catalogSyncStatus?.is_syncing
                                      ? 'Синхронизация...'
                                      : catalogSyncStatus?.last_sync_success
                                        ? 'Успешно'
                                        : 'Ошибка'}
                                  </span>
                                </div>

                                {catalogSyncStatus?.last_sync_time && (
                                  <>
                                    <div className="flex justify-between items-center">
                                      <span className="text-sm text-muted-foreground">Последняя синхронизация (МСК):</span>
                                      <span className="text-sm font-medium">
                                        {formatMoscowTime(catalogSyncStatus.last_sync_time)}
                                      </span>
                                    </div>
                                    <div className="flex justify-between items-center">
                                      <span className="text-sm text-muted-foreground">Следующее обновление (МСК):</span>
                                      <span className="text-sm font-medium">
                                        {getNextSyncTime(catalogSyncStatus.last_sync_time)}
                                      </span>
                                    </div>
                                  </>
                                )}

                                {catalogSyncStatus?.last_error && (
                                  <div className="flex justify-between items-center">
                                    <span className="text-sm text-muted-foreground">Ошибка:</span>
                                    <span className="text-sm font-medium text-red-600">
                                      {catalogSyncStatus.last_error}
                                    </span>
                                  </div>
                                )}
                              </div>
                            </div>

                            {/* Метаданные из Redis */}
                            {catalogSyncStatus?.redis_metadata && (
                              <div className="rounded-lg border p-4">
                                <h3 className="font-semibold mb-4">Данные в кеше</h3>
                                <div className="grid gap-3">
                                  <div className="flex justify-between items-center">
                                    <span className="text-sm text-muted-foreground">Товаров в кеше:</span>
                                    <span className="text-sm font-medium">
                                      {catalogSyncStatus.redis_metadata.items_count?.toLocaleString('ru-RU')}
                                    </span>
                                  </div>

                                  <div className="flex justify-between items-center">
                                    <span className="text-sm text-muted-foreground">Время кеша (МСК):</span>
                                    <span className="text-sm font-medium">
                                      {formatMoscowTime(catalogSyncStatus.redis_metadata.last_sync)}
                                    </span>
                                  </div>

                                  <div className="flex justify-between items-center">
                                    <span className="text-sm text-muted-foreground">TTL кеша:</span>
                                    <span className="text-sm font-medium">
                                      {Math.floor(catalogSyncStatus.redis_metadata.ttl_seconds / 3600)} ч ({catalogSyncStatus.redis_metadata.ttl_seconds} сек)
                                    </span>
                                  </div>
                                </div>
                              </div>
                            )}

                            {/* Кнопка запуска синхронизации */}
                            <div className="flex gap-2">
                              <Button
                                onClick={() => triggerSyncMutation.mutate()}
                                disabled={triggerSyncMutation.isPending || catalogSyncStatus?.is_syncing}
                              >
                                {triggerSyncMutation.isPending || catalogSyncStatus?.is_syncing
                                  ? 'Синхронизация...'
                                  : 'Запустить синхронизацию'}
                              </Button>
                              <Button
                                variant="outline"
                                onClick={() => refetchCatalogStatus()}
                              >
                                Обновить статус
                              </Button>
                            </div>

                            {/* Информация */}
                            <div className="rounded-lg bg-muted p-4 text-sm text-muted-foreground">
                              <p className="font-medium mb-2">Информация:</p>
                              <ul className="list-disc list-inside space-y-1">
                                <li>Каталог синхронизируется автоматически каждый час</li>
                                <li>Данные хранятся в Redis с TTL 2 часа</li>
                                <li>При необходимости можно запустить синхронизацию вручную</li>
                              </ul>
                            </div>
                          </div>
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

