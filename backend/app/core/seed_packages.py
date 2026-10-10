"""Генерація каталогу пакетів із тарифної сітки (app/core/pricing.py).

Запуск:  python -m app.cli seed-packages

Це НЕ startup-хук. Раніше пакети стиралися й генерувалися заново при кожному
рестарті контейнера — через це будь-яка правка в адмінці зникала, а адмінський
CRUD по пакетах був фактично неробочим. Тепер сід викликається руками.

Поведінка: upsert за slug. Пакети, яких більше немає в сітці, не видаляються,
а деактивуються (is_active=False) — щоб не ламати посилання й історію.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pricing as P
from app.models.package import Package, Family, Audience, Format, Track


# --- людські назви для складання name ----------------------------------------
AUDIENCE_LABEL = {"adults": "Дорослі", "teens": "Підлітки", "kids": "Діти", "corporate": "Компанії"}
FORMAT_LABEL = {"individual": "Індивідуально", "pair": "У парі", "group": "Група", "club": "Клуб"}

TRACK_LABEL = {
    "general": "Загальний рівень",
    "speaking": "Розмовний фокус",
    "business": "Робота та кар'єра",
    "school": "Школа",
    "nmt": "НМТ",
    "exam": "Підготовка до іспиту",
    "job_ready": "Job Ready",
    "it": "English for IT",
    "travel": "Travel English",
}

TRACK_DESC = {
    "general": "Системно підняти англійську за рівнями CEFR, без прив'язки до іспиту.",
    "speaking": "Для тих, хто все розуміє, але мовчить. Мінімум теорії, максимум практики.",
    "school": "Шкільна програма без нудьги: підтягуємо оцінки й повертаємо впевненість.",
}

# Які напрями доступні кожній аудиторії в абонементах.
# «Розмовний фокус» відкритий усім: мовчазний підліток і дитина, яка все розуміє,
# але не говорить, — це та сама проблема, що й у дорослого. Раніше цей напрям
# був лише в дорослих, і в конструкторі він стояв сірий для двох аудиторій
# із трьох, що читалося як «вам не можна».
SUB_TRACKS = {
    "adults": ["general", "speaking"],
    "teens": ["general", "speaking", "school"],
    "kids": ["general", "speaking", "school"],
}

# Тривалість уроку у хвилинах: аудиторія → формат
LESSON_MIN = {
    "adults": {"individual": 50, "pair": 50, "group": 90},
    "teens":  {"individual": 50, "pair": 50, "group": 90},
    "kids":   {"individual": 40, "pair": 40, "group": 60},
}


def _pricing_row(ladder: List[int], prices: List[int], hints: List[str], idx: int) -> Dict:
    """Рахує ціну, якір і знижку для однієї сходинки пакета."""
    lessons = ladder[idx]
    ppl = prices[idx]
    total = ppl * lessons

    # Якір — ставка найменшого пакета × кількість. Реальна ціна, не вигадана.
    anchor = prices[0] * lessons
    discount_money = max(anchor - total, 0)
    discount_percent = round(discount_money / anchor * 100) if anchor and discount_money else 0

    chast_enabled, chast_parts = P.chast_for(total)
    return dict(
        lessons_count=lessons,
        price_per_lesson=ppl,
        total_price=total,
        not_true_price=anchor if discount_money else None,
        discount_money=discount_money or None,
        discount_percent=discount_percent or None,
        duration_hint=hints[idx],
        chast_enabled=chast_enabled,
        chast_max_parts=chast_parts,
        validity_days=P.validity_for(lessons),
    )


def build_catalogue() -> List[Dict]:
    """Збирає повний каталог зі сітки. Чистa функція — нічого не пише в базу."""
    items: List[Dict] = []
    order = 0

    # ================= 1. АБОНЕМЕНТИ =================
    for audience in ("adults", "teens", "kids"):
        is_kids = audience == "kids"
        for track in SUB_TRACKS[audience]:
            for fmt in ("individual", "pair", "group"):
                # яка лінійка й ціни діють для цієї комбінації
                if is_kids:
                    if fmt == "group":
                        ladder, prices, hints = P.KIDS_GROUP_LADDER, P.KIDS_GROUP_PRICE, P.KIDS_GROUP_HINT
                    elif fmt == "pair":
                        ladder, prices, hints = P.KIDS_LADDER, P.KIDS_PAIR, P.KIDS_DURATION_HINT
                    else:
                        ladder, prices, hints = P.KIDS_LADDER, P.KIDS_INDIVIDUAL, P.KIDS_DURATION_HINT
                else:
                    if fmt == "group":
                        ladder, prices, hints = P.GROUP_LADDER, P.GROUP_PRICE, P.GROUP_DURATION_HINT
                    elif fmt == "pair":
                        ladder, prices, hints = P.ADULT_LADDER, P.ADULT_PAIR, P.ADULT_DURATION_HINT
                    else:
                        ladder, prices, hints = P.ADULT_LADDER, P.ADULT_INDIVIDUAL, P.ADULT_DURATION_HINT

                for idx in range(len(ladder)):
                    row = _pricing_row(ladder, prices, hints, idx)
                    order += 1
                    items.append(dict(
                        slug=f"{track}-{audience}-{fmt}-{row['lessons_count']}",
                        name=(f"{TRACK_LABEL[track]} · {AUDIENCE_LABEL[audience]} · "
                              f"{FORMAT_LABEL[fmt]} · {row['lessons_count']} уроків"),
                        family=Family.SUBSCRIPTION,
                        audience=Audience(audience),
                        fmt=Format(fmt),
                        track=Track(track),
                        short_description=TRACK_DESC.get(track),
                        lesson_duration_min=LESSON_MIN[audience][fmt],
                        group_size_max=P.GROUP_SIZE_MAX if fmt == "group" else (2 if fmt == "pair" else None),
                        price_per_person=(fmt == "pair"),
                        sort_order=order,
                        **row,
                    ))

    # ================= 2. ТЕМАТИЧНІ КУРСИ =================
    for c in P.COURSES:
        lessons = c["lessons"]
        fmt = c["fmt"]
        ppl = c.get("ppl") or P.course_rate(lessons, fmt)
        if c["track"] == "nmt":
            ppl = P.r10(ppl * P.NMT_COEF)
        total = ppl * lessons
        chast_enabled, chast_parts = P.chast_for(total)
        order += 1
        audience = c["audience"]
        items.append(dict(
            slug=c["slug"],
            name=c["name"],
            family=Family.COURSE,
            audience=Audience(audience),
            fmt=Format(fmt),
            track=Track(c["track"]),
            short_description=c.get("desc"),
            lesson_duration_min=LESSON_MIN[audience][fmt],
            lessons_count=lessons,
            group_size_max=P.GROUP_SIZE_MAX if fmt == "group" else None,
            level_from=c.get("level_from"),
            level_target=c.get("level_target"),
            duration_hint=c.get("hint"),
            price_per_lesson=ppl,
            total_price=total,
            price_per_person=(fmt == "pair"),
            chast_enabled=chast_enabled,
            chast_max_parts=chast_parts,
            validity_days=P.validity_for(lessons),
            is_popular=c.get("popular", False),
            sort_order=order,
        ))

    # ================= 3. SPEAKING CLUB =================
    for c in P.CLUBS:
        order += 1
        items.append(dict(
            slug=c["slug"],
            name=c["name"],
            family=Family.CLUB,
            audience=Audience(c["audience"]),
            fmt=Format.CLUB,
            track=Track.SPEAKING,
            short_description=c.get("desc"),
            lesson_duration_min=c.get("minutes", 60),
            lessons_count=c["meets"],
            group_size_max=c.get("size", 10),
            duration_hint="на місяць",
            price_per_lesson=round(c["price"] / c["meets"]),
            total_price=c["price"],
            is_popular=c.get("popular", False),
            sort_order=order,
        ))

    # ================= 4. КОРПОРАТИВ =================
    # ПЧ тут не вмикаємо: оплата йде банківським переказом за рахунком,
    # і за домовленістю — постоплатою за фактично проведені заняття.
    for c in P.CORPORATE:
        order += 1
        items.append(dict(
            slug=c["slug"],
            name=c["name"],
            family=Family.CORPORATE,
            audience=Audience.CORPORATE,
            fmt=Format.INDIVIDUAL if c["size"] == 1 else Format.GROUP,
            track=Track.BUSINESS,
            short_description=c.get("desc"),
            lesson_duration_min=c["duration"],
            lessons_count=1,
            group_size_max=c["size"],
            duration_hint=c.get("unit", "ціна за урок"),
            price_per_lesson=c["price"],
            total_price=c["price"],
            is_popular=c.get("popular", False),
            sort_order=order,
        ))

    return items


async def seed_packages(session: AsyncSession) -> Dict:
    """Upsert каталогу. Пакети поза сіткою деактивуються, а не видаляються."""
    items = build_catalogue()
    now = datetime.utcnow()

    existing = {p.slug: p for p in (await session.execute(select(Package))).scalars().all()}
    created = updated = 0

    for it in items:
        slug = it["slug"]
        pkg = existing.get(slug)
        if pkg is None:
            pkg = Package(created_at=now, updated_at=now, currency=P.CURRENCY, is_active=True)
            session.add(pkg)
            created += 1
        else:
            updated += 1
        for field, value in it.items():
            setattr(pkg, field, value)
        pkg.is_active = True
        pkg.updated_at = now

    fresh_slugs = {it["slug"] for it in items}
    deactivated = 0
    for slug, pkg in existing.items():
        if slug not in fresh_slugs and pkg.is_active:
            pkg.is_active = False
            deactivated += 1

    await session.commit()
    return {"created": created, "updated": updated, "deactivated": deactivated, "total": len(items)}
