'use client'

import * as React from "react"
import { Pie, PieChart, Cell, Legend, Tooltip } from "recharts"
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
} from "@/components/ui/chart"
import { statsApi } from "@/lib/api/stats"
import { Skeleton } from "@/components/ui/skeleton"

// Хук для получения computed значений цветов
function useChartColors() {
  return React.useMemo(() => {
    if (typeof window === 'undefined') {
      // Fallback цвета для SSR
      return [
        "oklch(0.646 0.222 41.116)",
        "oklch(0.6 0.118 184.704)",
        "oklch(0.398 0.07 227.392)",
        "oklch(0.828 0.189 84.429)",
        "oklch(0.769 0.188 70.08)",
      ]
    }
    
    const root = document.documentElement
    return [
      getComputedStyle(root).getPropertyValue('--chart-1').trim() || "oklch(0.646 0.222 41.116)",
      getComputedStyle(root).getPropertyValue('--chart-2').trim() || "oklch(0.6 0.118 184.704)",
      getComputedStyle(root).getPropertyValue('--chart-3').trim() || "oklch(0.398 0.07 227.392)",
      getComputedStyle(root).getPropertyValue('--chart-4').trim() || "oklch(0.828 0.189 84.429)",
      getComputedStyle(root).getPropertyValue('--chart-5').trim() || "oklch(0.769 0.188 70.08)",
    ]
  }, [])
}

const channelLabels: Record<string, string> = {
  telegram: "Telegram",
  email: "Email",
  avito: "Avito",
}

export function ChannelDistribution() {
  const colors = useChartColors()
  const { data: channelData, isLoading } = useQuery({
    queryKey: ['stats', 'channels'],
    queryFn: () => statsApi.getChannelDistribution(),
  })

  const leadsChartData = React.useMemo(() => {
    if (!channelData?.channels) return []
    return channelData.channels.map(item => ({
      name: channelLabels[item.channel] || item.channel,
      value: item.leads,
    }))
  }, [channelData])

  const orderLeadsChartData = React.useMemo(() => {
    if (!channelData?.channels) return []
    return channelData.channels.map(item => ({
      name: channelLabels[item.channel] || item.channel,
      value: item.order_leads,
    }))
  }, [channelData])

  if (isLoading) {
    return (
      <Card className="@container/card">
        <CardHeader>
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-4 w-48 mt-2" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[300px] w-full" />
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Card className="@container/card">
        <CardHeader>
          <CardTitle>Распределение лидов</CardTitle>
          <CardDescription>
            По каналам связи
          </CardDescription>
        </CardHeader>
        <CardContent className="px-2 pt-4 sm:px-6 sm:pt-6">
          <ChartContainer
            config={{}}
            className="aspect-square h-[300px] w-full"
          >
            <PieChart
              margin={{
                top: 10,
                right: 10,
                bottom: 10,
                left: 10,
              }}
            >
              <defs>
                {colors.map((color, index) => (
                  <linearGradient key={`gradient-${index}`} id={`pieGradient-${index}`} x1="0" y1="0" x2="0" y2="1">
                    <stop
                      offset="0%"
                      stopColor={color}
                      stopOpacity={1.0}
                    />
                    <stop
                      offset="100%"
                      stopColor={color}
                      stopOpacity={0.7}
                    />
                  </linearGradient>
                ))}
              </defs>
              <Pie
                data={leadsChartData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
                stroke="transparent"
                strokeWidth={0}
              >
                {leadsChartData.map((entry, index) => (
                  <Cell 
                    key={`cell-${index}`} 
                    fill={`url(#pieGradient-${index % colors.length})`}
                    opacity={0.9}
                  />
                ))}
              </Pie>
              <ChartTooltip content={<ChartTooltipContent />} />
            </PieChart>
          </ChartContainer>
        </CardContent>
      </Card>
      <Card className="@container/card">
        <CardHeader>
          <CardTitle>Потенциальные заказы</CardTitle>
          <CardDescription>
            По каналам связи
          </CardDescription>
        </CardHeader>
        <CardContent className="px-2 pt-4 sm:px-6 sm:pt-6">
          <ChartContainer
            config={{}}
            className="aspect-square h-[300px] w-full"
          >
            <PieChart
              margin={{
                top: 10,
                right: 10,
                bottom: 10,
                left: 10,
              }}
            >
              <defs>
                {colors.map((color, index) => (
                  <linearGradient key={`gradient-order-${index}`} id={`pieGradientOrder-${index}`} x1="0" y1="0" x2="0" y2="1">
                    <stop
                      offset="0%"
                      stopColor={color}
                      stopOpacity={1.0}
                    />
                    <stop
                      offset="100%"
                      stopColor={color}
                      stopOpacity={0.7}
                    />
                  </linearGradient>
                ))}
              </defs>
              <Pie
                data={orderLeadsChartData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
                stroke="transparent"
                strokeWidth={0}
              >
                {orderLeadsChartData.map((entry, index) => (
                  <Cell 
                    key={`cell-${index}`} 
                    fill={`url(#pieGradientOrder-${index % colors.length})`}
                    opacity={0.9}
                  />
                ))}
              </Pie>
              <ChartTooltip content={<ChartTooltipContent />} />
            </PieChart>
          </ChartContainer>
        </CardContent>
      </Card>
    </div>
  )
}



