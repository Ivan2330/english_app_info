# app/core/bootstrap_admin.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.hash import bcrypt

from app.core.config import settings
from app.models.admin_user import AdminUser, AdminRole

# ↓↓↓ додай ці ІМПОРТИ ↓↓↓
from datetime import datetime
from app.models.package import Package, Type as PackageType, Audience as PackageAudience
# ↑↑↑ додай ці ІМПОРТИ ↑↑↑


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


# ↓↓↓ ДОДАЙ НОВУ ФУНКЦІЮ ДЛЯ СТАНДАРТНИХ ПАКЕТІВ (ADULTS) ↓↓↓
async def ensure_default_packages(session: AsyncSession) -> dict:
    """
    Ідемпотентно створює стандартні пакети для дорослих (STANDARD / ADULTS),
    якщо їх ще немає. Обчислює знижки в грошах і відсотках.
    """
    # Дані від тебе (в гривнях), тривалість 50 хв всюди
    items = [
        {
            "slug": "standard-adults-6",
            "name": "Standard — Adults (6 lessons)",
            "lessons_count": 6,
            "price_per_lesson": 500,
            "total_price": 3000,
            "not_true_price": 3500,
        },
        {
            "slug": "standard-adults-16",
            "name": "Standard — Adults (16 lessons)",
            "lessons_count": 16,
            "price_per_lesson": 430,
            "total_price": 6880,
            "not_true_price": 7200,
        },
        {
            "slug": "standard-adults-24",
            "name": "Standard — Adults (24 lessons)",
            "lessons_count": 24,
            "price_per_lesson": 400,
            "total_price": 9600,
            "not_true_price": 10000,
        },
        {
            "slug": "standard-adults-48",
            "name": "Standard — Adults (48 lessons)",
            "lessons_count": 48,
            "price_per_lesson": 350,
            "total_price": 16800,
            "not_true_price": 17500,
        },
    ]

    created = []
    for it in items:
        # перевіряємо існування за slug
        existing_q = await session.execute(
            select(Package).where(Package.slug == it["slug"])
        )
        existing = existing_q.scalar_one_or_none()
        if existing:
            continue

        # обчислення знижок
        not_true = it["not_true_price"]
        total = it["total_price"]
        disc_money = max(not_true - total, 0)
        # округляємо до найближчого цілого
        disc_percent = round((disc_money / not_true) * 100) if not_true else None

        # ОПИСИ (короткий + довгий)
        short_description = (
            "50-хвилинні індивідуальні заняття з чітким фокусом на результат."
        )
        long_description = (
            "Готові завдання + індивідуально створені під ваші слабкі місця і цілі. "
            "Додаткові домашні завдання (позаурочні) на всі контролі англійської: "
            "Reading, Grammar, Vocabulary, Listening, Speaking. "
            "Списки слів під теми та ваші життєві задачі (робота, подорожі, інтерв’ю). "
            "Прозорий прогрес і підтримка між уроками — краса й порядок 🧠✨"
        )

        pkg = Package(
            slug=it["slug"],
            name=it["name"],
            type=PackageType.STANDARD,
            audience=PackageAudience.ADULTS,
            short_description=short_description,
            long_description=long_description,
            lesson_duration="50",
            lessons_count=it["lessons_count"],
            currency="UAH",
            not_true_price=not_true,
            price_per_lesson=it["price_per_lesson"],
            base_price=None,  # не використовуємо
            discount_percent=disc_percent,
            discount_money=disc_money,
            total_price=total,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(pkg)
        created.append(it["slug"])

    if created:
        await session.commit()

    return {"created_slugs": created}
# ↑↑↑ КІНЕЦЬ НОВОЇ ФУНКЦІЇ ↑↑↑
