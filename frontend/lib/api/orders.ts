import api from '../api'

export interface OrderSubmission {
  id: string
  created_at: string
  client_name: string | null
  client_contact: string | null
  currency: string
  subtotal: number | null
  total: number | null
  items_count: number | null
  status: string
}

export interface OrdersListResponse {
  orders: OrderSubmission[]
  total: number
  page: number
  limit: number
}

export const ordersApi = {
  getOrders: async (params: { page?: number; limit?: number } = {}): Promise<OrdersListResponse> => {
    const qs = new URLSearchParams()
    if (params.page) qs.append('page', String(params.page))
    if (params.limit) qs.append('limit', String(params.limit))
    const response = await api.get<OrdersListResponse>(`/api/orders?${qs.toString()}`)
    return response.data
  },
}



