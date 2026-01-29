'use client'

import { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
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
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Search, RefreshCw, Eye } from "lucide-react"
import { toast } from "sonner"
import api from '@/lib/api'

interface CatalogItem {
  group_name: string
  group_code: string
  item_name: string
  item_code: string
  Код?: string
  Наименование?: string
  Остаток?: string
  Толщина?: string
  Ширина?: string
  Длина?: string
  [key: string]: any
}

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
  const [promptContent, setPromptContent] = useState('')
  const [knowledgeBaseContent, setKnowledgeBaseContent] = useState('')
  const [catalogSearch, setCatalogSearch] = useState('')
  const [catalogPage, setCatalogPage] = useState(0)
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [selectedItem, setSelectedItem] = useState<CatalogItem | null>(null)
  const theme = useTheme()
  const catalogLimit = 50

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(catalogSearch)
      setCatalogPage(0) // Reset to first page on search
    }, 500)
    return () => clearTimeout(timer)
  }, [catalogSearch])

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

  // Загрузка данных каталога из Redis
  const { data: catalogData, isLoading: catalogLoading, refetch: refetchCatalog } = useQuery({
    queryKey: ['redis-catalog', catalogPage, debouncedSearch],
    queryFn: async () => {
      const response = await api.get('/api/redis/catalog', {
        params: {
          limit: catalogLimit,
          offset: catalogPage * catalogLimit,
          search: debouncedSearch || undefined,
        },
      })
      return response.data
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

                    {/* Просмотр данных каталога */}
                    <Card className="mt-4">
                      <CardHeader>
                        <div className="flex items-center justify-between">
                          <div>
                            <CardTitle>Данные каталога в Redis</CardTitle>
                            <CardDescription>
                              {catalogData
                                ? `Найдено ${catalogData.total.toLocaleString('ru-RU')} товаров`
                                : 'Загрузка...'}
                            </CardDescription>
                          </div>
                          <Button
                            variant="outline"
                            size="icon"
                            onClick={() => refetchCatalog()}
                          >
                            <RefreshCw className="h-4 w-4" />
                          </Button>
                        </div>
                      </CardHeader>
                      <CardContent>
                        {/* Search */}
                        <div className="mb-4">
                          <div className="relative">
                            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                            <Input
                              type="search"
                              placeholder="Поиск по названию, группе, коду..."
                              className="pl-8"
                              value={catalogSearch}
                              onChange={(e) => setCatalogSearch(e.target.value)}
                            />
                          </div>
                        </div>

                        {/* Table */}
                        {catalogLoading ? (
                          <div className="space-y-2">
                            <Skeleton className="h-12 w-full" />
                            <Skeleton className="h-12 w-full" />
                            <Skeleton className="h-12 w-full" />
                          </div>
                        ) : catalogData && catalogData.items.length > 0 ? (
                          <>
                            <div className="rounded-md border overflow-auto max-h-[500px]">
                              <Table>
                                <TableHeader>
                                  <TableRow>
                                    <TableHead>Код</TableHead>
                                    <TableHead>Название</TableHead>
                                    <TableHead>Группа</TableHead>
                                    <TableHead>Ед. изм.</TableHead>
                                    <TableHead>Цена</TableHead>
                                    <TableHead>Остаток</TableHead>
                                    <TableHead>Размеры</TableHead>
                                    <TableHead></TableHead>
                                  </TableRow>
                                </TableHeader>
                                <TableBody>
                                  {catalogData.items.map((item: CatalogItem, idx: number) => (
                                    <TableRow
                                      key={idx}
                                      className="cursor-pointer hover:bg-muted/50"
                                      onClick={() => setSelectedItem(item)}
                                    >
                                      <TableCell className="font-mono text-xs">
                                        {item.item_code || item.Код || '-'}
                                      </TableCell>
                                      <TableCell className="font-medium">
                                        {item.item_name || item.Наименование || '-'}
                                      </TableCell>
                                      <TableCell className="text-sm text-muted-foreground">
                                        {item.group_name || '-'}
                                      </TableCell>
                                      <TableCell className="text-sm">
                                        {item.ЕдИзмерения || item.Дополнительнаяедизмерения1 || 'шт'}
                                      </TableCell>
                                      <TableCell className="font-medium">
                                        {item.Цена ? (
                                          `${Number(item.Цена).toLocaleString('ru-RU')} ₽`
                                        ) : (
                                          '-'
                                        )}
                                      </TableCell>
                                      <TableCell>
                                        {item.Остаток ? (
                                          <Badge variant="secondary">{item.Остаток}</Badge>
                                        ) : (
                                          '-'
                                        )}
                                      </TableCell>
                                      <TableCell className="text-xs text-muted-foreground">
                                        {[
                                          item.Толщина && `${item.Толщина}мм`,
                                          item.Ширина && `${item.Ширина}мм`,
                                          item.Длина && `${item.Длина}мм`,
                                        ]
                                          .filter(Boolean)
                                          .join(' × ') || '-'}
                                      </TableCell>
                                      <TableCell>
                                        <Button
                                          variant="ghost"
                                          size="icon"
                                          className="h-8 w-8"
                                          onClick={(e) => {
                                            e.stopPropagation()
                                            setSelectedItem(item)
                                          }}
                                        >
                                          <Eye className="h-4 w-4" />
                                        </Button>
                                      </TableCell>
                                    </TableRow>
                                  ))}
                                </TableBody>
                              </Table>
                            </div>

                            {/* Pagination */}
                            <div className="flex items-center justify-between mt-4">
                              <div className="text-sm text-muted-foreground">
                                Страница {catalogPage + 1} из {Math.ceil(catalogData.total / catalogLimit)} (показано{' '}
                                {catalogData.items.length} из {catalogData.total.toLocaleString('ru-RU')})
                              </div>
                              <div className="flex gap-2">
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => setCatalogPage((p) => Math.max(0, p - 1))}
                                  disabled={catalogPage === 0}
                                >
                                  Назад
                                </Button>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => setCatalogPage((p) => p + 1)}
                                  disabled={catalogPage >= Math.ceil(catalogData.total / catalogLimit) - 1}
                                >
                                  Вперёд
                                </Button>
                              </div>
                            </div>
                          </>
                        ) : (
                          <div className="text-center text-muted-foreground py-8">
                            Данные не найдены
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

      {/* Product Detail Dialog */}
      <Dialog open={!!selectedItem} onOpenChange={() => setSelectedItem(null)}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-xl">
              {selectedItem?.item_name || selectedItem?.Наименование}
            </DialogTitle>
            <DialogDescription>
              Код: {selectedItem?.item_code || selectedItem?.Код}
            </DialogDescription>
          </DialogHeader>

          {selectedItem && (
            <div className="space-y-4">
              {/* Main Info */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <div className="text-sm font-medium text-muted-foreground">Группа</div>
                  <div>{selectedItem.group_name || '-'}</div>
                </div>
                <div className="space-y-2">
                  <div className="text-sm font-medium text-muted-foreground">Остаток</div>
                  <div>
                    {selectedItem.Остаток ? (
                      <Badge variant="secondary">{selectedItem.Остаток}</Badge>
                    ) : (
                      '-'
                    )}
                  </div>
                </div>
              </div>

              {/* Price & Unit */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <div className="text-sm font-medium text-muted-foreground">Цена</div>
                  <div className="text-2xl font-bold">
                    {selectedItem.Цена
                      ? `${Number(selectedItem.Цена).toLocaleString('ru-RU')} ₽`
                      : '-'}
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="text-sm font-medium text-muted-foreground">
                    Единица измерения
                  </div>
                  <div>{selectedItem.ЕдИзмерения || selectedItem.Дополнительнаяедизмерения1 || 'шт'}</div>
                </div>
              </div>

              {/* Dimensions */}
              {(selectedItem.Толщина || selectedItem.Ширина || selectedItem.Длина) && (
                <div className="space-y-2">
                  <div className="text-sm font-medium text-muted-foreground">Размеры</div>
                  <div className="grid grid-cols-3 gap-2">
                    {selectedItem.Толщина && (
                      <div className="text-sm">
                        <span className="text-muted-foreground">Толщина:</span>{' '}
                        {selectedItem.Толщина} мм
                      </div>
                    )}
                    {selectedItem.Ширина && (
                      <div className="text-sm">
                        <span className="text-muted-foreground">Ширина:</span>{' '}
                        {selectedItem.Ширина} мм
                      </div>
                    )}
                    {selectedItem.Длина && (
                      <div className="text-sm">
                        <span className="text-muted-foreground">Длина:</span>{' '}
                        {selectedItem.Длина} мм
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Material Properties */}
              <div className="grid grid-cols-2 gap-4">
                {selectedItem.Влажность && (
                  <div className="space-y-2">
                    <div className="text-sm font-medium text-muted-foreground">Влажность</div>
                    <div>{selectedItem.Влажность}</div>
                  </div>
                )}
                {selectedItem.Сорт && (
                  <div className="space-y-2">
                    <div className="text-sm font-medium text-muted-foreground">Сорт</div>
                    <div>{selectedItem.Сорт}</div>
                  </div>
                )}
                {selectedItem.Порода && (
                  <div className="space-y-2">
                    <div className="text-sm font-medium text-muted-foreground">Порода</div>
                    <div>{selectedItem.Порода}</div>
                  </div>
                )}
                {selectedItem.ПлотностькгмОбщие && (
                  <div className="space-y-2">
                    <div className="text-sm font-medium text-muted-foreground">Плотность</div>
                    <div>{selectedItem.ПлотностькгмОбщие} кг/м³</div>
                  </div>
                )}
              </div>

              {/* Additional Info */}
              <div className="grid grid-cols-2 gap-4">
                {selectedItem.СрокпроизводстваднОбщие && (
                  <div className="space-y-2">
                    <div className="text-sm font-medium text-muted-foreground">
                      Срок производства
                    </div>
                    <div>{selectedItem.СрокпроизводстваднОбщие} дней</div>
                  </div>
                )}
                {selectedItem.Количествовм2Общие && (
                  <div className="space-y-2">
                    <div className="text-sm font-medium text-muted-foreground">
                      Количество в м²
                    </div>
                    <div>{selectedItem.Количествовм2Общие}</div>
                  </div>
                )}
                {selectedItem.Коэфдополнительнаяедизмерения1 && (
                  <div className="space-y-2">
                    <div className="text-sm font-medium text-muted-foreground">
                      Коэффициент ед. изм.
                    </div>
                    <div>{selectedItem.Коэфдополнительнаяедизмерения1}</div>
                  </div>
                )}
                {selectedItem.ПопулярностьОбщие && (
                  <div className="space-y-2">
                    <div className="text-sm font-medium text-muted-foreground">
                      Популярность
                    </div>
                    <div>
                      <Badge>{selectedItem.ПопулярностьОбщие}</Badge>
                    </div>
                  </div>
                )}
              </div>

              {/* All Fields (Debug) */}
              <details className="mt-4">
                <summary className="text-sm font-medium text-muted-foreground cursor-pointer hover:text-foreground">
                  Все поля (для разработки)
                </summary>
                <pre className="mt-2 p-4 bg-muted rounded-md text-xs overflow-auto max-h-60">
                  {JSON.stringify(selectedItem, null, 2)}
                </pre>
              </details>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </SidebarProvider>
  )
}

