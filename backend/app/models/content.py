"""Каталог контенту кабінету."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.db.database import Base


class Idea(Base):
    __tablename__ = "ws_ideas"

    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey("admin_users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False, default="")
    format = Column(String(16), nullable=False, default="post")
    topic = Column(String(120), nullable=False, default="")
    source = Column(String(16), nullable=False, default="original")
    reference_url = Column(String(500), nullable=False, default="")
    priority = Column(Integer, nullable=False, default=2)
    status = Column(String(16), nullable=False, default="new")
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
