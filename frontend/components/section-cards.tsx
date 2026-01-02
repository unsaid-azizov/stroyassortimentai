'use client'

import { useQuery } from "@tanstack/react-query"
import { IconTrendingUp, IconX } from "@tabler/icons-react"

import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { statsApi } from "@/lib/api/stats"
import { Skeleton } from "@/components/ui/skeleton"

export function SectionCards() {
  const { data: businessMetrics, isLoading } = useQuery({
    queryKey: ['stats', 'business'],
    queryFn: () => statsApi.getBusinessMetrics(),
  })

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-4 px-4 lg:px-6 @xl/main:grid-cols-2 @5xl/main:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-8 w-32 mt-2" />
            </CardHeader>
          </Card>
        ))}
      </div>
    )
  }

  return (
    <div className="*:data-[slot=card]:from-primary/5 *:data-[slot=card]:to-card dark:*:data-[slot=card]:bg-card grid grid-cols-1 gap-4 px-4 *:data-[slot=card]:bg-gradient-to-t *:data-[slot=card]:shadow-xs lg:px-6 @xl/main:grid-cols-2 @5xl/main:grid-cols-4">
      <Card className="@container/card">
        <CardHeader>
          <CardDescription>Потенциальных заказов</CardDescription>
          <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
            {businessMetrics?.potential_orders ?? 0}
          </CardTitle>
        </CardHeader>
        <CardFooter className="flex-col items-start gap-1.5 text-sm">
          <div className="line-clamp-1 flex gap-2 font-medium">
            Клиенты готовы к покупке <IconTrendingUp className="size-4" />
          </div>
          <div className="text-muted-foreground">
            Интерес к покупке
          </div>
        </CardFooter>
      </Card>
      <Card className="@container/card">
        <CardHeader>
          <CardDescription>Новых лидов (сегодня)</CardDescription>
          <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
            {businessMetrics?.new_leads_today ?? 0}
          </CardTitle>
        </CardHeader>
        <CardFooter className="flex-col items-start gap-1.5 text-sm">
          <div className="line-clamp-1 flex gap-2 font-medium">
            Новые контакты сегодня <IconTrendingUp className="size-4" />
          </div>
          <div className="text-muted-foreground">
            За неделю: {businessMetrics?.new_leads_week ?? 0}
          </div>
        </CardFooter>
      </Card>
      <Card className="@container/card">
        <CardHeader>
          <CardDescription>Конверсия</CardDescription>
          <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
            {(businessMetrics?.conversion_rate ?? 0).toFixed(1)}%
          </CardTitle>
        </CardHeader>
        <CardFooter className="flex-col items-start gap-1.5 text-sm">
          <div className="line-clamp-1 flex gap-2 font-medium">
            {businessMetrics?.leads_with_orders ?? 0} из {businessMetrics?.total_leads ?? 0} лидов совершили заказ <IconTrendingUp className="size-4" />
          </div>
          <div className="text-muted-foreground">
            Конверсия лидов в заказы
          </div>
        </CardFooter>
      </Card>
      <Card className="@container/card">
        <CardHeader>
          <CardDescription>Сумма заказов (неделя)</CardDescription>
          <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
            {(businessMetrics?.orders_total_amount_week ?? 0).toLocaleString('ru-RU')} ₽
          </CardTitle>
        </CardHeader>
        <CardFooter className="flex-col items-start gap-1.5 text-sm">
          <div className="line-clamp-1 flex gap-2 font-medium">
            Всего заказов: {businessMetrics?.orders_count ?? 0} <IconTrendingUp className="size-4" />
          </div>
          <div className="text-muted-foreground">
            Всего сумма: {(businessMetrics?.orders_total_amount ?? 0).toLocaleString('ru-RU')} ₽
          </div>
        </CardFooter>
      </Card>
    </div>
  )
}
