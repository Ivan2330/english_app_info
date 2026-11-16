"""Лист власнику про нову заявку.

Налаштовується змінними оточення (у git лише .env.example):
    SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD, SMTP_FROM, LEAD_NOTIFY_EMAIL
Якщо SMTP_HOST або LEAD_NOTIFY_EMAIL порожні, листи просто не шлються (нічого не падає):
заявка в будь-якому разі зберігається в базі й видна в кабінеті.

Лист іде у фоні (`app.core.background`): відповідь людині не чекає на поштовий сервер.
Лист містить контакти людини, але адресований власнику школи. У лог потрапляє лише
факт помилки без адрес і тексту.
"""
from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.background import fire_and_forget
from app.core.config import settings

log = logging.getLogger("app.notify")

AUDIENCE = {"adults": "дорослий", "teens": "підліток 13–17", "kids": "дитина 5–12"}


def enabled() -> bool:
    return bool(settings.smtp_host and settings.lead_notify_email)


def build_message(lead) -> EmailMessage:
    contact = lead.phone or lead.telegram or lead.email or "без контакту"
    lines = [
        f"Імʼя: {lead.name}",
        f"Контакт: {contact}",
        f"Для кого: {AUDIENCE.get(lead.audience or '', lead.audience or 'не вказано')}",
        f"Рівень: {lead.level or 'не вказано'}",
        f"Зручний час: {lead.preferred_time or 'не вказано'}",
        f"Форма: {lead.source or 'site'}",
    ]
    if lead.utm_source or lead.utm_campaign:
        lines.append(f"Реклама: {lead.utm_source or '—'} / {lead.utm_campaign or '—'}"
                     + (f" / {lead.utm_content}" if lead.utm_content else ""))
    if lead.comment:
        lines += ["", "Коментар:", lead.comment]
    lines += ["", f"Відкрити в кабінеті: {settings.site_url}/admin/leads"]

    msg = EmailMessage()
    msg["Subject"] = f"Нова заявка на пробний: {lead.name}"
    msg["From"] = settings.smtp_from or settings.smtp_user or settings.lead_notify_email
    msg["To"] = settings.lead_notify_email
    msg.set_content("\n".join(lines))
    return msg


def _send_blocking(msg: EmailMessage) -> None:
    ctx = ssl.create_default_context()
    if settings.smtp_port == 465:
        server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15, context=ctx)
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
    with server:
        if settings.smtp_port != 465:
            server.starttls(context=ctx)
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)


async def send_lead_email(lead) -> bool:
    if not enabled():
        return False
    try:
        await asyncio.to_thread(_send_blocking, build_message(lead))
        return True
    except Exception as exc:  # noqa: BLE001 — лист не повинен ламати заявку
        log.warning("Лист про заявку не надіслано (%s)", type(exc).__name__)
        return False


def notify_new_lead(lead) -> None:
    if enabled():
        fire_and_forget(send_lead_email(lead))
