'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AppSidebar } from '@/components/app-sidebar'
import { SiteHeader } from '@/components/site-header'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { leadsApi, type LeadsFilters } from '@/lib/api/leads'
import { LeadsTable } from '@/components/leads-table'
import { LeadsFilters as FiltersComponent } from '@/components/leads-filters'
import { Skeleton } from '@/components/ui/skeleton'

export default function LeadsPage() {
  const [filters, setFilters] = useState<LeadsFilters>({
    page: 1,
    limit: 50,
  })

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['leads', filters],
    queryFn: () => leadsApi.getLeads(filters),
  })

  const handleFiltersChange = (newFilters: Partial<LeadsFilters>) => {
    setFilters((prev) => ({ ...prev, ...newFilters, page: 1 }))
  }

  return (
    <SidebarProvider
      style={
        {
          '--sidebar-width': 'calc(var(--spacing) * 72)',
          '--header-height': 'calc(var(--spacing) * 12)',
        } as React.CSSProperties
      }
    >
      <AppSidebar variant="inset" />
      <SidebarInset>
        <SiteHeader />
        <div className="flex flex-1 flex-col">
          <div className="@container/main flex flex-1 flex-col gap-2">
            <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
              <div className="px-4 lg:px-6">
                <h1 className="text-2xl font-semibold mb-4">Доска лидов</h1>
                <FiltersComponent
                  filters={filters}
                  onFiltersChange={handleFiltersChange}
                />
              </div>
              {isLoading ? (
                <div className="px-4 lg:px-6 space-y-4">
                  <Skeleton className="h-12 w-full" />
                  <Skeleton className="h-64 w-full" />
                </div>
              ) : (
                <LeadsTable
                  leads={data?.leads || []}
                  total={data?.total || 0}
                  page={filters.page || 1}
                  limit={filters.limit || 50}
                  onPageChange={(page) =>
                    setFilters((prev) => ({ ...prev, page }))
                  }
                />
              )}
            </div>
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}




