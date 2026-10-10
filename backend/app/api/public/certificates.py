"""Публічна перевірка сертифіката.

Ключова зміна проти першої версії — **як шукаємо**.

Було: точний збіг із `public_code`. Тобто «pa-2025-abcd» замість
«PA-2025-ABCD» давало «сертифікат не знайдено», і людина робила висновок,
що документ підроблений. Половина звернень у підтримку — саме про це.

Стало: пошук за нормалізованим значенням (без дефісів, у верхньому регістрі)
і **по обох полях** — новому `serial_number` і старому `public_code`.
Вже видані сертифікати продовжують перевірятися, як раніше.

Ендпоінт відкритий без авторизації — так і має бути, його сенс у тому,
щоб роботодавець чи університет могли перевірити документ. Тому назовні
віддаємо лише те, що вже надруковано на самому сертифікаті.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import certificates as C
from app.db.database import get_async_session
from app.models.certificate import Certificate

router = APIRouter(prefix="/api", tags=["certificates"])


def _norm_sql(column):
    """Нормалізація на боці бази — щоб працював функціональний індекс.

    Мусить збігатися з тим, що робить `C.normalize()`: прибрати дефіси,
    підняти регістр. Індекси під це створені в міграції 0004.
    """
    return func.upper(func.replace(column, "-", ""))


@router.get("/certificates/verify")
async def verify_certificate(
    code: str = Query(..., min_length=3, max_length=80),
    session: AsyncSession = Depends(get_async_session),
):
    normalized = C.normalize(code).replace("-", "")

    stmt = select(Certificate).where(
        or_(
            _norm_sql(Certificate.serial_number) == normalized,
            _norm_sql(Certificate.public_code) == normalized,
        )
    )
    cert = (await session.execute(stmt)).scalar_one_or_none()

    if cert is None:
        # `looks_valid` дозволяє фронту розрізнити два різні випадки:
        # «такого номера немає» і «номер узагалі не схожий на наш».
        # Для людини це дуже різні повідомлення.
        return {
            "status": "invalid",
            "looks_valid": C.is_well_formed(code),
        }

    if cert.is_revoked:
        return {
            "status": "revoked",
            "serial_number": cert.serial_number,
            "revoked_at": cert.revoked_at.isoformat() if cert.revoked_at else None,
            # Причину анулювання назовні не віддаємо: це може бути
            # чутлива інформація про людину.
        }

    return {"status": "valid", **cert.as_public_dict()}


@router.get("/certificates/check-format")
async def check_format(code: str = Query(..., max_length=80)):
    """Чи схожий код на наш формат — без звернення до бази.

    Фронт викликає це перед відправкою, щоб зловити одруківку одразу.
    Контрольний символ ловить близько 99% однобуквених помилок.
    """
    return {
        "normalized": C.normalize(code),
        "looks_valid": C.is_well_formed(code),
    }
