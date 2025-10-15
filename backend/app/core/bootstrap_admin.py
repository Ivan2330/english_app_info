# app/core/bootstrap_admin.py
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.hash import bcrypt

from app.core.config import settings
from app.models.admin_user import AdminUser, AdminRole

# ↓↓↓ додані імпорти ↓↓↓
from datetime import datetime
from typing import Dict, List, Tuple
from app.models.package import Package, Type as PackageType, Audience as PackageAudience
# ↑↑↑ додані імпорти ↑↑↑


async def ensure_owner_admin(session: AsyncSession) -> dict:
    """
    Створює OWNER-адміна, якщо в системі ще нікого немає.
    Якщо користувачі вже є — нічого не робимо.
    Повертає {"created": bool, "email": str}.
    """
    result = await session.execute(select(AdminUser).limit(1))
    existing = result.scalar_one_or_none()
    if existing:
        return {"created": False, "email": existing.email}

    email = settings.admin_email.strip().lower()
    password = settings.admin_password

    admin = AdminUser(
        email=email,
        password_hash=bcrypt.hash(password),
        role=AdminRole.OWNER,
        is_active=True,
    )
    session.add(admin)
    await session.commit()
    return {"created": True, "email": email}


# ===== Внутрішні утиліти ======================================================

def _linear_percent_steps(n: int, min_pct: float, max_pct: float) -> List[float]:
    """
    Повертає n рівномірно розподілених значень від min_pct до max_pct включно.
    Напр.: n=5, 0.15..0.45 => [0.15, 0.225, 0.30, 0.375, 0.45]
    """
    if n <= 1:
        return [max(min_pct, 0.0)]
    step = (max_pct - min_pct) / (n - 1)
    return [min_pct + i * step for i in range(n)]


async def _purge_packages(
    session: AsyncSession,
    plan_type: PackageType,
    audience: PackageAudience,
) -> int:
    """
    Жорстко видаляє ВСІ пакети для вказаного типу/аудиторії.
    Повертає кількість видалених рядків.
    """
    res = await session.execute(
        delete(Package).where(
            Package.type == plan_type,
            Package.audience == audience,
        )
    )
    # SQLAlchemy повертає result.rowcount тільки для деяких backends; норм, якщо None.
    await session.commit()
    return res.rowcount or 0


def _build_pkgs_payload(
    plan_type: PackageType,
    audience: PackageAudience,
    raw_rows: List[Tuple[int, int, int]],  # (lessons_count, price_per_lesson, total_price)
    min_pct: float = 0.15,
    max_pct: float = 0.45,
    name_prefix: str = "",
    slug_prefix: str = "",
) -> List[Dict]:
    """
    Збирає структури для створення пакетів.
    not_true_price = total_price * (1 + pct), де pct лінійно зростає від min_pct до max_pct
    по тирах. Перший іде з +15%, останній з +45%.
    """
    tiers = sorted(raw_rows, key=lambda r: r[0])
    pcts = _linear_percent_steps(len(tiers), min_pct, max_pct)

    now = datetime.utcnow()

    if plan_type == PackageType.STANDARD:
        short_description = "50-хв індивідуальні уроки. Фокус на реальному прогресі та розмові."
        long_description = (
            "Поєднання готових і індивідуальних завдань під ваші цілі. "
            "Домашні завдання на Reading/Grammar/Vocabulary/Listening/Speaking, "
            "списки слів під реальні ситуації (робота, подорожі, інтерв’ю). "
            "Прозорий прогрес і підтримка між уроками."
        )
    else:
        short_description = "Преміум-напрям: 50-хв індивідуальні уроки + розширена підтримка."
        long_description = (
            "Поглиблена робота з викладачем, додаткові матеріали та перевірка домашніх, "
            "персональні рекомендації, пріоритетні слоти в розкладі. "
            "Підбір контенту під ваші задачі та регулярний трекінг прогресу."
        )

    items: List[Dict] = []
    for idx, (lessons_count, ppl, total_price) in enumerate(tiers):
        pct = pcts[idx]
        # ←←← ТУТ «накидається» відсоток до реальної total_price
        not_true_price = round(total_price * (1.0 + pct))

        discount_money = max(not_true_price - total_price, 0)
        discount_percent = round((discount_money / not_true_price) * 100) if not_true_price else None

        name = f"{name_prefix} — Adults ({lessons_count} lessons)"
        slug = f"{slug_prefix}-adults-{lessons_count}"

        items.append(
            {
                "slug": slug,
                "name": name,
                "type": plan_type,
                "audience": audience,
                "short_description": short_description,
                "long_description": long_description,
                "lesson_duration": "50",
                "lessons_count": lessons_count,
                "currency": "UAH",
                "not_true_price": not_true_price,
                "price_per_lesson": ppl,
                "base_price": None,
                "discount_percent": discount_percent,
                "discount_money": discount_money,
                "total_price": total_price,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
        )
    return items


async def _create_packages(session: AsyncSession, items: List[Dict]) -> Dict:
    """
    Масове створення пакетів (припускається, що ми попередньо все очистили).
    """
    for it in items:
        session.add(Package(**it))
    await session.commit()
    return {"created_slugs": [it["slug"] for it in items]}


# ===== ПУБЛІЧНІ ФУНКЦІЇ =======================================================

async def ensure_standard_packages(session: AsyncSession, purge_existing: bool = True) -> Dict:
    """
    Створює пакети STANDARD/ADULTS згідно 'стандартної' таблиці.
    За замовчуванням ПЕРЕД цим очищає попередні пакети цього типу/аудиторії.
    not_true_price: від +15% до +45% (лінійно по тирах).
    """
    if purge_existing:
        await _purge_packages(session, PackageType.STANDARD, PackageAudience.ADULTS)

    # (lessons_count, price_per_lesson, total_price)
    standard_rows: List[Tuple[int, int, int]] = [
        (6,   500,  3000),
        (16,  440,  7040),
        (24,  420,  10080),
        (48,  400,  19200),
        (64,  380,  24320),
        (72,  370,  26640),
        (96,  360,  34560),
        (144, 350,  50400),
        (184, 340,  62560),
        (250, 330,  82500),
    ]

    items = _build_pkgs_payload(
        plan_type=PackageType.STANDARD,
        audience=PackageAudience.ADULTS,
        raw_rows=standard_rows,
        min_pct=0.15,
        max_pct=0.45,
        name_prefix="Standard",
        slug_prefix="standard",
    )
    return await _create_packages(session, items)


async def ensure_premium_packages(session: AsyncSession, purge_existing: bool = True) -> Dict:
    """
    Створює пакети PREMIUM/ADULTS згідно 'преміум' таблиці.
    За замовчуванням очищає попередні пакети цього типу/аудиторії.
    not_true_price: від +15% до +45%.
    """
    if purge_existing:
        await _purge_packages(session, PackageType.PREMIUM, PackageAudience.ADULTS)

    # (lessons_count, price_per_lesson, total_price)
    premium_rows: List[Tuple[int, int, int]] = [
        (6,   650,  3900),
        (16,  600,  9600),
        (24,  570,  13680),
        (48,  540,  25920),
        (64,  500,  32000),
        (72,  480,  34560),
        (96,  460,  44160),
        (144, 440,  63360),
        (184, 420,  77280),
        (250, 400, 100000),
    ]

    items = _build_pkgs_payload(
        plan_type=PackageType.PREMIUM,
        audience=PackageAudience.ADULTS,
        raw_rows=premium_rows,
        min_pct=0.15,
        max_pct=0.45,
        name_prefix="Premium",
        slug_prefix="premium",
    )
    return await _create_packages(session, items)
