---
name: Gmail Integration for Said Agent
overview: Create a background service to poll Gmail via IMAP, process incoming emails through the AI agent, and reply via SMTP, using the agent's classification to filter spam.
todos:
  - id: add_imap_tools_dep
    content: Добавить imap_tools в pyproject.toml
    status: completed
  - id: add_imap_config
    content: Добавить IMAP настройки в .env.example и .env
    status: completed
  - id: implement_gmail_service_logic
    content: Реализовать gmail_service.py с циклом опроса IMAP и ответами через SMTP
    status: completed
  - id: update_run_sh_for_gmail_service
    content: Интегрировать запуск gmail_service в run.sh
    status: completed
---

# Планирование интеграции Gmail Gate

Интеграция позволит Саиду обрабатывать входящие письма как полноценному менеджеру. Мы будем использовать существующий `ai_service` для «мозгов» и добавим новый коннектор для почты.

## 1. Конфигурация

В `.env` необходимо добавить параметры IMAP для чтения почты (сервер, порт, логин, пароль). Настройки SMTP у нас уже есть.

## 2. Создание Gmail сервиса

Создадим `gmail_service.py`, который будет работать по следующему циклу:

1. Подключение к Gmail через IMAP.
2. Поиск непрочитанных (UNSEEN) сообщений.
3. Для каждого письма:

    - Извлечение адреса отправителя, имени и текста.
    - Запрос к `ai_service` с метаданными `channel: email`.
    - Если ответ не помечен как `ignore`:
        - Отправка ответного письма через SMTP с подписью Саида.
    - Пометка письма как прочитанного.
```mermaid
flowchart TD
    Inbox["Gmail Inbox (IMAP)"] --> GS["gmail_service.py"]
    GS -->|"POST /chat"| AI["ai_service.py"]
    AI -->|"Structured Response"| GS
    GS -->|"Check ignore: false"| Reply{"Нужен ответ?"}
    Reply -->|"Да"| SMTP["Отправка письма (SMTP)"]
    Reply -->|"Нет (Spam/Off-topic)"| Log["Логирование пропуска"]
```


## 3. Обновление управления

Добавим в `run.sh` флаг `--gmail` для отдельного запуска и включим его в `--all`.

## 4. Зависимости

Для удобной работы с почтой предлагаю добавить `imap_tools` в `pyproject.toml`, так как стандартная библиотека `imaplib` очень неудобна для парсинга современных писем.

## Важные файлы для изменения:

- `gmail_service.py` (создание)
- `run.sh` (обновление)
- `.env` (добавление параметров IMAP)
- `pyproject.toml` (добавление imap_tools)