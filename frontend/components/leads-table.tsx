'use client'

import { useRouter } from 'next/navigation'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import type { Lead } from '@/lib/api/leads'

interface LeadsTableProps {
  leads: Lead[]
  total: number
  page: number
  limit: number
  onPageChange: (page: number) => void
}

const channelLabels: Record<string, string> = {
  telegram: 'Telegram',
  email: 'Email',
  avito: 'Avito',
}

const statusLabels: Record<string, string> = {
  AI_ONLY: 'Только AI',
  HUMAN_INTERVENTION: 'Требует человека',
  CLOSED: 'Закрыт',
}

export function LeadsTable({
  leads,
  total,
  page,
  limit,
  onPageChange,
}: LeadsTableProps) {
  const router = useRouter()
  const totalPages = Math.ceil(total / limit)

  const handleRowClick = (leadId: string) => {
    router.push(`/leads/${leadId}`)
  }

  return (
    <div className="px-4 lg:px-6 space-y-4">
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Имя</TableHead>
              <TableHead>Телефон</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Канал</TableHead>
              <TableHead>Последний контакт</TableHead>
              <TableHead>Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {leads.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-muted-foreground">
                  Лиды не найдены
                </TableCell>
              </TableRow>
            ) : (
              leads.map((lead) => (
                <TableRow
                  key={lead.id}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => handleRowClick(lead.id)}
                >
                  <TableCell className="font-medium">
                    {lead.name || 'Без имени'}
                  </TableCell>
                  <TableCell>{lead.phone || '-'}</TableCell>
                  <TableCell>{lead.email || '-'}</TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {channelLabels[lead.channel] || lead.channel}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {format(new Date(lead.last_seen), 'dd MMM yyyy HH:mm', {
                      locale: ru,
                    })}
                  </TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRowClick(lead.id)}
                    >
                      Открыть
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Пагинация */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            Показано {((page - 1) * limit) + 1} - {Math.min(page * limit, total)} из {total}
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onPageChange(page - 1)}
              disabled={page === 1}
            >
              Назад
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
            >
              Вперед
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}




