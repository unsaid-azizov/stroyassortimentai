# Сохранение Username пользователей

## Обзор

Реализовано сохранение Telegram username, имени/фамилии и номера телефона пользователей в базе данных.

## Что сохраняется

### Обязательно (если есть):
- **username** - Telegram username (например `@SherryGarrick_a247`)

### Опционально (если есть):
- **name** - Полное имя (first_name + last_name)
- **phone** - Номер телефона
- **email** - Email адрес

## Изменения в базе данных

### Таблица `leads`

Добавлена новая колонка:

```sql
ALTER TABLE leads ADD COLUMN username VARCHAR(255);
CREATE INDEX ix_leads_username ON leads (username);
```

| Колонка      | Тип          | Описание                           |
|--------------|--------------|----------------------------------- |
| username     | VARCHAR(255) | Telegram @username или nickname    |
| name         | VARCHAR(255) | Полное имя пользователя            |
| phone        | VARCHAR(50)  | Номер телефона                     |
| email        | VARCHAR(255) | Email адрес                        |

## Изменения в коде

### Backend

#### [backend/db/models.py](../backend/db/models.py#L17)

```python
class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    channel: Mapped[str] = mapped_column(String(50))
    username: Mapped[Optional[str]] = mapped_column(String(255), index=True)  # ← Новое поле
    name: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
```

#### [backend/db/repository.py](../backend/db/repository.py#L32)

Функция `get_or_create_lead` теперь:
- Принимает параметр `username`
- Обновляет username/name/phone/email при каждом сообщении пользователя

```python
async def get_or_create_lead(
    session: AsyncSession,
    channel: str,
    external_id: str,
    username: Optional[str] = None,  # ← Новый параметр
    name: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None
) -> Lead:
    # ... создание или поиск лида

    # Обновление данных при повторном контакте
    if username and lead.username != username:
        lead.username = username
        updated = True
```

#### [backend/services/ai_router.py](../backend/services/ai_router.py#L49)

Формирует полное имя из first_name и last_name:

```python
first_name = metadata.get("first_name", "")
last_name = metadata.get("last_name", "")
full_name = " ".join(filter(None, [first_name, last_name])) or None

lead = await get_or_create_lead(
    db_session,
    channel=channel,
    external_id=external_id,
    username=metadata.get("username"),  # ← Telegram @username
    name=full_name,
    phone=metadata.get("phone"),
    email=metadata.get("email")
)
```

#### [backend/db/init_db.py](../backend/db/init_db.py#L91)

Автоматическая миграция при запуске:

```python
# Add username column to leads table
try:
    await conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS username VARCHAR(255)"))
    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_leads_username ON leads (username)"))
    print("Миграция leads.username успешно применена.")
except Exception as e:
    print(f"Не удалось применить миграцию leads.username: {e}")
```

### Frontend

#### [frontend/lib/api/leads.ts](../frontend/lib/api/leads.ts#L3)

```typescript
export interface Lead {
  id: string
  external_id: string | null
  channel: string
  username: string | null  // ← Новое поле
  name: string | null
  phone: string | null
  email: string | null
  last_seen: string
}
```

#### [frontend/components/leads-table.tsx](../frontend/components/leads-table.tsx#L56)

Добавлена колонка "Username" в таблицу лидов:

```tsx
<TableHead>Username</TableHead>

// ...

<TableCell>
  {lead.username ? (
    <span className="text-blue-600">@{lead.username.replace(/^@/, '')}</span>
  ) : (
    '-'
  )}
</TableCell>
```

#### [frontend/app/leads/[id]/page.tsx](../frontend/app/leads/[id]/page.tsx#L169)

Добавлено отображение username на странице детального просмотра лида:

```tsx
{lead.username && (
  <div className="flex items-center gap-2">
    <IconMessage className="h-4 w-4 text-muted-foreground" />
    <span className="text-sm text-muted-foreground">Username:</span>
    <span className="text-sm font-medium text-blue-600">
      @{lead.username.replace(/^@/, '')}
    </span>
  </div>
)}
```

## Поиск по username

Функция `get_leads()` в [backend/db/repository.py](../backend/db/repository.py#L162) теперь ищет по username:

```python
if search:
    search_pattern = f"%{search}%"
    conditions.append(
        or_(
            Lead.name.ilike(search_pattern),
            Lead.username.ilike(search_pattern),  # ← Поиск по username
            Lead.phone.ilike(search_pattern),
            Lead.email.ilike(search_pattern)
        )
    )
```

## Применение изменений

### 1. Пересобрать API контейнер

```bash
docker compose up --build -d api
```

### 2. Миграция выполняется автоматически

При запуске контейнера через `docker-entrypoint.sh` автоматически запускается:

```bash
python -m db.init_db
```

Который добавляет колонку `username` если её ещё нет.

### 3. Проверить миграцию

```bash
# Проверить структуру таблицы
docker exec postgres psql -U said -d said_crm -c "\d leads"

# Проверить логи
docker logs api 2>&1 | grep "Миграция leads.username"
```

Должно вывести:
```
Миграция leads.username успешно применена.
```

### 4. Проверить работу

```bash
# Посмотреть данные
docker exec postgres psql -U said -d said_crm -c "SELECT id, external_id, username, name FROM leads LIMIT 5"
```

## Как работает

1. **Telegram бот получает сообщение** ([backend/bot.py](../backend/bot.py#L129))
   - Извлекает `message.from_user.username`
   - Извлекает `message.from_user.first_name`, `message.from_user.last_name`
   - Сохраняет в metadata

2. **AI Router обрабатывает запрос** ([backend/services/ai_router.py](../backend/services/ai_router.py#L49))
   - Формирует полное имя из first_name + last_name
   - Вызывает `get_or_create_lead()` с username

3. **Repository сохраняет/обновляет Lead** ([backend/db/repository.py](../backend/db/repository.py#L32))
   - Создает нового лида с username
   - Или обновляет существующего если username изменился

4. **Frontend отображает username** ([frontend/components/leads-table.tsx](../frontend/components/leads-table.tsx))
   - Показывает username с префиксом `@`
   - Подсвечивает синим цветом

## Примечания

- Username сохраняется для **всех каналов** (telegram, email, avito)
- Для Telegram это `@username`
- Для Email можно дублировать email в username или оставить NULL
- Для Avito это nickname пользователя на платформе
- Username обновляется при каждом сообщении пользователя (если изменился)
- Старые лиды получат username при следующем сообщении от пользователя

## Пример данных

| external_id | channel  | username           | name              |
|-------------|----------|--------------------|-------------------|
| 8272309934  | telegram | @SherryGarrick_a247| Sherry Garrick    |
| 1103652370  | telegram | @said_builder      | Said Stazizov     |
| user@mail   | email    | NULL               | John Doe          |
