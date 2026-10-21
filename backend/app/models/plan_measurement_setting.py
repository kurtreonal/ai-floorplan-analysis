"""Append-only plan inputs, separate from approved page scales and floor datum."""
from datetime import datetime
from sqlalchemy import BigInteger,DateTime,ForeignKey,Integer,JSON,String,UniqueConstraint,func
from sqlalchemy.orm import Mapped,mapped_column
from app.models.base import Base


class PlanMeasurementSetting(Base):
    __tablename__='plan_measurement_settings'
    __table_args__=(UniqueConstraint('floor_plan_id','revision',name='uq_plan_measurement_revision'),
        UniqueConstraint('floor_plan_id','request_id',name='uq_plan_measurement_request'))
    id:Mapped[int]=mapped_column(BigInteger,primary_key=True,autoincrement=True)
    floor_plan_id:Mapped[int]=mapped_column(BigInteger,ForeignKey('floor_plans.id',ondelete='CASCADE'),nullable=False,index=True)
    revision:Mapped[int]=mapped_column(Integer,nullable=False)
    request_id:Mapped[str]=mapped_column(String(36),nullable=False)
    actor_user_id:Mapped[int]=mapped_column(BigInteger,ForeignKey('users.id'),nullable=False)
    document:Mapped[dict]=mapped_column(JSON,nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime,server_default=func.now(),nullable=False)
