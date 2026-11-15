"""Робочий простір кабінету: спільні блоки, завдання, нотатки, звіти.

Спільні блоки (коментарі, оцінки, файли, позначки «прочитано») чіпляються
до будь-якої сутності парою `entity_type` + `entity_id`. Так один і той самий
код коментарів працює для завдань, звітів, а далі — для креативів і учнів,
без окремої таблиці під кожен розділ.

Зовнішнього ключа на entity_id немає свідомо: він може вказувати на різні
таблиці. Цілісність тримає API: сутність перевіряється перед кожним записом,
а при видаленні сутності її коментарі, оцінки й файли прибираються разом із нею.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Index, Integer, JSON,
    String, Text, UniqueConstraint,
)

from app.db.database import Base


def _now():
    return datetime.now(timezone.utc)


# ============================================================ спільні блоки

class Comment(Base):
    __tablename__ = "ws_comments"
    __table_args__ = (Index("ix_ws_comments_entity", "entity_type", "entity_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(32), nullable=False)
    entity_id   = Column(Integer, nullable=False)
    author_id   = Column(Integer, ForeignKey("admin_users.id"), nullable=False)
    body        = Column(Text, nullable=False)
    edited      = Column(Boolean, nullable=False, default=False)
    created_at  = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at  = Column(DateTime(timezone=True), nullable=False, default=_now)


class Review(Base):
    """Оцінка: у кожного адміна одна на сутність, бал 1–10 необовʼязковий."""
    __tablename__ = "ws_reviews"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "author_id", name="uq_ws_reviews_one_per_author"),
        CheckConstraint("score is null or (score >= 1 and score <= 10)", name="score"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(32), nullable=False)
    entity_id   = Column(Integer, nullable=False)
    author_id   = Column(Integer, ForeignKey("admin_users.id"), nullable=False)
    score       = Column(Integer, nullable=True)
    body        = Column(Text, nullable=False, default="")
    created_at  = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at  = Column(DateTime(timezone=True), nullable=False, default=_now)


class Attachment(Base):
    """Файл на диску сервера. `stored_name` випадковий, оригінальна назва — лише для показу."""
    __tablename__ = "ws_attachments"
    __table_args__ = (Index("ix_ws_attachments_entity", "entity_type", "entity_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type   = Column(String(32), nullable=False)
    entity_id     = Column(Integer, nullable=False)
    stored_name   = Column(String(64), nullable=False, unique=True)
    original_name = Column(String(255), nullable=False)
    mime          = Column(String(100), nullable=False)
    kind          = Column(String(16), nullable=False)          # image | video | document
    size_bytes    = Column(Integer, nullable=False)
    uploaded_by   = Column(Integer, ForeignKey("admin_users.id"), nullable=False)
    created_at    = Column(DateTime(timezone=True), nullable=False, default=_now)


class AuditLog(Base):
    """Хто, що, коли. Без паролів, токенів і персональних даних — лише короткий опис."""
    __tablename__ = "ws_audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor_id    = Column(Integer, ForeignKey("admin_users.id"), nullable=True, index=True)
    action      = Column(String(64), nullable=False, index=True)
    entity_type = Column(String(32), nullable=True)
    entity_id   = Column(Integer, nullable=True)
    summary     = Column(String(300), nullable=False, default="")
    created_at  = Column(DateTime(timezone=True), nullable=False, default=_now, index=True)


class ReadMark(Base):
    """Коли адмін востаннє відкривав сутність. Звідси лічильники непрочитаного."""
    __tablename__ = "ws_read_marks"
    __table_args__ = (UniqueConstraint("user_id", "entity_type", "entity_id", name="uq_ws_read_marks_entity"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id     = Column(Integer, ForeignKey("admin_users.id"), nullable=False)
    entity_type = Column(String(32), nullable=False)
    entity_id   = Column(Integer, nullable=False)
    seen_at     = Column(DateTime(timezone=True), nullable=False, default=_now)


class LoginAttempt(Base):
    """Спроби входу — для ліміту. Пароль не зберігається, лише пошта, IP і результат."""
    __tablename__ = "admin_login_attempts"
    __table_args__ = (Index("ix_admin_login_attempts_email_at", "email", "created_at"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    email      = Column(String(200), nullable=False)
    ip         = Column(String(64), nullable=True, index=True)
    success    = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


# ============================================================ розділи

class TaskStatus:
    NEW = "new"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"
    ALL = (NEW, IN_PROGRESS, REVIEW, DONE)


class Task(Base):
    __tablename__ = "ws_tasks"
    __table_args__ = (
        CheckConstraint("status in ('new', 'in_progress', 'review', 'done')", name="status"),
        CheckConstraint("priority in ('P0', 'P1', 'P2')", name="priority"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    title       = Column(String(200), nullable=False)
    description = Column(Text, nullable=False, default="")
    author_id   = Column(Integer, ForeignKey("admin_users.id"), nullable=False, index=True)
    assignee_id = Column(Integer, ForeignKey("admin_users.id"), nullable=False, index=True)
    status      = Column(String(16), nullable=False, default=TaskStatus.NEW, index=True)
    priority    = Column(String(2), nullable=False, default="P1")
    due_date    = Column(Date, nullable=True, index=True)
    tags        = Column(JSON, nullable=False, default=list)
    # Повʼязана сутність, необовʼязково: report / content / student + id.
    related_type = Column(String(32), nullable=True)
    related_id   = Column(Integer, nullable=True)

    created_at  = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at  = Column(DateTime(timezone=True), nullable=False, default=_now)
    done_at     = Column(DateTime(timezone=True), nullable=True)
    # Остання подія (правка, зміна статусу, коментар) і хто її зробив —
    # для лічильника непрочитаного: своя дія не повинна світитися «новим».
    activity_at    = Column(DateTime(timezone=True), nullable=False, default=_now)
    activity_by_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True)


class Note(Base):
    """Особиста нотатка. Приватну бачить ТІЛЬКИ автор — owner теж ні."""
    __tablename__ = "ws_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    author_id  = Column(Integer, ForeignKey("admin_users.id"), nullable=False, index=True)
    title      = Column(String(200), nullable=False, default="")
    body       = Column(Text, nullable=False, default="")
    pinned     = Column(Boolean, nullable=False, default=False)
    shared     = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class ReportStatus:
    NEW = "new"
    REVIEW = "review"
    ACCEPTED = "accepted"
    REWORK = "rework"
    ALL = (NEW, REVIEW, ACCEPTED, REWORK)


REPORT_KINDS = ("marketing", "analytics", "development", "sales", "other")


class Report(Base):
    __tablename__ = "ws_reports"
    __table_args__ = (
        CheckConstraint("status in ('new', 'review', 'accepted', 'rework')", name="status"),
        CheckConstraint("kind in ('marketing', 'analytics', 'development', 'sales', 'other')", name="kind"),
        CheckConstraint("source in ('manual', 'api')", name="source"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    title     = Column(String(200), nullable=False)
    kind      = Column(String(16), nullable=False, default="other", index=True)
    agent     = Column(String(120), nullable=False, default="")    # агент / джерело, вільне поле
    body      = Column(Text, nullable=False, default="")
    tags      = Column(JSON, nullable=False, default=list)
    status    = Column(String(16), nullable=False, default=ReportStatus.NEW, index=True)
    # manual — завантажив адмін руками; api — колись прийде від агента автоматично.
    source    = Column(String(8), nullable=False, default="manual")
    author_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    activity_at    = Column(DateTime(timezone=True), nullable=False, default=_now)
    activity_by_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
