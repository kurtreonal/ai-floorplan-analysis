from datetime import datetime
from sqlalchemy import Integer, JSON, DateTime, BigInteger, ForeignKey, func
from sqlalchemy.orm import Mapped,mapped_column
from app.models.base import Base


class ApplicationDefaults(Base):
    __tablename__='application_defaults'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    revision:Mapped[int]=mapped_column(Integer,nullable=False)
    document:Mapped[dict]=mapped_column(JSON,nullable=False)
    updated_by_user_id:Mapped[int]=mapped_column(BigInteger,ForeignKey('users.id'),nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,server_default=func.now(),onupdate=func.now())
