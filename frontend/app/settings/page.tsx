"use client"

import * as React from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { IconEye, IconEyeOff, IconKey, IconMail } from "@tabler/icons-react"

import { AppSidebar } from "@/components/app-sidebar"
import { SiteHeader } from "@/components/site-header"
import {
  SidebarInset,
  SidebarProvider,
} from "@/components/ui/sidebar"
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { settingsApi } from "@/lib/api/settings"

export default function SettingsPage() {
  const queryClient = useQueryClient()
  const [token, setToken] = React.useState("")
  const [showToken, setShowToken] = React.useState(false)
  const [botToken, setBotToken] = React.useState("")
  const [showBotToken, setShowBotToken] = React.useState(false)
  // Gmail settings
  const [smtpUser, setSmtpUser] = React.useState("")
  const [smtpPassword, setSmtpPassword] = React.useState("")
  const [showSmtpPassword, setShowSmtpPassword] = React.useState(false)
  const [salesEmail, setSalesEmail] = React.useState("")
  const [imapServer, setImapServer] = React.useState("imap.gmail.com")
  const [imapPort, setImapPort] = React.useState("993")
  const [smtpServer, setSmtpServer] = React.useState("smtp.gmail.com")
  const [smtpPort, setSmtpPort] = React.useState("587")
  const [isDirty, setIsDirty] = React.useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: () => settingsApi.getSettings(),
  })

  // Обрабатываем данные при их загрузке
  React.useEffect(() => {
    if (data?.settings) {
      if (data.settings.openrouter_token) {
        setToken(data.settings.openrouter_token)
      }
      if (data.settings.telegram_bot_token) {
        setBotToken(data.settings.telegram_bot_token)
      }
      if (data.settings.smtp_user) {
        setSmtpUser(data.settings.smtp_user)
      }
      if (data.settings.smtp_password) {
        setSmtpPassword(data.settings.smtp_password)
      }
      if (data.settings.sales_email) {
        setSalesEmail(data.settings.sales_email)
      }
      if (data.settings.imap_server) {
        setImapServer(data.settings.imap_server)
      }
      if (data.settings.imap_port) {
        setImapPort(String(data.settings.imap_port))
      }
      if (data.settings.smtp_server) {
        setSmtpServer(data.settings.smtp_server)
      }
      if (data.settings.smtp_port) {
        setSmtpPort(String(data.settings.smtp_port))
      }
    }
  }, [data])

  const { mutate: saveSettings, isPending } = useMutation({
    mutationFn: () => {
      const settings: Record<string, any> = {}
      
      // Добавляем только непустые значения
      if (token.trim()) settings.openrouter_token = token.trim()
      if (botToken.trim()) settings.telegram_bot_token = botToken.trim()
      if (smtpUser.trim()) settings.smtp_user = smtpUser.trim()
      if (smtpPassword.trim()) settings.smtp_password = smtpPassword.trim()
      if (salesEmail.trim()) settings.sales_email = salesEmail.trim()
      if (imapServer.trim()) settings.imap_server = imapServer.trim()
      if (imapPort.trim()) {
        const port = parseInt(imapPort.trim(), 10)
        if (!isNaN(port)) settings.imap_port = port
      }
      if (smtpServer.trim()) settings.smtp_server = smtpServer.trim()
      if (smtpPort.trim()) {
        const port = parseInt(smtpPort.trim(), 10)
        if (!isNaN(port)) settings.smtp_port = port
      }
      
      return settingsApi.updateSettings(settings)
    },
    onSuccess: () => {
      setIsDirty(false)
      queryClient.invalidateQueries({ queryKey: ["settings"] })
    },
    onError: (error) => {
      console.error("Ошибка сохранения настроек:", error)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!isDirty) return
    saveSettings()
  }

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
            <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6 px-4 lg:px-6 max-w-3xl">
              <Card>
                <CardHeader>
                  <CardTitle>Настройки интеграций</CardTitle>
                  <CardDescription>
                    Управляйте подключением к OpenRouter. Токен хранится на сервере и не отображается без вашего подтверждения.
                  </CardDescription>
                </CardHeader>
                <form onSubmit={handleSubmit}>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="openrouter-token">OpenRouter API ключ</Label>
                      <div className="relative">
                        <Input
                          id="openrouter-token"
                          type={showToken ? "text" : "password"}
                          placeholder="sk-or-..."
                          value={token}
                          onChange={(e) => {
                            setToken(e.target.value)
                            setIsDirty(true)
                          }}
                          disabled={isLoading || isPending}
                          className="pr-10"
                        />
                        <button
                          type="button"
                          onClick={() => setShowToken((v) => !v)}
                          className="absolute inset-y-0 right-0 flex items-center pr-3 text-muted-foreground hover:text-foreground"
                        >
                          {showToken ? (
                            <IconEyeOff className="h-4 w-4" />
                          ) : (
                            <IconEye className="h-4 w-4" />
                          )}
                          <span className="sr-only">
                            {showToken ? "Скрыть токен" : "Показать токен"}
                          </span>
                        </button>
                      </div>
                      <p className="text-xs text-muted-foreground flex items-center gap-1">
                        <IconKey className="h-3 w-3" />
                        Токен используется для вызовов моделей через OpenRouter.
                      </p>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="telegram-bot-token">Telegram Bot токен</Label>
                      <div className="relative">
                        <Input
                          id="telegram-bot-token"
                          type={showBotToken ? "text" : "password"}
                          placeholder="1234567890:AA..."
                          value={botToken}
                          onChange={(e) => {
                            setBotToken(e.target.value)
                            setIsDirty(true)
                          }}
                          disabled={isLoading || isPending}
                          className="pr-10"
                        />
                        <button
                          type="button"
                          onClick={() => setShowBotToken((v) => !v)}
                          className="absolute inset-y-0 right-0 flex items-center pr-3 text-muted-foreground hover:text-foreground"
                        >
                          {showBotToken ? (
                            <IconEyeOff className="h-4 w-4" />
                          ) : (
                            <IconEye className="h-4 w-4" />
                          )}
                          <span className="sr-only">
                            {showBotToken ? "Скрыть токен бота" : "Показать токен бота"}
                          </span>
                        </button>
                      </div>
                      <p className="text-xs text-muted-foreground flex items-center gap-1">
                        <IconKey className="h-3 w-3" />
                        Используется для подключения Telegram-бота.
                      </p>
                    </div>
                  </CardContent>
                  <CardFooter className="flex justify-end gap-2">
                    <Button
                      type="submit"
                      disabled={!isDirty || isPending}
                    >
                      {isPending ? "Сохраняем..." : "Сохранить"}
                    </Button>
                  </CardFooter>
                </form>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Настройки Gmail</CardTitle>
                  <CardDescription>
                    Настройки для подключения к Gmail через IMAP и SMTP. Используется для обработки входящих писем и отправки ответов.
                  </CardDescription>
                </CardHeader>
                <form onSubmit={handleSubmit}>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="smtp-user">Email (SMTP User)</Label>
                        <Input
                          id="smtp-user"
                          type="email"
                          placeholder="your-email@gmail.com"
                          value={smtpUser}
                          onChange={(e) => {
                            setSmtpUser(e.target.value)
                            setIsDirty(true)
                          }}
                          disabled={isLoading || isPending}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="sales-email">Email для продаж</Label>
                        <Input
                          id="sales-email"
                          type="email"
                          placeholder="sales@example.com"
                          value={salesEmail}
                          onChange={(e) => {
                            setSalesEmail(e.target.value)
                            setIsDirty(true)
                          }}
                          disabled={isLoading || isPending}
                        />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="smtp-password">Пароль приложения Gmail</Label>
                      <div className="relative">
                        <Input
                          id="smtp-password"
                          type={showSmtpPassword ? "text" : "password"}
                          placeholder="Введите пароль приложения"
                          value={smtpPassword}
                          onChange={(e) => {
                            setSmtpPassword(e.target.value)
                            setIsDirty(true)
                          }}
                          disabled={isLoading || isPending}
                          className="pr-10"
                        />
                        <button
                          type="button"
                          onClick={() => setShowSmtpPassword((v) => !v)}
                          className="absolute inset-y-0 right-0 flex items-center pr-3 text-muted-foreground hover:text-foreground"
                        >
                          {showSmtpPassword ? (
                            <IconEyeOff className="h-4 w-4" />
                          ) : (
                            <IconEye className="h-4 w-4" />
                          )}
                          <span className="sr-only">
                            {showSmtpPassword ? "Скрыть пароль" : "Показать пароль"}
                          </span>
                        </button>
                      </div>
                      <p className="text-xs text-muted-foreground flex items-center gap-1">
                        <IconMail className="h-3 w-3" />
                        Используйте пароль приложения из настроек безопасности Google.
                      </p>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="imap-server">IMAP сервер</Label>
                        <Input
                          id="imap-server"
                          type="text"
                          placeholder="imap.gmail.com"
                          value={imapServer}
                          onChange={(e) => {
                            setImapServer(e.target.value)
                            setIsDirty(true)
                          }}
                          disabled={isLoading || isPending}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="imap-port">IMAP порт</Label>
                        <Input
                          id="imap-port"
                          type="number"
                          placeholder="993"
                          value={imapPort}
                          onChange={(e) => {
                            setImapPort(e.target.value)
                            setIsDirty(true)
                          }}
                          disabled={isLoading || isPending}
                        />
                      </div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="smtp-server">SMTP сервер</Label>
                        <Input
                          id="smtp-server"
                          type="text"
                          placeholder="smtp.gmail.com"
                          value={smtpServer}
                          onChange={(e) => {
                            setSmtpServer(e.target.value)
                            setIsDirty(true)
                          }}
                          disabled={isLoading || isPending}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="smtp-port">SMTP порт</Label>
                        <Input
                          id="smtp-port"
                          type="number"
                          placeholder="587"
                          value={smtpPort}
                          onChange={(e) => {
                            setSmtpPort(e.target.value)
                            setIsDirty(true)
                          }}
                          disabled={isLoading || isPending}
                        />
                      </div>
                    </div>
                  </CardContent>
                  <CardFooter className="flex justify-end gap-2">
                    <Button
                      type="submit"
                      disabled={!isDirty || isPending}
                    >
                      {isPending ? "Сохраняем..." : "Сохранить"}
                    </Button>
                  </CardFooter>
                </form>
              </Card>
            </div>
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}


