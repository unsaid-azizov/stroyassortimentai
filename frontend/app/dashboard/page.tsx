"use client"

import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { AppSidebar } from "@/components/app-sidebar"
import { ChartAreaInteractive } from "@/components/chart-area-interactive"
import { SectionCards } from "@/components/section-cards"
import { FunnelChart } from "@/components/funnel-chart"
import { ChannelDistribution } from "@/components/channel-distribution"
import { OrdersTable } from "@/components/orders-table"
import { SiteHeader } from "@/components/site-header"
import {
  SidebarInset,
  SidebarProvider,
} from "@/components/ui/sidebar"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { ordersApi } from "@/lib/api/orders"

export default function Page() {
  const [page, setPage] = React.useState(1)
  const limit = 10

  const { data: ordersData, isLoading } = useQuery({
    queryKey: ['orders', 'dashboard', page, limit],
    queryFn: () => ordersApi.getOrders({ page, limit }),
  })

  return (
    <SidebarProvider
      style={
        {
          "--sidebar-width": "calc(var(--spacing) * 72)",
          "--header-height": "calc(var(--spacing) * 12)",
        } as React.CSSProperties
      }
    >
      <AppSidebar variant="inset" />
      <SidebarInset>
        <SiteHeader />
        <div className="flex flex-1 flex-col">
          <div className="@container/main flex flex-1 flex-col gap-2">
            <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
              <SectionCards />
              <div className="px-4 lg:px-6">
                <ChartAreaInteractive />
              </div>
              <div className="px-4 lg:px-6">
                <FunnelChart />
              </div>
              <div className="px-4 lg:px-6">
                <ChannelDistribution />
              </div>
              <div className="px-4 lg:px-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Последние заказы</CardTitle>
                    <CardDescription>
                      Заявки, оформленные через бота (с рассчитанными итогами)
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {isLoading ? (
                      <div className="space-y-4">
                        <Skeleton className="h-12 w-full" />
                        <Skeleton className="h-12 w-full" />
                        <Skeleton className="h-12 w-full" />
                      </div>
                    ) : ordersData ? (
                      <OrdersTable
                        orders={ordersData.orders}
                        total={ordersData.total}
                        page={page}
                        limit={limit}
                        onPageChange={setPage}
                      />
                    ) : (
                      <div className="text-center text-muted-foreground py-8">
                        Заказы не найдены
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
