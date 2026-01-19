# SMTP Setup для отправки заказов и вызова менеджера

## Проблема

Агент использует инструменты `call_manager` и `collect_order_info` для отправки заказов/запросов на email отдела продаж, но Gmail отклоняет авторизацию.

## Решение: Google App Passwords

Google требует специальные **App Passwords** для приложений, которые подключаются через SMTP.

### Шаг 1: Создать App Password

1. Перейти: https://myaccount.google.com/apppasswords
2. Выбрать "Mail" или создать для "Other (Custom name)" → "stroyassortiment"
3. Google сгенерирует 16-символьный пароль: `xxxx xxxx xxxx xxxx`

### Шаг 2: Обновить `.env`

```env
SMTP_USER=stazizovs@gmail.com
SMTP_PASSWORD=nicwoqxwgpvjaoyz  # БЕЗ пробелов! Слитно!
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SALES_EMAIL=astexlab@gmail.com
```

**ВАЖНО:** Записывайте App Password **без пробелов** - слитно 16 символов.

### Шаг 3: Пересоздать контейнеры

```bash
docker compose down api
docker compose up -d api
```

## Проверка работоспособности

### Тест SMTP подключения

```bash
docker exec api python -c "
import asyncio
import aiosmtplib
import os
from email.message import EmailMessage

async def test_smtp():
    msg = EmailMessage()
    msg['From'] = os.getenv('SMTP_USER')
    msg['To'] = os.getenv('SALES_EMAIL')
    msg['Subject'] = 'Test SMTP Connection'
    msg.set_content('Test email from consultant bot')

    try:
        await aiosmtplib.send(
            msg,
            hostname=os.getenv('SMTP_SERVER'),
            port=int(os.getenv('SMTP_PORT', 587)),
            username=os.getenv('SMTP_USER'),
            password=os.getenv('SMTP_PASSWORD'),
            start_tls=True
        )
        print('✅ SMTP connection successful!')
    except Exception as e:
        print(f'❌ SMTP failed: {e}')

asyncio.run(test_smtp())
"
```

Ожидаемый результат: `✅ SMTP connection successful!`

### Проверить логи агента

```bash
docker logs api 2>&1 | grep -i "email\|smtp\|handover"
```

## Инструменты агента, использующие email

### 1. `call_manager` ([backend/tools/sales_tools.py:380](../backend/tools/sales_tools.py#L380))

Вызывает живого менеджера когда:
- Клиент просит связаться с менеджером
- Агент не может ответить на вопрос
- Нужно человеческое вмешательство

**Письмо включает:**
- Краткое саммари диалога
- Приоритет (низкий/средний/высокий)
- Контактные данные клиента
- Детальная информация о заказе (если есть)

### 2. `collect_order_info` ([backend/tools/sales_tools.py:474](../backend/tools/sales_tools.py#L474))

Оформляет предварительную заявку на заказ когда:
- Клиент предоставил имя и контакт
- Определился с товарами
- Готов оформить заказ

**Письмо включает:**
- Позиции заказа с кодами 1С
- Актуальные цены и остатки
- Итоговая сумма
- Адрес доставки / способ получения

## Troubleshooting

### Ошибка: "Username and Password not accepted"

**Причина:** Используется обычный пароль Gmail вместо App Password

**Решение:**
1. Создать App Password (см. выше)
2. Обновить `SMTP_PASSWORD` в `.env`
3. Пересоздать контейнер: `docker compose down api && docker compose up -d api`

### Ошибка: "Authentication Required"

**Причина:** 2FA не включена на аккаунте Gmail

**Решение:**
1. Включить 2FA: https://myaccount.google.com/security
2. Создать App Password (доступен только с 2FA)

### Ошибка: Пароль правильный, но все равно не работает

**Причина:** Docker не подхватил новые переменные из `.env`

**Решение:**
```bash
# Остановить все контейнеры
docker compose down

# Запустить заново (переменные загрузятся из .env)
docker compose up -d
```

### Ошибка: Письма не приходят, но ошибок нет

**Причина:** Письма попадают в Spam

**Решение:**
1. Проверить папку Spam в Gmail
2. Отметить письмо как "Not Spam"
3. Создать фильтр: все письма от `stazizovs@gmail.com` → входящие

### Проверить что переменные загрузились

```bash
docker exec api env | grep SMTP
```

Должно вывести:
```
SMTP_USER=stazizovs@gmail.com
SMTP_PASSWORD=nicwoqxwgpvjaoyz
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
```

## Альтернативные решения

### Использовать другой SMTP провайдер

#### SendGrid

```env
SMTP_SERVER=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=<your-sendgrid-api-key>
```

#### Mailgun

```env
SMTP_SERVER=smtp.mailgun.org
SMTP_PORT=587
SMTP_USER=<your-mailgun-username>
SMTP_PASSWORD=<your-mailgun-password>
```

#### Yandex Mail

```env
SMTP_SERVER=smtp.yandex.ru
SMTP_PORT=465
SMTP_USER=<your-yandex-email>
SMTP_PASSWORD=<your-yandex-password>
```

## Безопасность

- ⚠️ App Passwords дают **полный доступ** к аккаунту Gmail
- ⚠️ НЕ коммитить `.env` в git (уже в `.gitignore`)
- ✅ Использовать отдельный Gmail аккаунт для бота (не личный)
- ✅ Периодически ротировать App Passwords

## Email шаблоны

Агент использует HTML шаблоны в корпоративном стиле:
- Зеленый header (#26a65b)
- Чистый минималистичный дизайн
- Адаптивный layout (работает на мобильных)

Шаблон: [backend/tools/sales_tools.py:273](../backend/tools/sales_tools.py#L273) функция `render_email_html()`

## Логирование

Все отправки email логируются:

```python
logger.info(f"Отправка email на {sales_email}...")
await aiosmtplib.send(...)
logger.info("Email успешно отправлен.")
```

Проверить логи:
```bash
docker logs api 2>&1 | grep "Отправка email\|Email успешно"
```

## Статусы заказов в БД

Каждая попытка отправки заказа сохраняется в PostgreSQL ([backend/tools/sales_tools.py:92](../backend/tools/sales_tools.py#L92)):

```python
await _persist_order_submission(order, status="SENT")   # Успешно
await _persist_order_submission(order, status="FAILED", error=str(e))  # Ошибка
```

Таблица: `order_submissions` (см. [backend/db/models.py](../backend/db/models.py))

Посмотреть через CRM dashboard: http://localhost:3000/dashboard
