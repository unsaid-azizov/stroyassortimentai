import api from '../api'

// Типы для лидов
export interface Lead {
  id: string
  external_id: string | null
  channel: string
  username: string | null
  name: string | null
  phone: string | null
  email: string | null
  last_seen: string
}

export interface LeadsListResponse {
  leads: Lead[]
  total: number
  page: number
  limit: number
}

export interface Thread {
  id: string
  lead_id: string
  status: string
  created_at: string
}

export interface Message {
  id: string
  thread_id: string
  sender_role: string
  sender_id: string | null
  content: string
  created_at: string
  ai_stats: {
    category: string
    reasoning: string | null
    tokens_input: number | null
    tokens_output: number | null
    cost: number | null
    ignored: boolean
  } | null
}

export interface ThreadDetail {
  id: string
  lead_id: string
  status: string
  created_at: string
  lead: Lead
  messages: Message[]
}

// Параметры для фильтрации лидов
export interface LeadsFilters {
  channel?: string
  status?: string
  date_from?: string
  date_to?: string
  category?: string
  search?: string
  has_phone?: boolean
  has_email?: boolean
  page?: number
  limit?: number
}

// API функции для лидов
export const leadsApi = {
  // Получить список лидов
  getLeads: async (filters: LeadsFilters = {}): Promise<LeadsListResponse> => {
    const params = new URLSearchParams()
    
    if (filters.channel) params.append('channel', filters.channel)
    if (filters.status) params.append('status', filters.status)
    if (filters.date_from) params.append('date_from', filters.date_from)
    if (filters.date_to) params.append('date_to', filters.date_to)
    if (filters.category) params.append('category', filters.category)
    if (filters.search) params.append('search', filters.search)
    if (filters.has_phone !== undefined) params.append('has_phone', String(filters.has_phone))
    if (filters.has_email !== undefined) params.append('has_email', String(filters.has_email))
    if (filters.page) params.append('page', String(filters.page))
    if (filters.limit) params.append('limit', String(filters.limit))

    const response = await api.get<LeadsListResponse>(
      `/api/leads?${params.toString()}`
    )
    return response.data
  },

  // Получить детали лида
  getLead: async (leadId: string): Promise<Lead> => {
    const response = await api.get<Lead>(`/api/leads/${leadId}`)
    return response.data
  },

  // Получить треды лида
  getThreads: async (leadId?: string, status?: string): Promise<Thread[]> => {
    const params = new URLSearchParams()
    if (leadId) params.append('lead_id', leadId)
    if (status) params.append('status', status)

    const response = await api.get<Thread[]>(
      `/api/threads?${params.toString()}`
    )
    return response.data
  },

  // Получить детали треда
  getThread: async (threadId: string): Promise<ThreadDetail> => {
    const response = await api.get<ThreadDetail>(`/api/threads/${threadId}`)
    return response.data
  },

  // Обновить статус треда
  updateThreadStatus: async (
    threadId: string,
    status: string
  ): Promise<Thread> => {
    const response = await api.patch<Thread>(`/api/threads/${threadId}`, {
      status,
    })
    return response.data
  },
}




