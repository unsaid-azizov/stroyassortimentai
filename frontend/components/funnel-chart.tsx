'use client'

import * as React from "react"
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts"
import { useQuery } from "@tanstack/react-query"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import { statsApi } from "@/lib/api/stats"
import { Skeleton } from "@/components/ui/skeleton"

// Хук для получения computed значения цвета
function useChartColor() {
  return React.useMemo(() => {
    if (typeof window === 'undefined') {
      return "oklch(0.646 0.222 41.116)"
    }
    const root = document.documentElement
    return getComputedStyle(root).getPropertyValue('--chart-1').trim() || "oklch(0.646 0.222 41.116)"
  }, [])
}

const chartConfig = {
  count: {
    label: "Количество",
    color: "var(--chart-1)",
  },
} satisfies ChartConfig

const stageLabels: Record<string, string> = {
  "Всего обращений": "Всего обращений",
  "Отфильтровано спама": "Отфильтровано спама",
  "Потенциальные заказы": "Потенциальные заказы",
  "Требуют человека": "Требуют человека",
  "Активные диалоги": "Активные диалоги",
}

export function FunnelChart() {
  const chartColor = useChartColor()
  const { data: funnelData, isLoading } = useQuery({
    queryKey: ['stats', 'funnel-enhanced'],
    queryFn: () => statsApi.getEnhancedFunnel(),
  })

  const chartData = React.useMemo(() => {
    if (!funnelData?.funnel) return []
    return funnelData.funnel.map(item => ({
      stage: stageLabels[item.stage] || item.stage,
      count: item.count,
    }))
  }, [funnelData])

  if (isLoading) {
    return (
      <Card className="@container/card">
        <CardHeader>
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-4 w-48 mt-2" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[250px] w-full" />
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="@container/card">
      <CardHeader>
        <CardTitle>Воронка продаж</CardTitle>
        <CardDescription>
          Конверсия от обращений к активным диалогам
        </CardDescription>
      </CardHeader>
      <CardContent className="px-2 pt-4 sm:px-6 sm:pt-6">
        <ChartContainer
          config={chartConfig}
          className="aspect-auto h-[300px] w-full"
        >
          <BarChart 
            data={chartData} 
            layout="vertical"
            margin={{
              top: 10,
              right: 10,
              bottom: 10,
              left: 10,
            }}
          >
            <defs>
              <linearGradient id="barGradient" x1="0" y1="0" x2="1" y2="0">
                <stop
                  offset="0%"
                  stopColor={chartColor}
                  stopOpacity={1.0}
                />
                <stop
                  offset="100%"
                  stopColor={chartColor}
                  stopOpacity={0.6}
                />
              </linearGradient>
            </defs>
            <CartesianGrid horizontal={false} strokeDasharray="3 3" opacity={0.1} />
            <XAxis 
              type="number" 
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              domain={[(dataMin: number) => Math.max(0, dataMin - 1), (dataMax: number) => dataMax + 1]}
            />
            <YAxis
              dataKey="stage"
              type="category"
              width={150}
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              tickFormatter={(value) => value}
            />
            <ChartTooltip
              cursor={false}
              content={<ChartTooltipContent indicator="line" />}
            />
            <Bar
              dataKey="count"
              fill="url(#barGradient)"
              radius={[0, 4, 4, 0]}
              stroke={chartColor}
              strokeWidth={0}
            />
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}



