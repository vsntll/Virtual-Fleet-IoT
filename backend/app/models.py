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
    sequence_number = Column(Integer)

    device = relationship("Device", back_populates="measurements")

class FleetSetting(Base):
    __tablename__ = "fleet_settings"

    id = Column(Integer, primary_key=True, index=True)
    num_devices = Column(Integer, default=15)
    sample_interval_secs = Column(Integer, default=10)
    upload_interval_secs = Column(Integer, default=60)
    heartbeat_interval_secs = Column(Integer, default=30)
