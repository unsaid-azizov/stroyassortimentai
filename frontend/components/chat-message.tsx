'use client'

import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { cn } from '@/lib/utils'
import type { Message } from '@/lib/api/leads'
import { IconUser, IconRobot } from '@tabler/icons-react'

interface ChatMessageProps {
  message: Message
  leadName?: string | null
}

const categoryLabels: Record<string, string> = {
  ORDER_LEAD: 'Заказ',
  QUESTION: 'Вопрос',
  SPAM: 'Спам',
  GREETING: 'Приветствие',
  GOODBYE: 'Прощание',
  OTHER: 'Другое',
}

const categoryColors: Record<string, string> = {
  ORDER_LEAD: 'bg-green-500/10 text-green-700 dark:text-green-400 border-green-500/20',
  QUESTION: 'bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/20',
  SPAM: 'bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/20',
  GREETING: 'bg-purple-500/10 text-purple-700 dark:text-purple-400 border-purple-500/20',
  GOODBYE: 'bg-orange-500/10 text-orange-700 dark:text-orange-400 border-orange-500/20',
  OTHER: 'bg-gray-500/10 text-gray-700 dark:text-gray-400 border-gray-500/20',
}

export function ChatMessage({ message, leadName }: ChatMessageProps) {
  // В БД sender_role может быть: "USER", "AI", "MANAGER"
  const isUser = message.sender_role === 'USER' || message.sender_role.toLowerCase() === 'user'
  const isAI = message.sender_role === 'AI' || message.sender_role.toLowerCase() === 'ai'
  const category = message.ai_stats?.category
  const categoryLabel = category ? categoryLabels[category] || category : null
  const categoryColor = category ? categoryColors[category] || categoryColors.OTHER : null

  return (
    <div
      className={cn(
        'flex gap-3 px-4 py-3',
        isUser ? 'justify-start' : 'justify-end'
      )}
    >
      {isUser && (
        <Avatar className="h-10 w-10 shrink-0">
          <AvatarFallback className="bg-green-100 dark:bg-green-900/30">
            <IconUser className="h-5 w-5 text-green-600 dark:text-green-400" />
          </AvatarFallback>
        </Avatar>
      )}
      <div
        className={cn(
          'flex flex-col gap-1.5 max-w-[80%]',
          isUser ? 'items-start' : 'items-end'
        )}
      >
        {isUser && leadName && (
          <div className="flex items-center gap-2 justify-start">
            <span className="text-xs font-medium text-muted-foreground">
              {leadName}
            </span>
          </div>
        )}
        {isAI && (
          <div className="flex items-center gap-2 justify-end">
            <span className="text-xs font-medium text-muted-foreground">
              AI Ассистент
            </span>
          </div>
        )}
        <div
          className={cn(
            'rounded-lg px-4 py-2.5 shadow-sm',
            isAI
              ? 'bg-blue-500 text-white dark:bg-blue-600'
              : isUser
              ? 'bg-gray-100 text-gray-900 dark:bg-gray-800 dark:text-gray-100'
              : 'bg-gray-100 text-gray-900 dark:bg-gray-800 dark:text-gray-100'
          )}
        >
          <p className="text-sm whitespace-pre-wrap break-words leading-relaxed">
            {message.content}
          </p>
        </div>
        <div className={cn(
          'flex items-center gap-2 text-xs',
          isUser ? 'justify-start' : 'justify-end',
          'text-muted-foreground'
        )}>
          {categoryLabel && categoryColor && (
            <Badge
              variant="outline"
              className={cn('text-xs', categoryColor)}
            >
              {categoryLabel}
            </Badge>
          )}
          <span>
            {format(new Date(message.created_at), 'dd MMM yyyy HH:mm', {
              locale: ru,
            })}
          </span>
        </div>
        {message.ai_stats?.reasoning && isAI && (
          <div className="text-xs text-muted-foreground italic max-w-full bg-muted/50 rounded px-2 py-1">
            {message.ai_stats.reasoning}
          </div>
        )}
      </div>
      {isAI && (
        <Avatar className="h-10 w-10 shrink-0">
          <AvatarFallback className="bg-blue-100 dark:bg-blue-900/30">
            <IconRobot className="h-5 w-5 text-blue-600 dark:text-blue-400" />
          </AvatarFallback>
        </Avatar>
      )}
    </div>
  )
}

