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
    # slot: str # Not used for now, but in blueprint
    # battery: float # Not used for now, but in blueprint
    # errors: List[str] # Not used for now, but in blueprint

class MeasurementPayload(BaseModel):
    timestamp: datetime.datetime
    temp: float
    humidity: float
    battery: float

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
            last_seen=datetime.datetime.utcnow()
        )
        db.add(device)
    else:
        device.current_version = payload.firmware_version
        device.last_seen = datetime.datetime.utcnow()
        device.status = "online"

    db.commit()
    db.refresh(device)
    
    # Return desired version if set
    return {"desired_version": device.desired_version}

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
            battery=m.battery
        )
        db.add(db_measurement)
    
    db.commit()
    return {"status": "ok", "message": f"Ingested {len(payload.measurements)} measurements."}
