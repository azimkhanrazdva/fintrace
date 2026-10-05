from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from fintrace_api.db import Base


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (UniqueConstraint("external_id", "entity_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(128), index=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    display_name: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    source_account: Mapped[str] = mapped_column(String(128), index=True)
    destination_account: Mapped[str] = mapped_column(String(128), index=True)
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    timestamp_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transaction_type: Mapped[str] = mapped_column(String(64))
    channel: Mapped[str] = mapped_column(String(64))
