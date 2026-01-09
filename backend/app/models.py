from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, text
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
    desired_state = Column(String, nullable=True)
    reported_state = Column(String, nullable=True)
    config_flags = Column(String, nullable=True, default="{}")
    lifecycle_state = Column(String, default="new", nullable=False, server_default="new") # Added server_default
    auth_token = Column(String, unique=True, nullable=True, index=True)
    registered_at = Column(DateTime, nullable=True, server_default=text("CURRENT_TIMESTAMP")) # Added server_default

    measurements = relationship("Measurement", back_populates="device")
    errors = relationship("DeviceError", back_populates="device")
    metrics = relationship("Metric", backref="device_rel") # Using backref for simplicity
    alerts = relationship("Alert", backref="device_rel") # Using backref for simplicity

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
    signature = Column(String, nullable=True)
    rollout_status = Column(String, default="active", nullable=False) # new field

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

class Metric(Base):
    __tablename__ = "metrics"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    metric_name = Column(String)
    metric_value = Column(Float)
    device_id = Column(String, ForeignKey("devices.id"), nullable=True)
    firmware_version = Column(String, nullable=True)
    # group_id - will add if group functionality is implemented

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    device_id = Column(String, ForeignKey("devices.id"), nullable=True)
    firmware_version = Column(String, nullable=True)
    alert_type = Column(String)
    severity = Column(String) # e.g., "info", "warning", "critical"
    message = Column(String)
    is_active = Column(Boolean, default=True)
