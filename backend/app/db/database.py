# app/db/database.py
from __future__ import annotations
from typing import AsyncGenerator
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
metadata = MetaData(naming_convention=NAMING)

class Base(DeclarativeBase):
    metadata = metadata

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug_sql,
    pool_pre_ping=True,
    future=True,
)

async_session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session

async def create_all():
    # ВАЖЛИВО: імпортуємо моделі, щоб вони зареєструвалися в metadata
    from app.models.package import Package  # noqa
    from app.models.certificate import Certificate  # noqa
    from app.models.lead import Lead  # noqa
    from app.models.admin_user import AdminUser  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
