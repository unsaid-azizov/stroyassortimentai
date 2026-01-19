'use client'

import { useState } from 'react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { Button } from '@/components/ui/button'
import type { LeadsFilters } from '@/lib/api/leads'

interface LeadsFiltersProps {
  filters: LeadsFilters
  onFiltersChange: (filters: Partial<LeadsFilters>) => void
}

export function LeadsFilters({ filters, onFiltersChange }: LeadsFiltersProps) {
  const [search, setSearch] = useState(filters.search || '')

  const handleSearch = () => {
    onFiltersChange({ search: search || undefined })
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Поиск */}
        <div className="space-y-2">
          <Label htmlFor="search">Поиск</Label>
          <div className="flex gap-2">
            <Input
              id="search"
              placeholder="Имя, телефон, email..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            />
            <Button onClick={handleSearch}>Найти</Button>
          </div>
        </div>

        {/* Канал */}
        <div className="space-y-2">
          <Label htmlFor="channel">Канал</Label>
          <Select
            value={filters.channel || 'all'}
            onValueChange={(value) =>
              onFiltersChange({ channel: value === 'all' ? undefined : value })
            }
          >
            <SelectTrigger id="channel">
              <SelectValue placeholder="Все каналы" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Все каналы</SelectItem>
              <SelectItem value="telegram">Telegram</SelectItem>
              <SelectItem value="email">Email</SelectItem>
              <SelectItem value="avito">Avito</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Статус */}
        <div className="space-y-2">
          <Label htmlFor="status">Статус</Label>
          <Select
            value={filters.status || 'all'}
            onValueChange={(value) =>
              onFiltersChange({ status: value === 'all' ? undefined : value })
            }
          >
            <SelectTrigger id="status">
              <SelectValue placeholder="Все статусы" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Все статусы</SelectItem>
              <SelectItem value="AI_ONLY">Только AI</SelectItem>
              <SelectItem value="HUMAN_INTERVENTION">Требует человека</SelectItem>
              <SelectItem value="CLOSED">Закрыт</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Фильтры по наличию данных */}
        <div className="space-y-2">
          <Label>Наличие данных</Label>
          <div className="flex gap-4">
            <div className="flex items-center space-x-2">
              <Checkbox
                id="has_phone"
                checked={filters.has_phone === true}
                onCheckedChange={(checked) =>
                  onFiltersChange({
                    has_phone: checked ? true : undefined,
                  })
                }
              />
              <Label htmlFor="has_phone" className="text-sm font-normal">
                Телефон
              </Label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="has_email"
                checked={filters.has_email === true}
                onCheckedChange={(checked) =>
                  onFiltersChange({
                    has_email: checked ? true : undefined,
                  })
                }
              />
              <Label htmlFor="has_email" className="text-sm font-normal">
                Email
              </Label>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}




