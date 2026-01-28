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
import httpx
from langchain.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Цвета бренда из скриншота
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
    """Структурированная позиция заказа (по возможности с кодом 1С)."""

    product_code: Optional[str] = Field(
        None,
        description="Код номенклатуры/товара в 1С (например, '00-00003162'), если удалось определить",
    )
    product_name: str = Field(description="Название товара (как в 1С/как договорились с клиентом)")
    quantity: Optional[float] = Field(
        None,
        description="Количество (число). Если клиент сказал 'примерно' — укажи оценку числом",
    )
    unit: Optional[str] = Field(None, description="Ед. измерения (шт, м, м2, м3, упак и т.п.), если известно")
    unit_price: Optional[float] = Field(None, description="Цена за единицу (число без валюты), если известна")
    line_total: Optional[float] = Field(None, description="Итог по позиции (число без валюты), если можно посчитать")
    availability: Optional[str] = Field(None, description="Наличие/остатки коротко (например, 'в наличии', 'под заказ')")
    comment: Optional[str] = Field(None, description="Примечание по позиции (сорт/влажность/размеры/требования)")


class OrderPricing(BaseModel):
    """Сводка по ценам. Валюта по умолчанию — RUB."""

    currency: str = Field("RUB", description="Валюта (обычно RUB)")
    subtotal: Optional[float] = Field(None, description="Сумма позиций без доставки/скидок")
    delivery_cost: Optional[float] = Field(None, description="Стоимость доставки, если обсуждалась")
    discount: Optional[float] = Field(None, description="Скидка (если обсуждалась), положительное число")
    total: Optional[float] = Field(None, description="Итого к оплате")
    payment_terms: Optional[str] = Field(None, description="Условия оплаты (нал/безнал, предоплата и т.д.)")


class DialogueSummary(BaseModel):
    """Детальное резюме диалога для менеджера."""

    summary: str = Field(description="Детальное саммари диалога (1-2 абзаца)")
    key_points: List[str] = Field(default_factory=list, description="Ключевые факты/договоренности списком")
    open_questions: List[str] = Field(default_factory=list, description="Что ещё нужно уточнить у клиента")
    next_steps: List[str] = Field(default_factory=list, description="Рекомендуемые следующие шаги менеджеру")


def _pydantic_dump(obj: BaseModel) -> dict:
    # Pydantic v2 has model_dump; v1 has dict
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return obj.dict()


async def _persist_order_submission(order: "OrderInfo", status: str, error: Optional[str] = None) -> None:
    """
    Store order in Postgres for dashboard analytics.
    """
    try:
        from db.session import async_session_factory
        from db.models import OrderSubmission
    except Exception as e:
        logger.warning(f"DB not available for order persistence: {repr(e)}")
        return

    payload = _pydantic_dump(order)
    currency = (order.pricing.currency if order.pricing else "RUB") if getattr(order, "pricing", None) else "RUB"
    subtotal = getattr(order.pricing, "subtotal", None) if getattr(order, "pricing", None) else None
    total = getattr(order.pricing, "total", None) if getattr(order, "pricing", None) else None
    items_count = len(order.items) if getattr(order, "items", None) else None

    async with async_session_factory() as session:
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
        try:
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.warning(f"Failed to persist order submission: {repr(e)}")


async def _fetch_products_from_1c(product_codes: List[str]) -> Dict[str, dict]:
    """
    Fetches current product info for product codes from 1C (GetDetailedItems).
    Returns map: code -> {"price": float|None, "stock_qty": float|None, "stock_raw": str|None}
    """
    import importlib.util
    from pathlib import Path
    _schemas_path = Path(__file__).parent.parent / "schemas" / "1с_schemas.py"
    _spec = importlib.util.spec_from_file_location("schemas_1c", _schemas_path)
    _schemas = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_schemas)
    parse_get_detailed_items_payload = _schemas.parse_get_detailed_items_payload

    # Keep config consistent with search_1c_products.py
    api_url = os.getenv(
        "C1_DETAILED_API_URL",
        "http://172.16.77.34/stroyast_copy_itspec_38601/hs/AiBot/GetDetailedItems",
    )
    api_user = os.getenv("C1_API_USER", "Администратор")
    api_password = os.getenv("C1_API_PASSWORD", "159753")
    api_enabled = os.getenv("C1_API_ENABLED", "true").lower() not in ("false", "0", "off")
    timeout_s = float(os.getenv("C1_API_TIMEOUT_SECONDS", "30"))

    if not api_enabled or not product_codes:
        return {}

    payload = {"items": product_codes}
    auth = (api_user, api_password)

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_s)) as client:
            resp = await client.post(api_url, json=payload, auth=auth)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning(f"Failed to fetch prices from 1C: {repr(e)}")
        return {}

    items = parse_get_detailed_items_payload(data)
    out: Dict[str, dict] = {}
    for it in items:
        if not it.code:
            continue
        stock_qty = None
        stock_raw = None
        try:
            # C1Stock.qty is Decimal | None
            stock_qty = float(it.stock.qty) if getattr(it.stock, "qty", None) is not None else None
            stock_raw = getattr(it.stock, "raw", None)
        except Exception:
            stock_qty = None
            stock_raw = None

        out[it.code] = {
            "price": (float(it.price) if it.price is not None else None),
            "stock_qty": stock_qty,
            "stock_raw": stock_raw,
        }
    return out


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


async def enrich_and_calculate_order(order: "OrderInfo") -> "OrderInfo":
    """
    Server-side enrichment + classic totals calculation.
    - If items have product_code but missing unit_price, fetch from 1C
    - Calculate line totals and order totals
    """
    if not order.items:
        return order

    # Enforce product_code: we only do classic pricing if codes exist
    missing_codes = [it.product_name for it in order.items if not it.product_code]
    if missing_codes:
        raise ValueError(
            "Для расчёта заказа нужны коды номенклатуры (product_code) по каждой позиции. "
            f"Нет кода у: {', '.join(missing_codes[:5])}"
        )

    # Fetch product info for items (prices + stock)
    need_codes = [it.product_code for it in order.items if it.product_code]
    codes_unique = list(dict.fromkeys([c for c in need_codes if c]))
    if codes_unique:
        products = await _fetch_products_from_1c(codes_unique)
        for it in order.items:
            if not it.product_code:
                continue
            p = products.get(it.product_code)
            if not p:
                continue

            # Fill unit_price from 1C if missing
            if it.unit_price is None and p.get("price") is not None:
                it.unit_price = p["price"]

            # Fill availability using 1C stock (остатки в м³)
            stock_qty = p.get("stock_qty")
            stock_raw = p.get("stock_raw")
            if stock_qty is not None:
                it.availability = f"остаток: {stock_qty:g} м³"
                # If client order is in m³, warn when quantity exceeds stock
                if it.quantity is not None and it.unit and it.unit.strip().lower() in ("м3", "м³", "куб", "куба", "куб.м", "куб. м", "м^3"):
                    try:
                        if float(it.quantity) > float(stock_qty):
                            it.availability += " (не хватает, нужен предзаказ/уточнение)"
                    except Exception:
                        pass
            elif stock_raw:
                it.availability = f"остатки: {stock_raw}"

    return _calculate_order_totals(order)

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

    product_details: Optional[str] = Field(
        None,
        description="Текстом: что заказывает клиент (название/объем/размеры). Используется если структурированные позиции не заполнены",
    )
    main_product: Optional[str] = Field(
        None,
        description="Основной товар для заголовка (например, 'Лиственница', 'Доска обрезная')",
    )
    estimated_volume: Optional[str] = Field(
        None,
        description="Кратко объем/кол-во для заголовка (например, '15 м3', '2 куба', '100 шт')",
    )

    # New structured fields
    dialogue_summary: Optional[DialogueSummary] = Field(
        None,
        description="Детальное саммари диалога по заказу (желательно заполнить)",
    )
    items: List[OrderLineItem] = Field(
        default_factory=list,
        description="Позиции заказа (с кодом 1С/кол-вом/ценой по возможности)",
    )
    pricing: Optional[OrderPricing] = Field(
        None,
        description="Сводка по ценам/итогу/оплате. Если можешь посчитать total — укажи",
    )

    delivery_address: Optional[str] = Field(None, description="Адрес доставки, если клиент его указал")
    delivery_method: Optional[str] = Field(None, description="Доставка/самовывоз/ТК и т.п., если обсуждалось")
    additional_comments: Optional[str] = Field(None, description="Дополнительные пожелания клиента")

class ManagerHandover(BaseModel):
    client_summary: str = Field(description="Краткое описание того, что хочет клиент и на чем остановился диалог")

    # New detailed summary (optional)
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
        description="Если в диалоге уже есть конкретика по заказу — приложи структуру заказа (позиции/цены/итоги)",
    )

@tool
async def call_manager(handover: ManagerHandover) -> str:
    """
    Вызывает живого менеджера для помощи клиенту. 
    Обязательно составь краткое саммари для менеджера и выдели тему (main_topic).
    """
    sales_email = os.getenv("SALES_EMAIL")
    if not sales_email:
        return "Ошибка конфигурации: почта отдела продаж не настроена."

    # Enrich order (if provided) and calculate totals server-side
    if handover.order:
        try:
            handover.order = await enrich_and_calculate_order(handover.order)
        except Exception as e:
            # Don't fail the call_manager tool; include what we can.
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
    if handover.order:
        order = handover.order
        lines: List[str] = []
        cur = (order.pricing.currency if order.pricing else "RUB")
        if order.items:
            for i, it in enumerate(order.items, start=1):
                code = f" (код 1С: {it.product_code})" if it.product_code else ""
                qty = _fmt_qty(it.quantity, it.unit)
                price = _fmt_money(it.unit_price, cur) if it.unit_price is not None else "—"
                total = _fmt_money(it.line_total, cur) if it.line_total is not None else "—"
                extra = f" | {it.availability}" if it.availability else ""
                lines.append(f"{i}. {it.product_name}{code} — {qty} × {price} = {total}{extra}")
                if it.comment:
                    lines.append(f"   примечание: {it.comment}")
        if order.pricing:
            p = order.pricing
            lines.append("")
            lines.append(f"Сумма позиций: {_fmt_money(p.subtotal, cur)}")
            lines.append(f"Доставка: {_fmt_money(p.delivery_cost, cur)}")
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
        "Сообщение сформировано автоматически системой Саид-ИИ"
    )

    message = EmailMessage()
    message["From"] = os.getenv("SMTP_USER")
    message["To"] = sales_email
    message["Subject"] = subject
    message.set_content(f"Вызов менеджера: {handover.client_name} - {handover.main_topic}")
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
    
    ВАЖНО: ПЕРЕД использованием этого инструмента ОБЯЗАТЕЛЬНО проверь наличие товаров через:
    - `search_1c_products` (для поиска по группам)
    - `get_product_details` (для проверки конкретных товаров)
    
    НЕ оформляй заказы на товары, которые не проверил на складе!
    Если товара нет в наличии - предложи альтернативу (тоже проверенную) или позови менеджера.
    """
    sales_email = os.getenv("SALES_EMAIL", "astexlab@gmail.com")
    
    # Enrich order and calculate totals server-side (do not rely on LLM for math)
    try:
        order = await enrich_and_calculate_order(order)
    except Exception as e:
        # If we can't compute a reliable order, ask the agent to go through 1C selection first.
        logger.warning(f"Failed to enrich/calculate order: {repr(e)}")
        return (
            "Чтобы оформить заказ, мне нужны коды номенклатуры 1С по каждой позиции (product_code). "
            "Давай сначала подберём конкретные товары через 1С (search_1c_products → get_product_details), "
            "после этого я посчитаю цены/итог и отправлю заявку."
        )
    
    logger.info(f"Сбор заказа: {order.dict()}")
    
    if not sales_email:
        return "Ошибка конфигурации: почта отдела продаж не настроена."

    main_product = order.main_product
    if not main_product and order.items:
        main_product = order.items[0].product_name
    main_product = main_product or "Товар"

    volume = order.estimated_volume
    if not volume and order.items:
        volume = _fmt_qty(order.items[0].quantity, order.items[0].unit)
    volume = volume or "—"

    subject = f"ЗАКАЗ | {main_product} | {volume} | {order.client_name}"

    items_text = ""
    if order.items:
        cur = (order.pricing.currency if order.pricing else "RUB")
        parts: List[str] = []
        for i, it in enumerate(order.items, start=1):
            code = f" (код 1С: {it.product_code})" if it.product_code else ""
            qty = _fmt_qty(it.quantity, it.unit)
            price = _fmt_money(it.unit_price, cur) if it.unit_price is not None else "—"
            total = _fmt_money(it.line_total, cur) if it.line_total is not None else "—"
            extra = f" | {it.availability}" if it.availability else ""
            parts.append(f"{i}. {it.product_name}{code} — {qty} × {price} = {total}{extra}")
            if it.comment:
                parts.append(f"   примечание: {it.comment}")
        items_text = "\n".join(parts)

    pricing_text = ""
    if order.pricing:
        p = order.pricing
        cur = p.currency or "RUB"
        pricing_lines = [
            f"Сумма позиций: {_fmt_money(p.subtotal, cur)}",
            f"Доставка: {_fmt_money(p.delivery_cost, cur)}",
            f"Скидка: {_fmt_money(p.discount, cur)}",
            f"Итого: {_fmt_money(p.total, cur)}",
        ]
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
    
    fields = {
        "Клиент": order.client_name,
        "Контакты": order.client_contact,
        "Основной товар": main_product,
        "Объем / Количество": volume,
        "Позиции заказа": items_text,
        "Цены / Итоги": pricing_text,
        "Саммари диалога": dialogue_text,
        "Детали заказа": order.product_details or "",
        "Адрес доставки": order.delivery_address or "Самовывоз",
        "Способ получения": order.delivery_method or "",
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
    message.set_content(f"Новый заказ: {order.client_name} - {main_product}")
    message.add_alternative(html_body, subtype='html')

    try:
        logger.info(f"Отправка email на {sales_email}...")
        await aiosmtplib.send(message, hostname=os.getenv("SMTP_SERVER"), port=int(os.getenv("SMTP_PORT", "587")),
                             username=os.getenv("SMTP_USER"), password=os.getenv("SMTP_PASSWORD"),
                             start_tls=True if os.getenv("SMTP_PORT") == "587" else False)
        logger.info("Email успешно отправлен.")
        await _persist_order_submission(order, status="SENT")
        return f"Благодарю, {order.client_name}! Ваша заявка отправлена в отдел продаж. Менеджер свяжется с вами в ближайшее время."
    except Exception as e:
        logger.error(f"Order error: {e}")
        await _persist_order_submission(order, status="FAILED", error=str(e))
        return "Заявка принята, менеджер увидит ваше сообщение в чате."
