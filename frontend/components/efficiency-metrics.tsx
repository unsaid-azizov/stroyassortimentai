'use client'

import { useQuery } from "@tanstack/react-query"

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
      <div className="grid grid-cols-1 gap-4 px-4 lg:px-6 md:grid-cols-2">
        {[1, 2].map((i) => (
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
    <div className="grid grid-cols-1 gap-4 px-4 lg:px-6 md:grid-cols-2">
      <Card>
        <CardHeader>
          <CardDescription>Конверсия</CardDescription>
          <CardTitle className="text-2xl font-semibold tabular-nums">
            {businessMetrics?.conversion_rate.toFixed(1) ?? '0.0'}%
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mt-2">
            {businessMetrics?.leads_with_orders ?? 0} из {businessMetrics?.total_leads ?? 0} лидов совершили заказ
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
          <p className="text-sm text-muted-foreground mt-2">
            Количество спам-сообщений, отфильтрованных системой
          </p>
        </CardContent>
      </Card>
    </div>
  )
}



