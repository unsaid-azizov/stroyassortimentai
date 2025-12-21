'use client'

import { useQuery } from "@tanstack/react-query"
import { IconCheck, IconX, IconTrendingUp } from "@tabler/icons-react"

import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { statsApi } from "@/lib/api/stats"
import { Skeleton } from "@/components/ui/skeleton"

export function EfficiencyMetrics() {
  const { data: businessMetrics, isLoading } = useQuery({
    queryKey: ['stats', 'business'],
    queryFn: () => statsApi.getBusinessMetrics(),
  })

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-4 px-4 lg:px-6 md:grid-cols-3">
        {[1, 2, 3].map((i) => (
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
    <div className="grid grid-cols-1 gap-4 px-4 lg:px-6 md:grid-cols-3">
      <Card>
        <CardHeader>
          <CardDescription>Конверсия</CardDescription>
          <CardTitle className="text-2xl font-semibold tabular-nums">
            {businessMetrics?.conversion_rate.toFixed(1) ?? '0.0'}%
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="gap-1">
              <IconTrendingUp className="size-3" />
              ORDER_LEAD / Всего обращений
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-2">
            Процент обращений, которые привели к потенциальным заказам
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardDescription>Эффективность AI</CardDescription>
          <CardTitle className="text-2xl font-semibold tabular-nums">
            {businessMetrics?.ai_efficiency.toFixed(1) ?? '0.0'}%
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="gap-1">
              <IconCheck className="size-3" />
              Обработано AI
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-2">
            Процент сообщений, обработанных без участия человека
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardDescription>Отфильтровано спама</CardDescription>
          <CardTitle className="text-2xl font-semibold tabular-nums">
            {businessMetrics?.spam_filtered ?? 0}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="gap-1">
              <IconX className="size-3" />
              SPAM
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-2">
            Количество спам-сообщений, отфильтрованных системой
          </p>
        </CardContent>
      </Card>
    </div>
  )
}



