'use client'

import { useEffect, useRef } from 'react'
import { ChatMessage } from './chat-message'
import type { Message } from '@/lib/api/leads'

interface ChatProps {
  messages: Message[]
  leadName?: string | null
}

export function Chat({ messages, leadName }: ChatProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  return (
    <div className="h-[600px] w-full rounded-lg border overflow-y-auto">
      <div ref={scrollRef} className="flex flex-col">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full p-8 text-muted-foreground">
            Нет сообщений
          </div>
        ) : (
          messages.map((message) => (
            <ChatMessage
              key={message.id}
              message={message}
              leadName={leadName}
            />
          ))
        )}
      </div>
    </div>
  )
}

