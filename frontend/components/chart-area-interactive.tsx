"use client"

import * as React from "react"
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts"
import { useQuery } from "@tanstack/react-query"
import { format, subDays } from "date-fns"

import { useIsMobile } from "@/hooks/use-mobile"
import {
  Card,
  CardAction,
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  ToggleGroup,
  ToggleGroupItem,
} from "@/components/ui/toggle-group"
import { statsApi } from "@/lib/api/stats"
import { Skeleton } from "@/components/ui/skeleton"

const chartConfig = {
  leads: {
    label: "Лиды",
    color: "var(--primary)",
  },
  orderLeads: {
    label: "Потенциальные заказы",
    color: "var(--chart-2)",
  },
} satisfies ChartConfig

export function ChartAreaInteractive() {
  const isMobile = useIsMobile()
  const [timeRange, setTimeRange] = React.useState("30d")
  const [metric, setMetric] = React.useState<"leads" | "messages" | "orderLeads">("leads")

  React.useEffect(() => {
    if (isMobile) {
      setTimeRange("7d")
    }
  }, [isMobile])

  // Вычисляем даты для запроса
  const dateTo = new Date().toISOString().split('T')[0]
  const dateFrom = React.useMemo(() => {
    const days = timeRange === "7d" ? 7 : timeRange === "30d" ? 30 : 90
    return subDays(new Date(), days).toISOString().split('T')[0]
  }, [timeRange])

  const { data: timelineData, isLoading } = useQuery({
    queryKey: ['stats', metric === 'orderLeads' ? 'order-leads-timeline' : 'timeline', metric, dateFrom, dateTo],
    queryFn: () => {
      if (metric === 'orderLeads') {
        return statsApi.getOrderLeadsTimeline(dateFrom, dateTo)
      }
      return statsApi.getTimeline(metric, dateFrom, dateTo)
    },
  })

  const chartData = React.useMemo(() => {
    if (!timelineData) return []
    return timelineData.map(item => ({
      date: item.date,
      value: item.value,
    }))
  }, [timelineData])

  const metricLabels = {
    leads: "Лиды",
    messages: "Сообщения",
    orderLeads: "Потенциальные заказы",
  }
  
  // Получаем computed значения цветов
  const chartColor = React.useMemo(() => {
    if (typeof window === 'undefined') {
      return metric === 'orderLeads' 
        ? "oklch(0.6 0.118 184.704)" 
        : "oklch(0.205 0 0)"
    }
    const root = document.documentElement
    if (metric === 'orderLeads') {
      return getComputedStyle(root).getPropertyValue('--chart-2').trim() || "oklch(0.6 0.118 184.704)"
    }
    return getComputedStyle(root).getPropertyValue('--primary').trim() || "oklch(0.205 0 0)"
  }, [metric])

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
        <CardTitle>Динамика {metricLabels[metric]}</CardTitle>
        <CardDescription>
          <span className="hidden @[540px]/card:block">
            За последний период
          </span>
          <span className="@[540px]/card:hidden">Последний период</span>
        </CardDescription>
        <CardAction className="flex gap-2">
          <Select value={metric} onValueChange={(v) => setMetric(v as typeof metric)}>
            <SelectTrigger className="w-40" size="sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="leads">Лиды</SelectItem>
              <SelectItem value="messages">Сообщения</SelectItem>
              <SelectItem value="orderLeads">Потенциальные заказы</SelectItem>
            </SelectContent>
          </Select>
          <ToggleGroup
            type="single"
            value={timeRange}
            onValueChange={setTimeRange}
            variant="outline"
            className="hidden *:data-[slot=toggle-group-item]:!px-4 @[767px]/card:flex"
          >
            <ToggleGroupItem value="90d">3 месяца</ToggleGroupItem>
            <ToggleGroupItem value="30d">30 дней</ToggleGroupItem>
            <ToggleGroupItem value="7d">7 дней</ToggleGroupItem>
          </ToggleGroup>
          <Select value={timeRange} onValueChange={setTimeRange}>
            <SelectTrigger
              className="flex w-40 **:data-[slot=select-value]:block **:data-[slot=select-value]:truncate @[767px]/card:hidden"
              size="sm"
              aria-label="Select a value"
            >
              <SelectValue placeholder="30 дней" />
            </SelectTrigger>
            <SelectContent className="rounded-xl">
              <SelectItem value="90d" className="rounded-lg">
                3 месяца
              </SelectItem>
              <SelectItem value="30d" className="rounded-lg">
                30 дней
              </SelectItem>
              <SelectItem value="7d" className="rounded-lg">
                7 дней
              </SelectItem>
            </SelectContent>
          </Select>
        </CardAction>
      </CardHeader>
      <CardContent className="px-2 pt-4 sm:px-6 sm:pt-6">
        <ChartContainer
          config={chartConfig}
          className="aspect-auto h-[250px] w-full"
        >
          <AreaChart 
            data={chartData}
            margin={{
              top: 10,
              right: 10,
              bottom: 10,
              left: 10,
            }}
          >
            <defs>
              <linearGradient id="fillValue" x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="5%"
                  stopColor={chartColor}
                  stopOpacity={1.0}
                />
                <stop
                  offset="95%"
                  stopColor={chartColor}
                  stopOpacity={0.1}
                />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="date"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              minTickGap={32}
              padding={{ left: 0, right: 0 }}
              tickFormatter={(value) => {
                const date = new Date(value)
                return format(date, "MMM d")
              }}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              width={50}
              domain={[(dataMin: number) => Math.max(0, dataMin - 1), (dataMax: number) => dataMax + 1]}
            />
            <ChartTooltip
              cursor={false}
              content={
                <ChartTooltipContent
                  labelFormatter={(value) => {
                    return format(new Date(value), "dd MMM yyyy")
                  }}
                  indicator="dot"
                />
              }
            />
            <Area
              dataKey="value"
              type="natural"
              fill="url(#fillValue)"
              stroke={chartColor}
            />
          </AreaChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}
