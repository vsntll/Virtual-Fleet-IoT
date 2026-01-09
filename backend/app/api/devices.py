from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import datetime

from .. import models
from ..database import get_db

# Pydantic models for request/response
from pydantic import BaseModel

class HeartbeatPayload(BaseModel):
    device_id: str
    firmware_version: str
    reported_sample_interval_secs: int
    reported_upload_interval_secs: int
    reported_heartbeat_interval_secs: int

class DeviceState(BaseModel):
    desired_sample_interval_secs: int
    desired_upload_interval_secs: int
    desired_heartbeat_interval_secs: int

class DeviceErrorPayload(BaseModel):
    firmware_version: str
    error_code: str
    error_message: str

class DeviceEnvironment(BaseModel):
    environment: str
    
class MeasurementPayload(BaseModel):
    timestamp: datetime.datetime
    temp: float
    humidity: float
    battery: float
    sequence_number: int

class IngestPayload(BaseModel):
    device_id: str
    measurements: List[MeasurementPayload]


router = APIRouter()

@router.post("/heartbeat")
def heartbeat(payload: HeartbeatPayload, db: Session = Depends(get_db)):
    device = db.query(models.Device).filter(models.Device.id == payload.device_id).first()
    if not device:
        # Register new device
        device = models.Device(
            id=payload.device_id,
            current_version=payload.firmware_version,
            status="online",
            last_seen=datetime.datetime.utcnow(),
            reported_sample_interval_secs=payload.reported_sample_interval_secs,
            reported_upload_interval_secs=payload.reported_upload_interval_secs,
            reported_heartbeat_interval_secs=payload.reported_heartbeat_interval_secs
        )
        db.add(device)
    else:
        device.current_version = payload.firmware_version
        device.last_seen = datetime.datetime.utcnow()
        device.status = "online"
        device.reported_sample_interval_secs = payload.reported_sample_interval_secs
        device.reported_upload_interval_secs = payload.reported_upload_interval_secs
        device.reported_heartbeat_interval_secs = payload.reported_heartbeat_interval_secs

    db.commit()
    db.refresh(device)
    
    # Return desired state
    return {
        "desired_version": device.desired_version,
        "desired_sample_interval_secs": device.desired_sample_interval_secs,
        "desired_upload_interval_secs": device.desired_upload_interval_secs,
        "desired_heartbeat_interval_secs": device.desired_heartbeat_interval_secs,
    }

@router.post("/{device_id}/state")
def update_device_state(device_id: str, state: DeviceState, db: Session = Depends(get_db)):
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    device.desired_sample_interval_secs = state.desired_sample_interval_secs
    device.desired_upload_interval_secs = state.desired_upload_interval_secs
    device.desired_heartbeat_interval_secs = state.desired_heartbeat_interval_secs
    
    db.commit()
    db.refresh(device)
    return device

@router.post("/{device_id}/environment")
def update_device_environment(device_id: str, environment: DeviceEnvironment, db: Session = Depends(get_db)):
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    device.environment = environment.environment
    db.commit()
    db.refresh(device)
    return device

@router.post("/ingest")
def ingest(payload: IngestPayload, db: Session = Depends(get_db)):
    device = db.query(models.Device).filter(models.Device.id == payload.device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    for m in payload.measurements:
        db_measurement = models.Measurement(
            device_id=payload.device_id,
            timestamp=m.timestamp,
            temp=m.temp,
            humidity=m.humidity,
            battery=m.battery,
            sequence_number=m.sequence_number
        )
        db.add(db_measurement)
    
    db.commit()
    return {"status": "ok", "message": f"Ingested {len(payload.measurements)} measurements."}

@router.post("/{device_id}/errors")
def report_error(device_id: str, payload: DeviceErrorPayload, db: Session = Depends(get_db)):
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    error = models.DeviceError(
        device_id=device_id,
        timestamp=datetime.datetime.utcnow(),
        firmware_version=payload.firmware_version,
        error_code=payload.error_code,
        error_message=payload.error_message,
    )
    db.add(error)
    db.commit()

    return {"status": "ok", "message": "Error reported successfully."}
