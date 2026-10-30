from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class LegendArtwork(Base):
    __tablename__ = 'legend_artwork'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    legend_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('symbol_legends.id'), index=True)
    png: Mapped[bytes] = mapped_column(LargeBinary(length=2 * 1024 * 1024))
    sha256: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
