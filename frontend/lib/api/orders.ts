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

export interface OrderSubmissionDetail extends OrderSubmission {
  payload: {
    client_name?: string
    client_contact?: string
    items?: Array<{
      product_code?: string
      product_name: string
      quantity: number
      unit?: string
      unit_price?: number | null
      line_total?: number | null
      availability?: string
      comment?: string
    }>
    pricing?: {
      currency?: string
      subtotal?: number | null
      delivery_cost?: number | null
      discount?: number | null
      total?: number | null
      payment_terms?: string
    }
    dialogue_summary?: {
      summary?: string
      key_points?: string[]
      open_questions?: string[]
      next_steps?: string[]
    }
    delivery_address?: string
    delivery_method?: string
    additional_comments?: string
  }
}

export const ordersApi = {
  getOrders: async (params: { page?: number; limit?: number } = {}): Promise<OrdersListResponse> => {
    const qs = new URLSearchParams()
    if (params.page) qs.append('page', String(params.page))
    if (params.limit) qs.append('limit', String(params.limit))
    const response = await api.get<OrdersListResponse>(`/api/orders?${qs.toString()}`)
    return response.data
  },

  getOrderDetail: async (orderId: string): Promise<OrderSubmissionDetail> => {
    const response = await api.get<OrderSubmissionDetail>(`/api/orders/${orderId}`)
    return response.data
  },
}



