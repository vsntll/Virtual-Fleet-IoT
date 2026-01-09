from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base
import datetime
import random

class Device(Base):
    __tablename__ = "devices"

    id = Column(String, primary_key=True, index=True)
    current_version = Column(String)
    desired_version = Column(String)
    last_seen = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String)
    rollout_bucket = Column(Integer, default=lambda: random.randint(0, 99))
    environment = Column(String, default="blue")
    region = Column(String, nullable=True)
    hardware_rev = Column(String, nullable=True)

    # Reported state
    reported_sample_interval_secs = Column(Integer, default=10)
    reported_upload_interval_secs = Column(Integer, default=60)
    reported_heartbeat_interval_secs = Column(Integer, default=30)
    
    # Desired state
    desired_sample_interval_secs = Column(Integer, default=10)
    desired_upload_interval_secs = Column(Integer, default=60)
    desired_heartbeat_interval_secs = Column(Integer, default=30)
    config_flags = Column(String, nullable=True, default="{}")
    lifecycle_state = Column(String, default="new", nullable=False) # new, active, suspended, decommissioned
    auth_token = Column(String, unique=True, nullable=True, index=True)
    registered_at = Column(DateTime, nullable=True)
    lifecycle_state = Column(String, default="new", nullable=False) # new, active, suspended, decommissioned
    auth_token = Column(String, unique=True, nullable=True, index=True)
    registered_at = Column(DateTime, nullable=True)

    measurements = relationship("Measurement", back_populates="device")
    errors = relationship("DeviceError", back_populates="device")

class Firmware(Base):
    __tablename__ = "firmware"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String, unique=True, index=True)
    checksum = Column(String)
    url = Column(String)
    rollout_group = Column(String, default="default")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    rollout_phase = Column(String, default="100%")
    target_percent = Column(Integer, default=100)
    required_region = Column(String, nullable=True)
    required_hardware_rev = Column(String, nullable=True)
    metrics_summary = Column(String, nullable=True)

class Measurement(Base):
    __tablename__ = "measurements"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, ForeignKey("devices.id"))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    temp = Column(Float)
    humidity = Column(Float)
    battery = Column(Float)
    sequence_number = Column(Integer)
    firmware_version = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    speed = Column(Float, nullable=True)

    device = relationship("Device", back_populates="measurements")

class DeviceError(Base):
    __tablename__ = "device_errors"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, ForeignKey("devices.id"))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    firmware_version = Column(String)
    error_code = Column(String)
    error_message = Column(String)

    device = relationship("Device", back_populates="errors")

class FleetSetting(Base):
    __tablename__ = "fleet_settings"

    id = Column(Integer, primary_key=True, index=True)
    num_devices = Column(Integer, default=15)
    sample_interval_secs = Column(Integer, default=10)
    upload_interval_secs = Column(Integer, default=60)
    heartbeat_interval_secs = Column(Integer, default=30)
