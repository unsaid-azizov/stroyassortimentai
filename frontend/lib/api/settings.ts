import api from '../api'

export interface Settings {
  openrouter_token?: string
  telegram_bot_token?: string
  // Gmail settings
  smtp_user?: string
  smtp_password?: string
  sales_email?: string
  imap_server?: string
  imap_port?: number
  smtp_server?: string
  smtp_port?: number
}

export interface SettingsResponse {
  settings: Settings
}

export const settingsApi = {
  getSettings: async (): Promise<SettingsResponse> => {
    const response = await api.get<SettingsResponse>('/api/settings')
    return response.data
  },

  updateSettings: async (settings: Settings): Promise<SettingsResponse> => {
    const response = await api.put<SettingsResponse>('/api/settings', settings)
    return response.data
  },
}


