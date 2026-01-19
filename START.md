# Инструкция по запуску CRM панели

## Быстрый старт

### 1. Проверка окружения

Убедитесь, что у вас есть файл `.env` в корне проекта с необходимыми переменными:

```bash
# Telegram Bot
BOT_TOKEN="your_bot_token"

# OpenAI / OpenRouter
OPENAI_BASE_URL="https://openrouter.ai/api/v1"
OPENAI_API_KEY="your_api_key"
MAIN_LLM="openai/gpt-5-mini"
BACKUP_LLM="google/gemini-2.5-flash"

# Gmail / Email Service
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SALES_EMAIL=your_email@gmail.com
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# PostgreSQL
POSTGRES_USER=said
POSTGRES_PASSWORD=said
POSTGRES_DB=said_crm

# JWT и админ
JWT_SECRET=your-secret-key-change-in-production
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin1234
```

### 2. Запуск через Docker Compose (рекомендуется)

```bash
# Остановить все контейнеры (если запущены)
docker-compose down

# Запустить все сервисы
docker-compose up -d

# Просмотр логов
docker-compose logs -f
```

Сервисы будут доступны:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:5537
- **PostgreSQL**: localhost:5433

### 3. Первый вход

1. Откройте http://localhost:3000
2. Войдите с учетными данными администратора:
   - Username: `admin`
   - Password: `admin1234`

Или зарегистрируйте нового пользователя через `/signup`

### 4. Структура панели

После входа вы увидите:

- **Главная** (`/dashboard`) - бизнес-метрики:
  - Потенциальных заказов
  - Новых лидов (сегодня/неделя)
  - Экономия времени (AI-обработанные сообщения)
  - Активных диалогов
  - Воронка продаж
  - Распределение по каналам
  - Метрики эффективности

- **Менеджер продаж** (`/sales-manager`) - настройки агента:
  - Редактор промпта
  - Редактор базы знаний
  - Перезагрузка агента

- **Лиды** (`/leads`) - список всех лидов

- **HR** и **Бухгалтер** - в разработке (показывают модалку)

## Локальный запуск (без Docker)

### Backend

```bash
cd backend

# Установка зависимостей (если еще не установлены)
uv sync

# Активация окружения
source .venv/bin/activate  # или на Windows: .venv\Scripts\activate

# Запуск сервиса
uv run uvicorn api:app --host 0.0.0.0 --port 5537 --reload
```

### Frontend

```bash
cd frontend

# Установка зависимостей (если еще не установлены)
npm install

# Запуск dev сервера
npm run dev
```

## Проверка работы

### 1. Проверка API

```bash
# Health check
curl http://localhost:5537/health

# Проверка авторизации (должен вернуть 401 без токена)
curl http://localhost:5537/api/auth/me
```

### 2. Проверка базы данных

```bash
# Подключение к PostgreSQL
docker exec -it said_postgres psql -U said -d said_crm

# Проверка таблиц
\dt

# Проверка пользователей
SELECT username, email, created_at FROM users;
```

### 3. Проверка логов

```bash
# Логи всех сервисов
docker-compose logs -f

# Логи конкретного сервиса
docker-compose logs -f api
docker-compose logs -f bot
docker-compose logs -f gmail_service
```

## Решение проблем

### Проблема: Frontend не может подключиться к API

**Решение**: Проверьте, что:
1. Backend запущен на порту 5537
2. В `frontend/.env.local` указан правильный `NEXT_PUBLIC_API_URL`
3. CORS настроен в `backend/api.py`

### Проблема: Ошибка авторизации

**Решение**: 
1. Проверьте, что `JWT_SECRET` установлен в `.env`
2. Пересоздайте админа: `docker-compose exec api python -m db.create_admin`

### Проблема: База данных не инициализирована

**Решение**:
```bash
# Инициализация БД
docker-compose exec api python -m db.init_db

# Создание админа
docker-compose exec api python -m db.create_admin
```

### Проблема: Порты заняты

**Решение**: Измените порты в `docker-compose.yml`:
- Frontend: измените `3000:3000` на другой порт
- Backend: измените `5537:5537` на другой порт
- PostgreSQL: измените `5433:5432` на другой порт

## Обновление после изменений

```bash
# Пересборка и перезапуск
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Остановка

```bash
# Остановить все сервисы
docker-compose down

# Остановить и удалить volumes (удалит данные БД!)
docker-compose down -v
```


