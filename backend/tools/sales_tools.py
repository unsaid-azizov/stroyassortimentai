"""
Инструменты для активных продаж и взаимодействия с менеджером.
Включает вызов менеджера и сбор данных для оформления заказа с отправкой на Email в красивом HTML формате.
"""
import os
import asyncio
import logging
from typing import Optional, Dict, List
from email.message import EmailMessage

import aiosmtplib
from langchain.tools import tool
from langchain_core.tools import InjectedToolArg
from pydantic import BaseModel, Field
from typing import Annotated

# Импортируем утилиты для расчета цен с учетом единиц измерения
from utils.price_calculator import parse_unit, calculate_price_per_piece

logger = logging.getLogger(__name__)

# Цвета бренда
BRAND_GREEN = "#26a65b"
BRAND_DARK = "#333333"
BG_LIGHT = "#f8f9fa"

def _fmt_money(amount: Optional[float], currency: str = "RUB") -> str:
    if amount is None:
        return "—"
    try:
        value = float(amount)
    except Exception:
        return str(amount)
    if currency.upper() in ("RUB", "RUR", "₽"):
        return f"{value:,.2f} ₽".replace(",", " ")
    return f"{value:,.2f} {currency}".replace(",", " ")


def _fmt_qty(qty: Optional[float], unit: Optional[str] = None) -> str:
    if qty is None:
        return "—"
    try:
        q = float(qty)
        s = (f"{q:.3f}".rstrip("0").rstrip(".")) or "0"
    except Exception:
        s = str(qty)
    return f"{s} {unit}".strip() if unit else s


class OrderLineItem(BaseModel):
    """Структурированная позиция заказа."""

    product_code: str = Field(
        description="Код номенклатуры/товара (например, '00-00003162') - ОБЯЗАТЕЛЬНО",
    )
    product_name: str = Field(description="Название товара")
    quantity: float = Field(
        description="Количество (число)",
    )
    unit: Optional[str] = Field(None, description="Ед. измерения (шт, м, м2, м3, упак и т.п.)")
    unit_price: Optional[float] = Field(None, description="Цена за единицу (заполнится автоматически из 1С)")
    line_total: Optional[float] = Field(None, description="Итог по позиции (посчитается автоматически)")
    availability: Optional[str] = Field(None, description="Наличие/остатки (заполнится из 1С)")
    comment: Optional[str] = Field(None, description="Примечание по позиции (сорт/влажность/размеры/требования)")


class OrderPricing(BaseModel):
    """Сводка по ценам. Валюта по умолчанию — RUB."""

    currency: str = Field("RUB", description="Валюта (обычно RUB)")
    subtotal: Optional[float] = Field(None, description="Сумма позиций без доставки/скидок (посчитается автоматически)")
    delivery_cost: Optional[float] = Field(None, description="Стоимость доставки, если обсуждалась")
    discount: Optional[float] = Field(None, description="Скидка (если обсуждалась), положительное число")
    total: Optional[float] = Field(None, description="Итого к оплате (посчитается автоматически)")
    payment_terms: Optional[str] = Field(None, description="Условия оплаты (нал/безнал, предоплата и т.д.)")


class DialogueSummary(BaseModel):
    """Детальное резюме диалога для менеджера."""

    summary: str = Field(description="Детальное саммари диалога (1-2 абзаца)")
    key_points: List[str] = Field(default_factory=list, description="Ключевые факты/договоренности списком")
    open_questions: List[str] = Field(default_factory=list, description="Что ещё нужно уточнить у клиента")
    next_steps: List[str] = Field(default_factory=list, description="Рекомендуемые следующие шаги менеджеру")


def _pydantic_dump(obj: BaseModel) -> dict:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return obj.dict()


async def _persist_order_submission(order: "OrderInfo", status: str, error: Optional[str] = None) -> None:
    """Store order in Postgres for dashboard analytics and update lead info."""
    try:
        from db.session import async_session_factory
        from db.models import OrderSubmission, Lead
        from sqlalchemy import select
    except Exception as e:
        logger.warning(f"DB not available for order persistence: {repr(e)}")
        return

    payload = _pydantic_dump(order)
    currency = (order.pricing.currency if order.pricing else "RUB") if getattr(order, "pricing", None) else "RUB"
    subtotal = getattr(order.pricing, "subtotal", None) if getattr(order, "pricing", None) else None
    total = getattr(order.pricing, "total", None) if getattr(order, "pricing", None) else None
    items_count = len(order.items) if getattr(order, "items", None) else None

    async with async_session_factory() as session:
        # 1. Сохраняем заказ
        rec = OrderSubmission(
            client_name=order.client_name,
            client_contact=order.client_contact,
            currency=currency or "RUB",
            subtotal=subtotal,
            total=total,
            items_count=items_count,
            status=status,
            error=error,
            payload=payload,
        )
        session.add(rec)

        # 2. Обновляем данные lead'а (если есть channel_source и contact_username)
        if order.channel_source and order.contact_username:
            try:
                # Ищем lead по username (для telegram это username без @)
                stmt = select(Lead).where(
                    Lead.channel == order.channel_source,
                    Lead.username == order.contact_username
                )
                result = await session.execute(stmt)
                lead = result.scalar_one_or_none()

                if lead:
                    # Обновляем phone/email если они есть в заказе
                    updated = False

                    # Извлекаем phone из client_contact (если это телефон)
                    if order.client_contact and order.client_contact.startswith('+'):
                        if not lead.phone or lead.phone != order.client_contact:
                            lead.phone = order.client_contact
                            updated = True
                            logger.info(f"Updated lead {lead.id} phone: {order.client_contact}")

                    # Извлекаем email из client_contact (если это email)
                    elif order.client_contact and '@' in order.client_contact:
                        if not lead.email or lead.email != order.client_contact:
                            lead.email = order.client_contact
                            updated = True
                            logger.info(f"Updated lead {lead.id} email: {order.client_contact}")

                    if updated:
                        session.add(lead)
            except Exception as e:
                logger.warning(f"Failed to update lead from order: {repr(e)}")

        try:
            await session.commit()
            logger.info(f"Order submission saved: {rec.id}")
        except Exception as e:
            await session.rollback()
            logger.warning(f"Failed to persist order submission: {repr(e)}")


def _fetch_products_from_1c_sync(product_codes: List[str]) -> Dict[str, dict]:
    """
    Синхронная версия получения данных из 1С.
    Использует ту же логику что и get_product_live_details.
    Returns map: code -> {all_1c_fields...}

    Возвращает ВСЕ данные из 1C без фильтрации!
    """
    if not product_codes:
        return {}

    try:
        # Импортируем функцию из get_product_live_details
        from tools.get_product_live_details import fetch_live_product_details

        items = fetch_live_product_details(product_codes)
        out: Dict[str, dict] = {}

        for item in items:
            code = item.get("Код")
            if not code:
                continue

            # ✅ Возвращаем ВСЕ данные из 1C как есть
            # Не фильтруем поля - нам может понадобиться любое из них
            out[code] = item

        return out
    except Exception as e:
        logger.warning(f"Failed to fetch prices from 1C: {repr(e)}")
        return {}


def _calculate_order_totals(order: "OrderInfo") -> "OrderInfo":
    """
    Pure classic calculation:
    - fill line_total = quantity * unit_price when both present
    - compute subtotal as sum(line_total)
    - compute total = subtotal + delivery_cost - discount
    """
    if not order.items:
        return order

    currency = order.pricing.currency if order.pricing else "RUB"
    pricing = order.pricing or OrderPricing(currency=currency)

    subtotal = 0.0
    any_totals = False

    for item in order.items:
        if item.quantity is not None and item.unit_price is not None:
            line_total = round(float(item.quantity) * float(item.unit_price), 2)
            item.line_total = line_total
            subtotal += line_total
            any_totals = True

    if any_totals:
        pricing.subtotal = round(subtotal, 2)
        delivery = float(pricing.delivery_cost or 0.0)
        discount = float(pricing.discount or 0.0)
        pricing.total = round(pricing.subtotal + delivery - discount, 2)

    order.pricing = pricing
    return order


def enrich_and_calculate_order_sync(order: "OrderInfo") -> "OrderInfo":
    """
    Синхронное обогащение + подсчет итогов.
    - Если items имеют product_code но нет unit_price, запрашивает из 1С
    - Правильно конвертирует цены с учетом единиц измерения
    - Считает итоги по позициям и общий итог
    """
    if not order.items:
        return order

    # Проверяем что у всех позиций есть product_code
    missing_codes = [it.product_name for it in order.items if not it.product_code]
    if missing_codes:
        raise ValueError(
            "Для расчёта заказа нужны коды номенклатуры (product_code) по каждой позиции. "
            f"Нет кода у: {', '.join(missing_codes[:5])}"
        )

    # Получаем данные из 1С (теперь получаем ВСЕ поля)
    need_codes = [it.product_code for it in order.items if it.product_code]
    codes_unique = list(dict.fromkeys([c for c in need_codes if c]))

    if codes_unique:
        products = _fetch_products_from_1c_sync(codes_unique)

        for it in order.items:
            if not it.product_code:
                continue

            product_data = products.get(it.product_code)
            if not product_data:
                logger.warning(f"Товар {it.product_code} не найден в 1С")
                continue

            # Получаем базовую цену и единицу из 1C
            base_price = product_data.get("Цена")
            product_unit = product_data.get("ЕдИзмерения", "шт")
            stock = product_data.get("Остаток")

            # Заполняем availability
            if stock:
                it.availability = str(stock)

            # ✅ ПРАВИЛЬНЫЙ РАСЧЕТ ЦЕНЫ С УЧЕТОМ ЕДИНИЦ ИЗМЕРЕНИЯ
            if it.unit_price is None and base_price is not None:
                base_price_float = float(base_price)

                # Парсим единицу измерения из 1C
                base_unit, pieces_per_unit = parse_unit(product_unit)

                # Нормализуем единицу клиента
                client_unit = (it.unit or "шт").lower().strip()
                client_unit_normalized = client_unit if client_unit not in ["штук", "штука", "шт."] else "шт"

                logger.info(f"💰 Price conversion for {it.product_name} ({it.product_code}):")
                logger.info(f"   Base price from 1C: {base_price_float} ₽/{base_unit}")
                logger.info(f"   Product unit: {product_unit}")
                logger.info(f"   Client wants: {it.quantity} {client_unit}")

                # Случай 1: Клиент заказывает в штуках, а товар в м³/м²
                if client_unit_normalized == "шт" and base_unit in ["м3", "м2", "м³", "м²"]:
                    if pieces_per_unit and pieces_per_unit > 0:
                        # Рассчитываем цену за штуку
                        price_per_piece = base_price_float / pieces_per_unit
                        it.unit_price = round(price_per_piece, 2)
                        logger.info(f"   ✅ Converted: {base_price_float}/{pieces_per_unit:.4f} = {it.unit_price} ₽/шт")
                    else:
                        # Нет коэффициента конверсии - используем базовую цену
                        it.unit_price = base_price_float
                        logger.warning(f"   ⚠️  No conversion coefficient, using base price")

                # Случай 2: Единицы совпадают или клиент заказывает в той же ЕИ
                elif client_unit_normalized == base_unit or client_unit_normalized in ["м3", "м2", "м³", "м²"] and base_unit in ["м3", "м2", "м³", "м²"]:
                    it.unit_price = base_price_float
                    logger.info(f"   ✅ Units match, using base price: {it.unit_price} ₽/{base_unit}")

                # Случай 3: Товар продается просто в штуках
                elif base_unit == "шт":
                    it.unit_price = base_price_float
                    logger.info(f"   ✅ Product priced per piece: {it.unit_price} ₽/шт")

                # Случай 4: Неизвестная конвертация - используем базовую цену с предупреждением
                else:
                    it.unit_price = base_price_float
                    logger.warning(f"   ⚠️  Unknown conversion {client_unit} -> {base_unit}, using base price")

    return _calculate_order_totals(order)


def render_email_html(title: str, subtitle: str, fields: Dict[str, str], footer_text: str) -> str:
    """Генерирует красивый структурированный HTML-шаблон с улучшенным дизайном."""
    items_html = ""
    for label, value in fields.items():
        if value and value.strip() and value != "—":  # Skip empty values and dashes
            # Специальная обработка для "Позиции заказа" и блоков с переносами строк
            if label in ("Позиции заказа", "Заказ / позиции", "Цены / Итоги", "Саммари диалога", "Детальное саммари"):
                value_html = value.replace('\n', '<br>')
                items_html += f"""
                <tr>
                    <td style="padding: 20px 0; border-bottom: 1px solid #eeeeee;">
                        <div style="font-size: 11px; color: #888888; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; font-weight: 600;">{label}</div>
                        <div style="font-size: 14px; color: {BRAND_DARK}; line-height: 1.8; background: #f9f9f9; padding: 15px; border-radius: 6px; border-left: 3px solid {BRAND_GREEN};">{value_html}</div>
                    </td>
                </tr>
                """
            else:
                value_html = value.replace('\n', '<br>')
                items_html += f"""
                <tr>
                    <td style="padding: 16px 0; border-bottom: 1px solid #eeeeee;">
                        <div style="font-size: 11px; color: #888888; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; font-weight: 600;">{label}</div>
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
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: {BRAND_DARK}; background-color: {BG_LIGHT}; margin: 0; padding: 20px; }}
            .container {{ max-width: 650px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 8px 24px rgba(0,0,0,0.08); }}
            .header {{ background: linear-gradient(135deg, {BRAND_GREEN} 0%, #229950 100%); padding: 35px 30px; text-align: center; color: #ffffff; }}
            .content {{ padding: 35px 30px; }}
            .footer {{ background: #f5f5f5; padding: 20px; text-align: center; font-size: 12px; color: #888888; border-top: 1px solid #e0e0e0; }}
            table {{ width: 100%; border-collapse: collapse; }}
            h1 {{ margin: 0; font-size: 24px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; }}
            .subtitle {{ font-size: 14px; opacity: 0.95; margin-top: 8px; font-weight: 400; }}
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
                © 2026 СтройАссортимент | Мытищи, Осташковское шоссе 14
            </div>
        </div>
    </body>
    </html>
    """

class OrderInfo(BaseModel):
    client_name: str = Field(description="Имя клиента")
    client_contact: str = Field(description="Контактные данные (телефон или email)")

    # Channel and contact source info
    channel_source: Optional[str] = Field(
        None,
        description="Канал связи откуда пришел клиент (telegram, email, etc.)"
    )
    contact_username: Optional[str] = Field(
        None,
        description="Username в канале связи (например @username в Telegram)"
    )

    # Structured fields
    dialogue_summary: Optional[DialogueSummary] = Field(
        None,
        description="Детальное саммари диалога по заказу (желательно заполнить)",
    )
    items: List[OrderLineItem] = Field(
        default_factory=list,
        description="Позиции заказа (с кодом товара/кол-вом). Цены и итоги посчитаются автоматически из 1С",
    )
    pricing: Optional[OrderPricing] = Field(
        None,
        description="Сводка по ценам/оплате. Итоги посчитаются автоматически, укажи только delivery_cost/discount/payment_terms если обсуждалось",
    )

    delivery_address: Optional[str] = Field(None, description="Адрес доставки, если клиент его указал")
    delivery_method: Optional[str] = Field(None, description="Доставка/самовывоз/ТК и т.п., если обсуждалось")
    additional_comments: Optional[str] = Field(None, description="Дополнительные пожелания клиента")

class ManagerHandover(BaseModel):
    client_summary: str = Field(description="Краткое описание того, что хочет клиент и на чем остановился диалог")

    dialogue_summary: Optional[DialogueSummary] = Field(
        None,
        description="Детальное саммари диалога для менеджера (желательно заполнить)",
    )

    priority: str = Field(description="Приоритет: 'низкий', 'средний', 'высокий'. Определи на основе срочности и объема заказа.")
    main_topic: str = Field(description="Тема обращения 1-2 словами для заголовка (например, 'Лиственница', 'Оплата', 'Брак')")
    client_name: str = Field(description="Имя клиента")
    client_contact: Optional[str] = Field(None, description="Контактные данные клиента, если он их оставил")

    order: Optional[OrderInfo] = Field(
        None,
        description="Если в диалоге уже есть конкретика по заказу — приложи структуру заказа (позиции/цены/итоги). Цены/итоги посчитаются автоматически",
    )

@tool
async def call_manager(handover: ManagerHandover) -> str:
    """
    Вызывает живого менеджера для помощи клиенту.
    Используй когда:
    - Клиент явно просит поговорить с человеком
    - Очень сложный технический вопрос
    - Клиент в раздумьях и нужна консультация
    - Специфические условия (скидки, индивидуальный расчет)

    Обязательно составь краткое саммари для менеджера и выдели тему (main_topic).
    Если в диалоге уже есть конкретика по заказу - укажи order со всеми позициями и кодами товаров.
    """
    sales_email = os.getenv("SALES_EMAIL")
    if not sales_email:
        return "Ошибка конфигурации: почта отдела продаж не настроена."

    # Обогащаем order если есть
    if handover.order and handover.order.items:
        try:
            handover.order = enrich_and_calculate_order_sync(handover.order)
        except Exception as e:
            logger.warning(f"Failed to enrich/calculate handover order: {repr(e)}")

    priority_map = {"высокий": "ВЫСОКИЙ", "средний": "СРЕДНИЙ", "низкий": "НИЗКИЙ"}
    priority_label = priority_map.get(handover.priority.lower(), handover.priority.upper())

    subject = f"ВЫЗОВ МЕНЕДЖЕРА | {priority_label} | {handover.main_topic} | {handover.client_name}"

    detailed_summary = ""
    if handover.dialogue_summary:
        ds = handover.dialogue_summary
        blocks: List[str] = [ds.summary]
        if ds.key_points:
            blocks.append("Ключевые моменты:\n- " + "\n- ".join(ds.key_points))
        if ds.open_questions:
            blocks.append("Нужно уточнить:\n- " + "\n- ".join(ds.open_questions))
        if ds.next_steps:
            blocks.append("Следующие шаги:\n- " + "\n- ".join(ds.next_steps))
        detailed_summary = "\n\n".join(blocks)

    order_block = ""
    if handover.order and handover.order.items:
        order = handover.order
        lines: List[str] = []
        cur = (order.pricing.currency if order.pricing else "RUB")
        has_missing_prices = False

        for i, it in enumerate(order.items, start=1):
            code = f" (код: {it.product_code})" if it.product_code else ""
            qty = _fmt_qty(it.quantity, it.unit)

            # Если нет цены - показываем "Уточнить"
            if it.unit_price is None:
                price = "Уточнить"
                total = "Уточнить"
                has_missing_prices = True
            else:
                price = _fmt_money(it.unit_price, cur)
                total = _fmt_money(it.line_total, cur) if it.line_total is not None else "Уточнить"

            extra = f" | {it.availability}" if it.availability else ""
            lines.append(f"{i}. {it.product_name}{code} — {qty} × {price} = {total}{extra}")
            if it.comment:
                lines.append(f"   примечание: {it.comment}")

        if has_missing_prices:
            lines.append("\n⚠️ Некоторые позиции требуют уточнения цены")
        if order.pricing:
            p = order.pricing
            lines.append("")
            lines.append(f"Сумма позиций: {_fmt_money(p.subtotal, cur)}")
            if p.delivery_cost:
                lines.append(f"Доставка: {_fmt_money(p.delivery_cost, cur)}")
            if p.discount:
                lines.append(f"Скидка: {_fmt_money(p.discount, cur)}")
            lines.append(f"Итого: {_fmt_money(p.total, cur)}")
            if p.payment_terms:
                lines.append(f"Оплата: {p.payment_terms}")
        order_block = "\n".join(lines).strip()

    fields = {
        "Клиент": handover.client_name,
        "Контакты": handover.client_contact or "Не указаны",
        "Приоритет": priority_label,
        "Тема": handover.main_topic,
        "Краткое содержание диалога": handover.client_summary,
        "Детальное саммари": detailed_summary,
        "Заказ / позиции": order_block,
    }

    html_body = render_email_html(
        "ВЫЗОВ МЕНЕДЖЕРА",
        "Требуется подключение специалиста к диалогу",
        fields,
        "Сообщение сформировано автоматически ИИ-ассистентом СтройАссортимент"
    )

    message = EmailMessage()
    message["From"] = os.getenv("SMTP_USER")
    message["To"] = sales_email
    message["Subject"] = subject
    message.set_content(f"Вызов менеджера: {handover.client_name} - {handover.main_topic}")
    message.add_alternative(html_body, subtype='html')

    try:
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        # Port 465 uses SSL, port 587 uses STARTTLS
        if smtp_port == 465:
            await aiosmtplib.send(message, hostname=os.getenv("SMTP_SERVER"), port=smtp_port,
                                 username=os.getenv("SMTP_USER"), password=os.getenv("SMTP_PASSWORD"),
                                 use_tls=True)
        else:
            await aiosmtplib.send(message, hostname=os.getenv("SMTP_SERVER"), port=smtp_port,
                                 username=os.getenv("SMTP_USER"), password=os.getenv("SMTP_PASSWORD"),
                                 start_tls=True)
        return "Менеджер получил ваш запрос и сейчас изучает историю переписки. Он ответит вам в ближайшее время."
    except Exception as e:
        logger.error(f"Handover error: {e}")
        return "Я передал вашу просьбу менеджеру, он скоро подключится."

@tool
async def collect_order_info(
    order: OrderInfo,
    config: Annotated[dict, InjectedToolArg] = None
) -> str:
    """
    Оформляет конкретный заказ и отправляет его в отдел продаж.

    ВАЖНО: Используй этот инструмент только когда:
    - Клиент ТОЧНО определился с товарами (не раздумывает)
    - Есть конкретные позиции с кодами товаров
    - Клиент готов оформить заказ

    ОБЯЗАТЕЛЬНО перед вызовом:
    1. Найди товары через search_products_tool
    2. Проверь актуальные цены/остатки через get_product_live_details
    3. Заполни для КАЖДОЙ позиции:
       - product_code (код из поиска)
       - product_name (название)
       - quantity (количество)
       - unit (единица измерения)

    Цены и итоги посчитаются АВТОМАТИЧЕСКИ из 1С!

    Если клиент в раздумьях или нужна консультация - используй call_manager вместо этого инструмента.
    """
    # Извлекаем user_info из конфигурации (передается агентом)
    user_info = config.get("configurable", {}).get("user_info", {}) if config else {}

    # Автоматически заполняем channel_source и contact_username из контекста
    if not order.channel_source:
        order.channel_source = user_info.get("channel")
    if not order.contact_username:
        order.contact_username = user_info.get("username")
    sales_email = os.getenv("SALES_EMAIL", "astexlab@gmail.com")

    # Валидация: должны быть позиции с кодами
    if not order.items:
        return "Для оформления заказа нужно указать хотя бы одну позицию товара."

    # Обогащаем заказ данными из 1С и считаем итоги
    try:
        order = enrich_and_calculate_order_sync(order)
        logger.info(f"Order enriched and calculated successfully")
    except Exception as e:
        logger.warning(f"Failed to enrich/calculate order: {repr(e)}")
        return (
            "Чтобы оформить заказ, мне нужны коды номенклатуры по каждой позиции (product_code). "
            "Давай сначала подберём конкретные товары через search_products_tool → get_product_live_details, "
            "после этого я посчитаю цены/итог и отправлю заявку."
        )

    logger.info(f"Сбор заказа: клиент={order.client_name}, позиций={len(order.items)}")

    # Определяем основной товар для темы письма
    main_product = order.items[0].product_name if order.items else "Товар"
    volume = _fmt_qty(order.items[0].quantity, order.items[0].unit) if order.items else "—"

    subject = f"ЗАКАЗ | {main_product} | {volume} | {order.client_name}"

    # Формируем список позиций (ВСЕ позиции, даже без цены)
    items_text = ""
    if order.items:
        cur = (order.pricing.currency if order.pricing else "RUB")
        parts: List[str] = []
        has_missing_prices = False

        for i, it in enumerate(order.items, start=1):
            code = f" (код: {it.product_code})" if it.product_code else ""
            qty = _fmt_qty(it.quantity, it.unit)

            # Если нет цены - показываем "Уточнить у менеджера"
            if it.unit_price is None:
                price = "Уточнить"
                total = "Уточнить"
                has_missing_prices = True
            else:
                price = _fmt_money(it.unit_price, cur)
                total = _fmt_money(it.line_total, cur) if it.line_total is not None else "Уточнить"

            extra = f" | {it.availability}" if it.availability else ""
            parts.append(f"{i}. {it.product_name}{code} — {qty} × {price} = {total}{extra}")
            if it.comment:
                parts.append(f"   примечание: {it.comment}")

        items_text = "\n".join(parts)

        # Если есть позиции без цен - добавляем примечание
        if has_missing_prices:
            items_text += "\n\n⚠️ Некоторые позиции требуют уточнения цены у менеджера"

    # Формируем итоги
    pricing_text = ""
    if order.pricing:
        p = order.pricing
        cur = p.currency or "RUB"
        pricing_lines = [
            f"Сумма позиций: {_fmt_money(p.subtotal, cur)}",
        ]
        if p.delivery_cost:
            pricing_lines.append(f"Доставка: {_fmt_money(p.delivery_cost, cur)}")
        if p.discount:
            pricing_lines.append(f"Скидка: {_fmt_money(p.discount, cur)}")
        pricing_lines.append(f"Итого: {_fmt_money(p.total, cur)}")
        if p.payment_terms:
            pricing_lines.append(f"Оплата: {p.payment_terms}")
        pricing_text = "\n".join(pricing_lines)

    dialogue_text = ""
    if order.dialogue_summary:
        ds = order.dialogue_summary
        blocks: List[str] = [ds.summary]
        if ds.key_points:
            blocks.append("Ключевые моменты:\n- " + "\n- ".join(ds.key_points))
        if ds.open_questions:
            blocks.append("Нужно уточнить:\n- " + "\n- ".join(ds.open_questions))
        if ds.next_steps:
            blocks.append("Следующие шаги:\n- " + "\n- ".join(ds.next_steps))
        dialogue_text = "\n\n".join(blocks)

    # Формируем информацию о канале связи
    channel_info = ""
    if order.channel_source:
        channel_info = order.channel_source
        if order.contact_username:
            channel_info += f" (@{order.contact_username})"

    fields = {
        "Клиент": order.client_name,
        "Контакты": order.client_contact,
        "Канал связи": channel_info or "—",
        "Позиции заказа": items_text,
        "Цены / Итоги": pricing_text,
        "Саммари диалога": dialogue_text,
        "Адрес доставки": order.delivery_address or "Самовывоз",
        "Способ получения": order.delivery_method or "",
        "Дополнительно": order.additional_comments or ""
    }

    html_body = render_email_html(
        "НОВАЯ ЗАЯВКА",
        "Предварительный заказ из чат-бота",
        fields,
        "Заявка сформирована автоматически ИИ-ассистентом СтройАссортимент"
    )

    message = EmailMessage()
    message["From"] = os.getenv("SMTP_USER")
    message["To"] = sales_email
    message["Subject"] = subject
    message.set_content(f"Новый заказ: {order.client_name} - {main_product}")
    message.add_alternative(html_body, subtype='html')

    try:
        logger.info(f"Отправка email на {sales_email}...")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        # Port 465 uses SSL, port 587 uses STARTTLS
        if smtp_port == 465:
            await aiosmtplib.send(message, hostname=os.getenv("SMTP_SERVER"), port=smtp_port,
                                 username=os.getenv("SMTP_USER"), password=os.getenv("SMTP_PASSWORD"),
                                 use_tls=True)
        else:
            await aiosmtplib.send(message, hostname=os.getenv("SMTP_SERVER"), port=smtp_port,
                                 username=os.getenv("SMTP_USER"), password=os.getenv("SMTP_PASSWORD"),
                                 start_tls=True)
        logger.info("Email успешно отправлен.")
        await _persist_order_submission(order, status="SENT")
        return f"Благодарю, {order.client_name}! Ваша заявка отправлена в отдел продаж. Менеджер свяжется с вами в ближайшее время для уточнения деталей и подтверждения заказа."
    except Exception as e:
        logger.error(f"Order error: {e}")
        await _persist_order_submission(order, status="FAILED", error=str(e))
        return "Заявка принята, менеджер увидит ваше сообщение в чате."
