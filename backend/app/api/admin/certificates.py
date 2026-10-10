"""Керування сертифікатами в кабінеті менеджера.

ЩО ЗМІНИЛОСЯ ПРОТИ ПЕРШОЇ ВЕРСІЇ
================================

**Номер більше не вводиться руками.** Раніше `serial_number` і `public_code`
були обовʼязковими полями форми, і менеджер вигадував їх сам. Це давало
і колізії, і номери без контрольного символу, які потім не проходили
перевірку на сайті. Тепер номер генерує `generate_serial()`.

**Не було списку.** Створити сертифікат можна було, а побачити видані — ні.
Менеджер не міг ані знайти документ за прізвищем, ані перевірити, чи вже
видавав його цій людині.

**Не було анулювання як дії.** Був прапорець `is_revoked` у загальному
PATCH — без дати й без причини. Тепер це окремий ендпоінт, який проставляє
`revoked_at` і зберігає причину для внутрішнього розбору.

**Видалення.** Фізично видаляти сертифікат можна лише поки його ніхто
не бачив. Виданий документ треба анулювати, а не стирати: у людини на руках
PDF, і перевірка має відповідати «анульовано», а не «не існує».
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.auth import get_current_admin
from app.core import certificates as C
from app.core.certificate_pdf import save_pdf
from app.core.config import settings
from app.db.database import get_async_session
from app.models.admin_user import AdminUser
from app.models.certificate import Certificate, CertificateKind

# Лого для шапки PDF. Той самий файл, що й для іконок сайту.

router = APIRouter(prefix="/api/admin", tags=["admin-certificates"])


def _full(c: Certificate) -> dict:
    """Повне представлення для кабінету — з полями, яких немає в публічному."""
    return {
        **c.as_public_dict(),
        "id": c.id,
        "public_code": c.public_code,
        "package_slug": c.package_slug,
        "is_revoked": c.is_revoked,
        "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
        "revoked_reason": c.revoked_reason,
        "meta": c.meta,
        "verify_url": C.verify_url(c.serial_number, settings.site_url),
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("/certificates")
async def list_certificates(
    q: str | None = Query(None, max_length=120),
    revoked: bool | None = None,
    kind: CertificateKind | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    admin: AdminUser = Depends(get_current_admin),
):
    stmt = select(Certificate)

    if q:
        like = f"%{q.strip()}%"
        # Менеджер шукає або за прізвищем, або за номером із документа
        normalized = C.normalize(q).replace("-", "")
        stmt = stmt.where(or_(
            Certificate.student_full_name.ilike(like),
            Certificate.course_title.ilike(like),
            Certificate.organization.ilike(like),
            func.upper(func.replace(Certificate.serial_number, "-", "")).like(f"%{normalized}%"),
        ))

    if revoked is not None:
        stmt = stmt.where(Certificate.is_revoked.is_(revoked))
    if kind:
        stmt = stmt.where(Certificate.kind == kind)

    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    stmt = stmt.order_by(Certificate.issued_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()

    return {"total": total, "items": [_full(c) for c in rows]}


@router.post("/certificates")
async def create_certificate(
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    admin: AdminUser = Depends(get_current_admin),
):
    """Видати сертифікат.

    Номер генерується автоматично. Вводити його руками більше не можна:
    саморобні номери не мають контрольного символу й не проходять перевірку
    на сайті, а ще дають колізії.
    """
    if not (data.get("student_full_name") or "").strip():
        raise HTTPException(status_code=400, detail="потрібне імʼя учня")
    if not (data.get("course_title") or "").strip():
        raise HTTPException(status_code=400, detail="потрібна назва курсу")

    # Теоретична колізія на 31^5 варіантів малоймовірна, але перевірити дешево
    for _ in range(5):
        serial = C.generate_serial()
        exists = await session.scalar(
            select(func.count()).select_from(Certificate)
            .where(Certificate.serial_number == serial)
        )
        if not exists:
            break
    else:
        raise HTTPException(status_code=500, detail="не вдалося згенерувати номер")

    def _dt(key):
        raw = data.get(key)
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return None

    cert = Certificate(
        serial_number=serial,
        kind=CertificateKind(data.get("kind", "course")),
        student_full_name=data["student_full_name"].strip(),
        organization=data.get("organization"),
        course_title=data["course_title"].strip(),
        package_slug=data.get("package_slug"),
        level_from=data.get("level_from"),
        level_to=data.get("level_to"),
        lessons_count=data.get("lessons_count"),
        hours=data.get("hours"),
        started_at=_dt("started_at"),
        finished_at=_dt("finished_at"),
        valid_until=_dt("valid_until"),
        teacher_name=data.get("teacher_name"),
        issued_by=data.get("issued_by") or "Prime Academy",
        pdf_url=data.get("pdf_url"),
        meta=data.get("meta"),
    )
    session.add(cert)
    await session.commit()
    await session.refresh(cert)

    return {"ok": True, "certificate": _full(cert)}


@router.patch("/certificates/{cert_id}")
async def update_certificate(
    cert_id: int,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    admin: AdminUser = Depends(get_current_admin),
):
    """Правка виданого сертифіката.

    `serial_number` у списку дозволених полів свідомо НЕМАЄ: номер надруковано
    на документі й зашито в QR. Помилилися в даних — правимо дані; помилилися
    в самому документі — анулюємо й видаємо новий.
    """
    cert = (await session.execute(
        select(Certificate).where(Certificate.id == cert_id)
    )).scalar_one_or_none()
    if cert is None:
        raise HTTPException(status_code=404, detail="сертифікат не знайдено")

    editable = (
        "student_full_name", "organization", "course_title", "package_slug",
        "level_from", "level_to", "lessons_count", "hours",
        "teacher_name", "issued_by", "pdf_url", "meta",
    )
    for field in editable:
        if field in data:
            setattr(cert, field, data[field])

    for field in ("started_at", "finished_at", "valid_until"):
        if field in data:
            raw = data[field]
            if not raw:
                setattr(cert, field, None)
            else:
                try:
                    setattr(cert, field, datetime.fromisoformat(str(raw).replace("Z", "+00:00")))
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"погана дата в {field}")

    if "kind" in data:
        try:
            cert.kind = CertificateKind(data["kind"])
        except ValueError:
            raise HTTPException(status_code=400, detail="невідомий тип сертифіката")

    await session.commit()
    await session.refresh(cert)
    return {"ok": True, "certificate": _full(cert)}


@router.post("/certificates/{cert_id}/revoke")
async def revoke_certificate(
    cert_id: int,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    admin: AdminUser = Depends(get_current_admin),
):
    """Анулювати сертифікат.

    Окрема дія, а не прапорець у загальній правці: анулювання завжди має
    дату й причину. Причина назовні не віддається — вона може містити
    чутливу інформацію про людину.
    """
    cert = (await session.execute(
        select(Certificate).where(Certificate.id == cert_id)
    )).scalar_one_or_none()
    if cert is None:
        raise HTTPException(status_code=404, detail="сертифікат не знайдено")

    cert.is_revoked = True
    cert.revoked_at = datetime.utcnow()
    cert.revoked_reason = f"{data.get('reason') or 'без пояснення'} · {admin.email}"
    await session.commit()
    return {"ok": True}


@router.post("/certificates/{cert_id}/restore")
async def restore_certificate(
    cert_id: int,
    session: AsyncSession = Depends(get_async_session),
    admin: AdminUser = Depends(get_current_admin),
):
    """Скасувати анулювання — на випадок помилки менеджера."""
    cert = (await session.execute(
        select(Certificate).where(Certificate.id == cert_id)
    )).scalar_one_or_none()
    if cert is None:
        raise HTTPException(status_code=404, detail="сертифікат не знайдено")

    cert.is_revoked = False
    cert.revoked_at = None
    cert.revoked_reason = None
    await session.commit()
    return {"ok": True}


@router.delete("/certificates/{cert_id}")
async def delete_certificate(
    cert_id: int,
    session: AsyncSession = Depends(get_async_session),
    admin: AdminUser = Depends(get_current_admin),
):
    """Видалити фізично — тільки якщо документ ще не пішов людині.

    Виданий сертифікат стирати не можна: у людини на руках PDF із номером,
    і перевірка на сайті має відповісти «анульовано», а не «не існує».
    Друге виглядає як підробка й породжує скандал на рівному місці.

    Тому дозволяємо видалення лише поки немає PDF і документ не анульований —
    тобто це щойно створений запис, у якому знайшли помилку.
    """
    cert = (await session.execute(
        select(Certificate).where(Certificate.id == cert_id)
    )).scalar_one_or_none()
    if cert is None:
        raise HTTPException(status_code=404, detail="сертифікат не знайдено")

    if cert.pdf_url or cert.is_revoked:
        raise HTTPException(
            status_code=409,
            detail="Сертифікат уже виданий. Його можна анулювати, але не видалити: "
                   "у власника лишається документ, і перевірка має показувати "
                   "«анульовано», а не «не існує».",
        )

    await session.delete(cert)
    await session.commit()
    return {"ok": True}


@router.post("/certificates/{cert_id}/pdf")
async def generate_pdf(
    cert_id: int,
    session: AsyncSession = Depends(get_async_session),
    admin: AdminUser = Depends(get_current_admin),
):
    """Згенерувати PDF і прикріпити до сертифіката.

    Перегенерація дозволена: якщо менеджер виправив імʼя чи рівень,
    документ треба перемалювати. Номер при цьому НЕ змінюється —
    файл просто перезаписується під тією самою назвою, і всі раніше
    надіслані посилання лишаються робочими.
    """
    cert = (await session.execute(
        select(Certificate).where(Certificate.id == cert_id)
    )).scalar_one_or_none()
    if cert is None:
        raise HTTPException(status_code=404, detail="сертифікат не знайдено")

    if cert.is_revoked:
        raise HTTPException(
            status_code=409,
            detail="Сертифікат анульований. Спершу відновіть його, якщо анулювання було помилкою.",
        )

    try:
        url = save_pdf(cert)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"не вдалося згенерувати PDF: {exc}")

    cert.pdf_url = url
    await session.commit()
    await session.refresh(cert)

    return {"ok": True, "pdf_url": url, "certificate": _full(cert)}


@router.get("/certificates/stats")
async def certificates_stats(
    session: AsyncSession = Depends(get_async_session),
    admin: AdminUser = Depends(get_current_admin),
):
    """Зведення для дашборда сертифікатів."""
    total = await session.scalar(select(func.count(Certificate.id))) or 0
    revoked = await session.scalar(
        select(func.count(Certificate.id)).where(Certificate.is_revoked.is_(True))
    ) or 0

    by_kind_rows = (await session.execute(
        select(Certificate.kind, func.count(Certificate.id)).group_by(Certificate.kind)
    )).all()

    month = func.date_trunc("month", Certificate.issued_at)
    by_month_rows = (await session.execute(
        select(month.label("m"), func.count(Certificate.id))
        .group_by(month).order_by(month.desc()).limit(12)
    )).all()

    return {
        "total": total,
        "revoked": revoked,
        "active": total - revoked,
        "by_kind": {(r[0].value if r[0] else "—"): r[1] for r in by_kind_rows},
        "by_month": [
            {"month": r[0].date().isoformat()[:7], "count": r[1]}
            for r in reversed(by_month_rows)
        ],
    }
