"""Сертифікат про завершення навчання.

ЩО ЗМІНИЛОСЯ ПРОТИ ПЕРШОЇ ВЕРСІЇ
================================

**Було два номери** — `serial_number` і `public_code` — і жоден не позначений
як той, що вводить людина. На папері друкується один; другий тільки плодив
питання «а який із них?». Тепер номер один: `serial_number`. `public_code`
лишається nullable заради вже виданих сертифікатів — перевірка приймає обидва.

**Не було типу сертифіката.** «Завершив курс IELTS» і «піднявся з A2 до B1» —
різні документи з різним змістом, а поле було одне: `course_title`.

**Не було прогресу.** Головне, що має бути на сертифікаті мовної школи, —
з якого рівня людина почала і на якому закінчила. Одного `level_cefr`
для цього замало.

**Не було звʼязку з реальністю.** Ні викладача, ні кількості занять,
ні періоду навчання. Сертифікат, у якому немає нічого, крім імені й назви
курсу, нічого не підтверджує.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text,
    Enum as SAEnum,
)

from app.db.database import Base


def _pg_enum(enum_cls, type_name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=type_name,
        values_callable=lambda members: [m.value for m in members],
    )


class CertificateKind(str, enum.Enum):
    """Що саме підтверджує документ.

    Від типу залежить і макет, і те, які поля обовʼязкові:
    у LEVEL головне — прогрес рівнів, у COURSE — назва курсу й обсяг.
    """
    LEVEL     = "level"       # підвищення рівня CEFR: A2 → B1
    COURSE    = "course"      # завершення тематичного курсу (IELTS, Job Ready, НМТ)
    CLUB      = "club"        # участь у Speaking Club
    CORPORATE = "corporate"   # корпоративна програма, видається компанії
    INTENSIVE = "intensive"   # короткий інтенсив або воркшоп


class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # ЄДИНИЙ номер, який друкується на сертифікаті й зашивається в QR.
    # Формат PA-2026-7K3F9X з контрольним символом — див. app/core/certificates.py
    serial_number = Column(String(64), unique=True, nullable=False, index=True)

    # Історичне поле. Нові сертифікати його не отримують, але перевірка
    # приймає і його — інакше вже видані документи перестали б працювати.
    public_code = Column(String(64), unique=True, nullable=True, index=True)

    kind = Column(
        _pg_enum(CertificateKind, "certificate_kind"),
        nullable=False, default=CertificateKind.COURSE, index=True,
    )

    # --- кому ---------------------------------------------------------------
    student_full_name = Column(String(200), nullable=False)
    # Для корпоративних сертифікатів — назва компанії
    organization = Column(String(200), nullable=True)

    # --- що саме ------------------------------------------------------------
    course_title = Column(String(200), nullable=False)
    package_slug = Column(String(160), nullable=True)   # звʼязок із каталогом

    # Прогрес: головне на сертифікаті мовної школи.
    level_from = Column(String(10), nullable=True)      # A2
    level_to   = Column(String(10), nullable=True)      # B1
    level_cefr = Column(String(10), nullable=True)      # історичне поле, лишено

    lessons_count = Column(Integer, nullable=True)
    hours         = Column(Integer, nullable=True)

    # --- коли ---------------------------------------------------------------
    started_at  = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    issued_at   = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)

    # --- хто підписав -------------------------------------------------------
    teacher_name = Column(String(200), nullable=True)
    issued_by    = Column(String(200), nullable=True, default="Prime Academy")

    pdf_url = Column(String(500), nullable=True)

    # --- анулювання ---------------------------------------------------------
    is_revoked     = Column(Boolean, nullable=False, default=False, index=True)
    revoked_at     = Column(DateTime(timezone=True), nullable=True)
    revoked_reason = Column(Text, nullable=True)

    meta = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def as_public_dict(self) -> dict:
        """Те, що віддаємо при публічній перевірці.

        Свідомо НЕ віддаємо: `meta`, внутрішні нотатки, `package_slug`.
        Перевіряльник має побачити достатньо, щоб упізнати документ,
        і не більше — сторінка перевірки відкрита для всіх.
        """
        return {
            "serial_number": self.serial_number,
            "kind": self.kind.value if self.kind else None,
            "student_full_name": self.student_full_name,
            "organization": self.organization,
            "course_title": self.course_title,
            "level_from": self.level_from,
            "level_to": self.level_to or self.level_cefr,
            "lessons_count": self.lessons_count,
            "hours": self.hours,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "issued_at": self.issued_at.isoformat() if self.issued_at else None,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "teacher_name": self.teacher_name,
            "issued_by": self.issued_by or "Prime Academy",
            "pdf_url": self.pdf_url,
        }
