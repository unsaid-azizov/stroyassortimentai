"""
Инструменты для активных продаж и взаимодействия с менеджером.
Включает вызов менеджера и сбор данных для оформления заказа с отправкой на Email в красивом HTML формате.
"""
import os
import asyncio
import logging
from typing import Optional, Dict
from email.message import EmailMessage

import aiosmtplib
from langchain.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Цвета бренда из скриншота
BRAND_GREEN = "#26a65b"
BRAND_DARK = "#333333"
BG_LIGHT = "#f8f9fa"

def render_email_html(title: str, subtitle: str, fields: Dict[str, str], footer_text: str) -> str:
    """Генерирует чистый, минималистичный HTML-шаблон в стиле сайта."""
    items_html = ""
    for label, value in fields.items():
        if value:
            # Выносим replace в отдельную переменную, т.к. в f-string нельзя использовать обратный слэш
            value_html = value.replace('\n', '<br>')
            items_html += f"""
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #eeeeee;">
                    <div style="font-size: 12px; color: #888888; text-transform: uppercase; margin-bottom: 4px;">{label}</div>
                    <div style="font-size: 16px; color: {BRAND_DARK}; font-weight: 500;">{value_html}</div>
                </td>
            </tr>
            """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: {BRAND_DARK}; background-color: {BG_LIGHT}; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
            .header {{ background-color: {BRAND_GREEN}; padding: 30px; text-align: center; color: #ffffff; }}
            .content {{ padding: 30px; }}
            .footer {{ background: #f1f1f1; padding: 20px; text-align: center; font-size: 12px; color: #777777; }}
            table {{ width: 100%; border-collapse: collapse; }}
            h1 {{ margin: 0; font-size: 22px; font-weight: 600; letter-spacing: 1px; }}
            .subtitle {{ font-size: 14px; opacity: 0.9; margin-top: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{title}</h1>
                <div class="subtitle">{subtitle}</div>
            </div>
            <div class="content">
                <table>
                    {items_html}
                </table>
            </div>
            <div class="footer">
                {footer_text}<br>
                © 2025 СтройАссортимент | Мытищи, Осташковское шоссе 14
            </div>
        </div>
    </body>
    </html>
    """

class OrderInfo(BaseModel):
    client_name: str = Field(description="Имя клиента")
    client_contact: str = Field(description="Контактные данные (телефон или email)")
    product_details: str = Field(description="Что именно заказывает клиент (название, объем, размеры)")
    main_product: str = Field(description="Название основного товара для заголовка письма (например, 'Лиственница', 'Доска обрезная')")
    estimated_volume: str = Field(description="Кратко объем заказа для заголовка (например, '15 м3', '2 куба', '100 шт')")
    delivery_address: Optional[str] = Field(None, description="Адрес доставки, если клиент его указал")
    additional_comments: Optional[str] = Field(None, description="Дополнительные пожелания клиента")

class ManagerHandover(BaseModel):
    client_summary: str = Field(description="Краткое описание того, что хочет клиент и на чем остановился диалог")
    priority: str = Field(description="Приоритет: 'низкий', 'средний', 'высокий'. Определи на основе срочности и объема заказа.")
    main_topic: str = Field(description="Тема обращения одним-двумя словами для заголовка (например, 'Лиственница', 'Оплата', 'Брак')")
    client_name: str = Field(description="Имя клиента")
    client_contact: Optional[str] = Field(None, description="Контактные данные клиента, если он их оставил")

@tool
async def call_manager(handover: ManagerHandover) -> str:
    """
    Вызывает живого менеджера для помощи клиенту. 
    Обязательно составь краткое саммари для менеджера и выдели тему (main_topic).
    """
    sales_email = os.getenv("SALES_EMAIL")
    if not sales_email:
        return "Ошибка конфигурации: почта отдела продаж не настроена."

    priority_map = {"высокий": "ВЫСОКИЙ", "средний": "СРЕДНИЙ", "низкий": "НИЗКИЙ"}
    priority_label = priority_map.get(handover.priority.lower(), handover.priority.upper())

    subject = f"ВЫЗОВ МЕНЕДЖЕРА | {priority_label} | {handover.main_topic} | {handover.client_name}"
    
    fields = {
        "Клиент": handover.client_name,
        "Контакты": handover.client_contact or "Не указаны",
        "Приоритет": priority_label,
        "Тема": handover.main_topic,
        "Краткое содержание диалога": handover.client_summary
    }

    html_body = render_email_html(
        "ВЫЗОВ МЕНЕДЖЕРА",
        "Требуется подключение специалиста к диалогу",
        fields,
        "Сообщение сформировано автоматически системой Саид-ИИ"
    )

    message = EmailMessage()
    message["From"] = os.getenv("SMTP_USER")
    message["To"] = sales_email
    message["Subject"] = subject
    message.set_content(f"Вызов менеджера: {handover.client_name} - {handover.main_topic}") # Plain text fallback
    message.add_alternative(html_body, subtype='html')

    try:
        await aiosmtplib.send(message, hostname=os.getenv("SMTP_SERVER"), port=int(os.getenv("SMTP_PORT", "587")),
                             username=os.getenv("SMTP_USER"), password=os.getenv("SMTP_PASSWORD"), 
                             start_tls=True if os.getenv("SMTP_PORT") == "587" else False)
        return "Менеджер получил ваш запрос и сейчас изучает историю переписки. Он ответит вам в ближайшее время."
    except Exception as e:
        logger.error(f"Handover error: {e}")
        return "Я передал вашу просьбу менеджеру, он скоро подключится."

@tool
async def collect_order_info(order: OrderInfo) -> str:
    """
    Оформляет предварительную заявку на заказ и отправляет её в отдел продаж.
    """
    sales_email = os.getenv("SALES_EMAIL")
    if not sales_email:
        return "Ошибка почты отдела продаж."

    subject = f"ЗАКАЗ | {order.main_product} | {order.estimated_volume} | {order.client_name}"
    
    fields = {
        "Клиент": order.client_name,
        "Контакты": order.client_contact,
        "Основной товар": order.main_product,
        "Объем / Количество": order.estimated_volume,
        "Детали заказа": order.product_details,
        "Адрес доставки": order.delivery_address or "Самовывоз",
        "Дополнительно": order.additional_comments
    }

    html_body = render_email_html(
        "НОВАЯ ЗАЯВКА",
        "Предварительный заказ из чат-бота",
        fields,
        "Заявка сформирована автоматически агентом Саидом"
    )

    message = EmailMessage()
    message["From"] = os.getenv("SMTP_USER")
    message["To"] = sales_email
    message["Subject"] = subject
    message.set_content(f"Новый заказ: {order.client_name} - {order.main_product}") # Plain text fallback
    message.add_alternative(html_body, subtype='html')

    try:
        await aiosmtplib.send(message, hostname=os.getenv("SMTP_SERVER"), port=int(os.getenv("SMTP_PORT", "587")),
                             username=os.getenv("SMTP_USER"), password=os.getenv("SMTP_PASSWORD"),
                             start_tls=True if os.getenv("SMTP_PORT") == "587" else False)
        return f"Благодарю, {order.client_name}! Ваша заявка отправлена в отдел продаж. Менеджер свяжется с вами в ближайшее время."
    except Exception as e:
        logger.error(f"Order error: {e}")
        return "Заявка принята, менеджер увидит ваше сообщение в чате."
