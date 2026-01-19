import api from '../api'

export interface SecretStatus {
  is_set: boolean
}

export interface Settings {
  openrouter_token?: SecretStatus
  telegram_bot_token?: SecretStatus
  // Gmail settings
  smtp_user?: string
  smtp_password?: SecretStatus
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

  updateSettings: async (settings: Omit<Settings, "openrouter_token" | "telegram_bot_token" | "smtp_password">): Promise<SettingsResponse> => {
    const response = await api.put<SettingsResponse>('/api/settings', settings as any)
    return response.data
  },

  updateSecrets: async (secrets: { openrouter_token?: string; telegram_bot_token?: string; smtp_password?: string }): Promise<SettingsResponse> => {
    const response = await api.put<SettingsResponse>('/api/settings/secrets', secrets)
    return response.data
  },

  changeAdminPassword: async (payload: { current_password: string; new_password: string }): Promise<{ status: string }> => {
    const response = await api.put<{ status: string }>('/api/auth/change-password', payload)
    return response.data
  },
}


