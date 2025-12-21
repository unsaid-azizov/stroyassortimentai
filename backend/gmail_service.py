"""
Сервис для обработки входящих писем через Gmail (IMAP).
Получает письма, отправляет их в AI сервис и отвечает клиенту.
"""
import asyncio
import logging
import os
import json
import httpx
from datetime import datetime
from imap_tools import MailBox, AND
from email.message import EmailMessage
import aiosmtplib
from dotenv import load_dotenv

load_dotenv()

# Настройка логирования
from utils.logger import setup_logging
logger = setup_logging("gmail_service")

# Конфигурация
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
EMAIL_USER = os.getenv("SMTP_USER")
EMAIL_PASS = os.getenv("SMTP_PASSWORD")
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:5537")

async def send_reply(to_email: str, subject: str, body: str, original_msg_id: str = None):
    """Отправка ответного письма через SMTP."""
    msg = EmailMessage()
    msg["From"] = EMAIL_USER
    msg["To"] = to_email
    msg["Subject"] = f"Re: {subject}" if not subject.startswith("Re:") else subject
    
    if original_msg_id:
        msg["In-Reply-To"] = original_msg_id
        msg["References"] = original_msg_id

    msg.set_content(body)

    try:
        await aiosmtplib.send(
            msg,
            hostname=SMTP_SERVER,
            port=SMTP_PORT,
            username=EMAIL_USER,
            password=EMAIL_PASS,
            start_tls=True if SMTP_PORT == 587 else False
        )
        logger.info(f"Reply sent to {to_email}")
    except Exception as e:
        logger.error(f"Error sending email reply: {e}")

async def process_emails():
    """Основной цикл проверки почты."""
    logger.info("Gmail service started. Polling for new emails...")
    
    # Запоминаем время запуска, чтобы обрабатывать только новые письма
    start_time = datetime.now()
    
    # Счетчик последовательных ошибок для экспоненциальной задержки
    consecutive_errors = 0
    max_retry_delay = 300  # Максимальная задержка 5 минут
    
    while True:
        try:
            # Подключаемся к почтовому ящику
            with MailBox(IMAP_SERVER, port=IMAP_PORT).login(EMAIL_USER, EMAIL_PASS, 'INBOX') as mailbox:
                # Ищем непрочитанные письма, пришедшие ПОСЛЕ запуска сервиса
                # mark_seen=False, чтобы письмо не помечалось прочитанным, если Саид упадет с ошибкой
                for msg in mailbox.fetch(AND(seen=False, date_gte=start_time.date()), mark_seen=False):
                    # Дополнительная проверка по времени
                    msg_date = msg.date.replace(tzinfo=None)
                    if msg_date < start_time:
                        continue
                        
                    logger.info(f"New email from: {msg.from_} | Subject: {msg.subject}")
                    
                    # Извлекаем данные
                    client_email = msg.from_
                    client_name = msg.from_values.name or "Клиент"
                    message_text = msg.text or msg.html
                    
                    # Отправляем в AI сервис
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        try:
                            request_data = {
                                "message": message_text,
                                "user_id": client_email,
                                "metadata": {
                                    "first_name": client_name,
                                    "channel": "email",
                                    "email": client_email
                                }
                            }
                            
                            response = await client.post(
                                f"{AI_SERVICE_URL}/chat",
                                json=request_data
                            )
                            response.raise_for_status()
                            result = response.json()
                            
                            ai_response = result.get("response", "")
                            
                            # Если агент не проигнорировал сообщение
                            if ai_response:
                                logger.info(f"AI generated response for {client_email}. Sending reply...")
                                # Получаем Message-ID из заголовков для корректного ответа в треде
                                # imap_tools headers - это словарь, где значения могут быть списками
                                msg_id_headers = msg.headers.get('message-id', [])
                                msg_id = msg_id_headers[0] if msg_id_headers else None
                                await send_reply(client_email, msg.subject, ai_response, msg_id)
                            else:
                                logger.info(f"AI decided to ignore email from {client_email} (Spam/Off-topic)")
                            
                            # Помечаем письмо как прочитанное ТОЛЬКО после успешной обработки или осознанного игнорирования
                            mailbox.flag(msg.uid, '\\Seen', True)
                                
                        except Exception as e:
                            logger.error(f"Error processing email via AI: {e}")
            
                # Сбрасываем счетчик ошибок при успешном подключении
                consecutive_errors = 0
            
            # Ждем перед следующей проверкой
            await asyncio.sleep(30)
            
        except (ConnectionError, OSError, TimeoutError) as e:
            # Сетевые ошибки - временные проблемы
            consecutive_errors += 1
            retry_delay = min(60 * (2 ** (consecutive_errors - 1)), max_retry_delay)
            logger.warning(f"Network error connecting to IMAP server (attempt {consecutive_errors}): {e}. Retrying in {retry_delay}s...")
            await asyncio.sleep(retry_delay)
            
        except Exception as e:
            # Другие ошибки (аутентификация, конфигурация и т.д.)
            consecutive_errors += 1
            error_type = type(e).__name__
            logger.error(f"IMAP Error [{error_type}]: {e}")
            
            # Для критических ошибок (не сетевых) используем фиксированную задержку
            retry_delay = min(120 * consecutive_errors, max_retry_delay)
            await asyncio.sleep(retry_delay)

if __name__ == "__main__":
    try:
        asyncio.run(process_emails())
    except KeyboardInterrupt:
        logger.info("Gmail service stopped by user")

