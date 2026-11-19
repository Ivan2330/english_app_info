"""Каталог контенту кабінету."""
from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint

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


class Creative(Base):
    __tablename__ = "ws_creatives"

    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey("admin_users.id"), nullable=False, index=True)
    idea_id = Column(Integer, ForeignKey("ws_ideas.id"), nullable=True, unique=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False, default="")
    format = Column(String(16), nullable=False)
    purpose = Column(String(16), nullable=False)
    topic = Column(String(120), nullable=False, default="")
    status = Column(String(20), nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=True, index=True)
    published_on = Column(Date, nullable=True)
    caption = Column(Text, nullable=False, default="")
    hashtags = Column(Text, nullable=False, default="")
    cta = Column(String(500), nullable=False, default="")
    notes = Column(Text, nullable=False, default="")
    version = Column(Integer, nullable=False, default=1)
    tags = Column(JSON, nullable=False, default=list)
    published_url = Column(String(500), nullable=False, default="")
    reach = Column(Integer, nullable=True)
    saves = Column(Integer, nullable=True)
    shares = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class CreativeMedia(Base):
    __tablename__ = "ws_creative_media"

    id = Column(Integer, primary_key=True)
    creative_id = Column(Integer, ForeignKey("ws_creatives.id"), nullable=False, index=True)
    position = Column(Integer, nullable=False)
    current_version = Column(Integer, nullable=False, default=1)


class CreativeMediaVersion(Base):
    __tablename__ = "ws_creative_media_versions"
    __table_args__ = (UniqueConstraint("media_id", "version", name="uq_creative_media_version"),)

    id = Column(Integer, primary_key=True)
    media_id = Column(Integer, ForeignKey("ws_creative_media.id"), nullable=False)
    version = Column(Integer, nullable=False)
    stored_name = Column(String(64), nullable=False, unique=True)
    original_name = Column(String(255), nullable=False)
    mime = Column(String(100), nullable=False)
    kind = Column(String(16), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    has_thumbnail = Column(Integer, nullable=False, default=0)
    uploader_id = Column(Integer, ForeignKey("admin_users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


CREATIVE_CRITERIA = ("idea", "design", "copy", "brand", "advertising")


class CreativeReview(Base):
    __tablename__ = "ws_creative_reviews"
    __table_args__ = (
        UniqueConstraint("creative_id", "author_id", name="uq_creative_review_per_author"),
        CheckConstraint(" AND ".join(f"{field} BETWEEN 1 AND 5" for field in CREATIVE_CRITERIA), name="scores"),
    )

    id = Column(Integer, primary_key=True)
    creative_id = Column(Integer, ForeignKey("ws_creatives.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("admin_users.id"), nullable=False)
    idea = Column(Integer, nullable=False)
    design = Column(Integer, nullable=False)
    copy = Column(Integer, nullable=False)
    brand = Column(Integer, nullable=False)
    advertising = Column(Integer, nullable=False)
    comment = Column(Text, nullable=False, default="")
    updated_at = Column(DateTime(timezone=True), nullable=False)
