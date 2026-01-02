#!/usr/bin/env python3
"""
Скрипт для генерации секретного ключа для JWT.
"""
import secrets

# Генерируем случайную строку длиной 32 байта (64 символа в hex)
secret = secrets.token_urlsafe(32)

print("Сгенерированный JWT_SECRET:")
print(secret)
print(f"\nДобавь в .env:")
print(f"JWT_SECRET={secret}")




