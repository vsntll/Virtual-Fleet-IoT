from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base
import datetime

class Device(Base):
    __tablename__ = "devices"

    id = Column(String, primary_key=True, index=True)
    current_version = Column(String)
    desired_version = Column(String)
    last_seen = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String)

    measurements = relationship("Measurement", back_populates="device")

class Firmware(Base):
    __tablename__ = "firmware"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String, unique=True, index=True)
    checksum = Column(String)
    url = Column(String)
    rollout_group = Column(String, default="default")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Measurement(Base):
    __tablename__ = "measurements"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, ForeignKey("devices.id"))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    temp = Column(Float)
    humidity = Column(Float)
    battery = Column(Float)

    device = relationship("Device", back_populates="measurements")
