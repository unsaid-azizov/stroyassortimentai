'use client'

import { useQuery } from '@tanstack/react-query'
import { useRouter, useParams } from 'next/navigation'
import { AppSidebar } from '@/components/app-sidebar'
import { SiteHeader } from '@/components/site-header'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Chat } from '@/components/chat'
import { leadsApi, type Message } from '@/lib/api/leads'
import { IconArrowLeft, IconPhone, IconMail, IconMessage } from '@tabler/icons-react'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'

const channelLabels: Record<string, string> = {
  telegram: 'Telegram',
  email: 'Email',
  avito: 'Avito',
}

export default function LeadDetailPage() {
  const params = useParams()
  const id = params.id as string
  const router = useRouter()

  const { data: lead, isLoading: isLoadingLead } = useQuery({
    queryKey: ['lead', id],
    queryFn: () => leadsApi.getLead(id),
    enabled: !!id,
  })

  const { data: threads, isLoading: isLoadingThreads } = useQuery({
    queryKey: ['threads', id],
    queryFn: () => leadsApi.getThreads(id),
    enabled: !!id,
  })

  // Получаем все сообщения из всех тредов
  const { data: allMessages, isLoading: isLoadingMessages } = useQuery({
    queryKey: ['threads-messages', id, threads?.map(t => t.id)],
    queryFn: async () => {
      if (!threads || threads.length === 0) return []
      
      const threadDetails = await Promise.all(
        threads.map(thread => leadsApi.getThread(thread.id))
      )
      
      // Объединяем все сообщения из всех тредов и сортируем по дате
      const messages: Message[] = []
      threadDetails.forEach(thread => {
        messages.push(...thread.messages)
      })
      
      return messages.sort((a, b) => 
        new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      )
    },
    enabled: !!threads && threads.length > 0,
  })

  const isLoading = isLoadingLead || isLoadingThreads || isLoadingMessages

  if (isLoading) {
    return (
      <SidebarProvider
        style={
          {
            '--sidebar-width': 'calc(var(--spacing) * 72)',
            '--header-height': 'calc(var(--spacing) * 12)',
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
                  <Skeleton className="h-8 w-64 mb-4" />
                  <Skeleton className="h-96 w-full" />
                </div>
              </div>
            </div>
          </div>
        </SidebarInset>
      </SidebarProvider>
    )
  }

  if (!lead) {
    return (
      <SidebarProvider
        style={
          {
            '--sidebar-width': 'calc(var(--spacing) * 72)',
            '--header-height': 'calc(var(--spacing) * 12)',
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
                  <Card>
                    <CardContent className="pt-6">
                      <p className="text-center text-muted-foreground">
                        Лид не найден
                      </p>
                    </CardContent>
                  </Card>
                </div>
              </div>
            </div>
          </div>
        </SidebarInset>
      </SidebarProvider>
    )
  }

  return (
    <SidebarProvider
      style={
        {
          '--sidebar-width': 'calc(var(--spacing) * 72)',
          '--header-height': 'calc(var(--spacing) * 12)',
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
                <Button
                  variant="ghost"
                  onClick={() => router.back()}
                  className="mb-4"
                >
                  <IconArrowLeft className="h-4 w-4 mr-2" />
                  Назад
                </Button>

                {/* Информация о лиде */}
                <Card className="mb-4">
                  <CardHeader>
                    <CardTitle>{lead.name || 'Без имени'}</CardTitle>
                    <CardDescription>
                      Информация о лиде
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="flex items-center gap-2">
                        <IconMessage className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm text-muted-foreground">Канал:</span>
                        <Badge variant="outline">
                          {channelLabels[lead.channel] || lead.channel}
                        </Badge>
                      </div>
                      {lead.username && (
                        <div className="flex items-center gap-2">
                          <IconMessage className="h-4 w-4 text-muted-foreground" />
                          <span className="text-sm text-muted-foreground">Username:</span>
                          <span className="text-sm font-medium text-blue-600">
                            @{lead.username.replace(/^@/, '')}
                          </span>
                        </div>
                      )}
                      {lead.phone && (
                        <div className="flex items-center gap-2">
                          <IconPhone className="h-4 w-4 text-muted-foreground" />
                          <span className="text-sm text-muted-foreground">Телефон:</span>
                          <span className="text-sm font-medium">{lead.phone}</span>
                        </div>
                      )}
                      {lead.email && (
                        <div className="flex items-center gap-2">
                          <IconMail className="h-4 w-4 text-muted-foreground" />
                          <span className="text-sm text-muted-foreground">Email:</span>
                          <span className="text-sm font-medium">{lead.email}</span>
                        </div>
                      )}
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground">Последний контакт:</span>
                        <span className="text-sm font-medium">
                          {format(new Date(lead.last_seen), 'dd MMM yyyy HH:mm', {
                            locale: ru,
                          })}
                        </span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Переписка */}
                <Card>
                  <CardHeader>
                    <CardTitle>Переписка</CardTitle>
                    <CardDescription>
                      {allMessages?.length || 0} сообщений
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Chat
                      messages={allMessages || []}
                      leadName={lead.name}
                    />
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}

