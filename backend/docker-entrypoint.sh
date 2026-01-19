#!/bin/bash
# Entrypoint скрипт для api - инициализирует БД при первом запуске

set -e

# Настройка WireGuard для доступа к 1С API
if [ -f "/app/data/prg1c.conf" ]; then
  echo "Настройка WireGuard VPN для доступа к 1С..."
  wg-quick up /app/data/prg1c.conf || echo "WireGuard уже запущен или ошибка подключения"
fi

echo "Ожидание готовности PostgreSQL..."
until uv run python check_db.py 2>/dev/null; do
  echo "PostgreSQL еще не готов, ждем..."
  sleep 2
done

echo "Инициализация базы данных..."
uv run python -m db.init_db || echo "БД уже инициализирована или ошибка (это нормально)"

echo "Создание администратора (если не существует)..."
uv run python -m db.create_admin || echo "Администратор уже существует или ошибка (это нормально)"

echo "Запуск AI Service..."
exec uv run uvicorn api:app --host 0.0.0.0 --port 5537

