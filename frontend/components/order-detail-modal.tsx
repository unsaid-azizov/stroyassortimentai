'use client'

import * as React from 'react'
import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import { X } from 'lucide-react'

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { ordersApi } from '@/lib/api/orders'
import { Skeleton } from '@/components/ui/skeleton'

interface OrderDetailModalProps {
  orderId: string | null
  open: boolean
  onClose: () => void
}

function formatMoney(amount: number | null | undefined, currency: string = 'RUB') {
  if (amount == null) return '—'
  if (currency.toUpperCase() === 'RUB') {
    return `${amount.toLocaleString('ru-RU')} ₽`
  }
  return `${amount.toLocaleString('ru-RU')} ${currency}`
}

export function OrderDetailModal({ orderId, open, onClose }: OrderDetailModalProps) {
  const { data: order, isLoading } = useQuery({
    queryKey: ['order', orderId],
    queryFn: () => ordersApi.getOrderDetail(orderId!),
    enabled: !!orderId && open,
  })

  return (
    <Dialog open={open} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center justify-between">
            <span>Детали заказа</span>
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </DialogTitle>
        </DialogHeader>

        {isLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-40 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : order ? (
          <div className="space-y-6">
            {/* Основная информация */}
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-sm text-muted-foreground">Дата</div>
                  <div className="font-medium">
                    {format(new Date(order.created_at), 'dd MMMM yyyy, HH:mm', { locale: ru })}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">Клиент</div>
                  <div className="font-medium">{order.client_name || '—'}</div>
                </div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">Контакт</div>
                <div className="font-medium">{order.client_contact || '—'}</div>
              </div>
            </div>

            <Separator />

            {/* Позиции заказа */}
            {order.payload?.items && order.payload.items.length > 0 && (
              <div className="space-y-3">
                <h3 className="font-semibold">Позиции заказа</h3>
                <div className="space-y-2">
                  {order.payload.items.map((item, idx) => (
                    <div
                      key={idx}
                      className="p-3 rounded-lg border bg-muted/30 space-y-1"
                    >
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <div className="font-medium">{item.product_name}</div>
                          {item.product_code && (
                            <div className="text-xs text-muted-foreground">
                              Код: {item.product_code}
                            </div>
                          )}
                        </div>
                        <div className="text-right">
                          <div className="font-medium">
                            {formatMoney(item.line_total, order.currency)}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {item.quantity} {item.unit || 'шт'} × {formatMoney(item.unit_price, order.currency)}
                          </div>
                        </div>
                      </div>
                      {item.availability && (
                        <div className="text-xs text-muted-foreground">
                          Наличие: {item.availability}
                        </div>
                      )}
                      {item.comment && (
                        <div className="text-sm text-muted-foreground mt-1">
                          Примечание: {item.comment}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Итоги */}
            {order.payload?.pricing && (
              <div className="space-y-3">
                <h3 className="font-semibold">Итоги</h3>
                <div className="space-y-2">
                  {order.payload.pricing.subtotal != null && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Сумма позиций:</span>
                      <span className="font-medium">
                        {formatMoney(order.payload.pricing.subtotal, order.currency)}
                      </span>
                    </div>
                  )}
                  {order.payload.pricing.delivery_cost != null && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Доставка:</span>
                      <span className="font-medium">
                        {formatMoney(order.payload.pricing.delivery_cost, order.currency)}
                      </span>
                    </div>
                  )}
                  {order.payload.pricing.discount != null && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Скидка:</span>
                      <span className="font-medium text-green-600">
                        -{formatMoney(order.payload.pricing.discount, order.currency)}
                      </span>
                    </div>
                  )}
                  <Separator />
                  <div className="flex justify-between text-lg">
                    <span className="font-semibold">Итого:</span>
                    <span className="font-bold">
                      {formatMoney(order.total, order.currency)}
                    </span>
                  </div>
                  {order.payload.pricing.payment_terms && (
                    <div className="text-sm text-muted-foreground">
                      Условия оплаты: {order.payload.pricing.payment_terms}
                    </div>
                  )}
                </div>
              </div>
            )}

            <Separator />

            {/* Саммари диалога */}
            {order.payload?.dialogue_summary && (
              <div className="space-y-3">
                <h3 className="font-semibold">Саммари диалога</h3>
                {order.payload.dialogue_summary.summary && (
                  <p className="text-sm">{order.payload.dialogue_summary.summary}</p>
                )}
                {order.payload.dialogue_summary.key_points && order.payload.dialogue_summary.key_points.length > 0 && (
                  <div>
                    <div className="text-sm font-medium mb-1">Ключевые моменты:</div>
                    <ul className="list-disc list-inside text-sm space-y-1 text-muted-foreground">
                      {order.payload.dialogue_summary.key_points.map((point, idx) => (
                        <li key={idx}>{point}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {order.payload.dialogue_summary.next_steps && order.payload.dialogue_summary.next_steps.length > 0 && (
                  <div>
                    <div className="text-sm font-medium mb-1">Следующие шаги:</div>
                    <ul className="list-disc list-inside text-sm space-y-1 text-muted-foreground">
                      {order.payload.dialogue_summary.next_steps.map((step, idx) => (
                        <li key={idx}>{step}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* Доставка */}
            {(order.payload?.delivery_address || order.payload?.delivery_method) && (
              <>
                <Separator />
                <div className="space-y-3">
                  <h3 className="font-semibold">Доставка</h3>
                  {order.payload.delivery_method && (
                    <div>
                      <div className="text-sm text-muted-foreground">Способ получения</div>
                      <div className="font-medium">{order.payload.delivery_method}</div>
                    </div>
                  )}
                  {order.payload.delivery_address && (
                    <div>
                      <div className="text-sm text-muted-foreground">Адрес</div>
                      <div className="font-medium">{order.payload.delivery_address}</div>
                    </div>
                  )}
                </div>
              </>
            )}

            {/* Дополнительно */}
            {order.payload?.additional_comments && (
              <>
                <Separator />
                <div className="space-y-3">
                  <h3 className="font-semibold">Дополнительно</h3>
                  <p className="text-sm text-muted-foreground">
                    {order.payload.additional_comments}
                  </p>
                </div>
              </>
            )}
          </div>
        ) : (
          <div className="text-center text-muted-foreground py-8">
            Заказ не найден
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
