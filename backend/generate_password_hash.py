#!/usr/bin/env python3
"""
Скрипт для генерации хеша пароля.
Использование: python generate_password_hash.py "твой_пароль"
"""
import sys
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

if len(sys.argv) < 2:
    password = input("Введите пароль: ")
else:
    password = sys.argv[1]

password_hash = pwd_context.hash(password)
print(f"\nХеш пароля:")
print(password_hash)
print(f"\nДобавь в .env:")
print(f"ADMIN_PASSWORD_HASH={password_hash}")




