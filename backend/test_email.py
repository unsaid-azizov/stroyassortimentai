#!/usr/bin/env python3
"""Тестовая отправка email через Yandex SMTP"""
import asyncio
import aiosmtplib
from email.message import EmailMessage
import os
from dotenv import load_dotenv

load_dotenv()

async def test_send_email():
    """Отправка тестового письма"""

    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    sales_email = os.getenv("SALES_EMAIL")

    print(f"Настройки SMTP:")
    print(f"  Сервер: {smtp_server}:{smtp_port}")
    print(f"  От кого: {smtp_user}")
    print(f"  Кому: {sales_email}")
    print()

    # Создаем простое письмо
    message = EmailMessage()
    message["From"] = smtp_user
    message["To"] = sales_email
    message["Subject"] = "ТЕСТ | Проверка отправки с bot@stroyassortiment.ru"
    message.set_content("Это тестовое письмо для проверки отправки с нового адреса bot@stroyassortiment.ru через Yandex SMTP.")

    try:
        print(f"Отправка email на {sales_email}...")

        # Port 465 uses SSL
        if smtp_port == 465:
            await aiosmtplib.send(
                message,
                hostname=smtp_server,
                port=smtp_port,
                username=smtp_user,
                password=smtp_password,
                use_tls=True
            )
        else:
            await aiosmtplib.send(
                message,
                hostname=smtp_server,
                port=smtp_port,
                username=smtp_user,
                password=smtp_password,
                start_tls=True
            )

        print("✅ Email успешно отправлен!")
        return True

    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_send_email())
    exit(0 if success else 1)
