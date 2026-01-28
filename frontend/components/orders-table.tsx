'use client'

import * as React from 'react'
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
import type { OrderSubmission } from '@/lib/api/orders'
import { OrderDetailModal } from '@/components/order-detail-modal'

interface OrdersTableProps {
  orders: OrderSubmission[]
  total: number
  page: number
  limit: number
  onPageChange: (page: number) => void
}

function formatMoney(amount: number | null, currency: string) {
  if (amount == null) return '—'
  if ((currency || '').toUpperCase() === 'RUB') {
    return `${amount.toLocaleString('ru-RU')} ₽`
  }
  return `${amount.toLocaleString('ru-RU')} ${currency}`
}

export function OrdersTable({ orders, total, page, limit, onPageChange }: OrdersTableProps) {
  const [selectedOrderId, setSelectedOrderId] = React.useState<string | null>(null)
  const totalPages = Math.ceil(total / limit)

  return (
    <>
      <div className="px-4 lg:px-6 space-y-4">
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Дата</TableHead>
                <TableHead>Клиент</TableHead>
                <TableHead>Контакт</TableHead>
                <TableHead>Позиций</TableHead>
                <TableHead>Сумма</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {orders.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground">
                    Заказы не найдены
                  </TableCell>
                </TableRow>
              ) : (
                orders.map((o) => (
                  <TableRow
                    key={o.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => setSelectedOrderId(o.id)}
                  >
                    <TableCell>
                      {format(new Date(o.created_at), 'dd MMM yyyy HH:mm', { locale: ru })}
                    </TableCell>
                    <TableCell className="font-medium">{o.client_name || '—'}</TableCell>
                    <TableCell>{o.client_contact || '—'}</TableCell>
                    <TableCell>{o.items_count ?? '—'}</TableCell>
                    <TableCell>{formatMoney(o.total, o.currency)}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>

        {totalPages > 1 && (
          <div className="flex items-center justify-between">
            <div className="text-sm text-muted-foreground">
              Показано {((page - 1) * limit) + 1} - {Math.min(page * limit, total)} из {total}
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => onPageChange(page - 1)} disabled={page === 1}>
                Назад
              </Button>
              <Button variant="outline" size="sm" onClick={() => onPageChange(page + 1)} disabled={page >= totalPages}>
                Вперед
              </Button>
            </div>
          </div>
        )}
      </div>

      <OrderDetailModal
        orderId={selectedOrderId}
        open={!!selectedOrderId}
        onClose={() => setSelectedOrderId(null)}
      />
    </>
  )
}
