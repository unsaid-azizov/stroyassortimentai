import api from '../api'

// Типы для статистики
export interface StatsOverview {
  total_leads: number
  active_threads: number
  total_messages: number
  avg_cost: number
}

export interface CategoryStat {
  category: string
  count: number
}

export interface TimelineData {
  date: string
  value: number
}

export interface FunnelData {
  stage: string
  count: number
}

export interface CostsData {
  total: number
  average: number
}

export interface BusinessMetrics {
  potential_orders: number
  new_leads_today: number
  new_leads_week: number
  ai_processed_messages: number
  human_needed_count: number
  spam_filtered: number
  conversion_rate: number
  total_leads: number
  leads_with_orders: number
  orders_count: number
  orders_total_amount: number
  orders_total_amount_week: number
}

export interface ChannelDistributionItem {
  channel: string
  leads: number
  order_leads: number
}

export interface ChannelDistribution {
  channels: ChannelDistributionItem[]
}

export interface EnhancedFunnelItem {
  stage: string
  count: number
}

export interface EnhancedFunnel {
  funnel: EnhancedFunnelItem[]
}

// API функции для статистики
export const statsApi = {
  // Получить общую статистику
  getOverview: async (): Promise<StatsOverview> => {
    const response = await api.get<StatsOverview>('/api/stats/overview')
    return response.data
  },

  // Получить распределение по категориям
  getCategories: async (): Promise<CategoryStat[]> => {
    const response = await api.get<CategoryStat[]>('/api/stats/categories')
    return response.data
  },

  // Получить динамику по дням
  getTimeline: async (
    metric: 'leads' | 'messages' | 'costs',
    dateFrom?: string,
    dateTo?: string
  ): Promise<TimelineData[]> => {
    const params = new URLSearchParams()
    params.append('metric', metric)
    if (dateFrom) params.append('date_from', dateFrom)
    if (dateTo) params.append('date_to', dateTo)

    const response = await api.get<TimelineData[]>(
      `/api/stats/timeline?${params.toString()}`
    )
    return response.data
  },

  // Получить воронку конверсий
  getFunnel: async (): Promise<FunnelData[]> => {
    const response = await api.get<FunnelData[]>('/api/stats/funnel')
    return response.data
  },

  // Получить статистику по стоимости
  getCosts: async (): Promise<CostsData> => {
    const response = await api.get<CostsData>('/api/stats/costs')
    return response.data
  },

  // Получить бизнес-метрики
  getBusinessMetrics: async (): Promise<BusinessMetrics> => {
    const response = await api.get<BusinessMetrics>('/api/stats/business')
    return response.data
  },

  // Получить распределение по каналам
  getChannelDistribution: async (): Promise<ChannelDistribution> => {
    const response = await api.get<ChannelDistribution>('/api/stats/channels')
    return response.data
  },

  // Получить расширенную воронку
  getEnhancedFunnel: async (): Promise<EnhancedFunnel> => {
    const response = await api.get<EnhancedFunnel>('/api/stats/funnel-enhanced')
    return response.data
  },

  // Получить динамику потенциальных заказов
  getOrderLeadsTimeline: async (
    dateFrom?: string,
    dateTo?: string
  ): Promise<TimelineData[]> => {
    const params = new URLSearchParams()
    if (dateFrom) params.append('date_from', dateFrom)
    if (dateTo) params.append('date_to', dateTo)

    const response = await api.get<TimelineData[]>(
      `/api/stats/order-leads-timeline?${params.toString()}`
    )
    return response.data
  },
}


