from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from .. import models
from ..database import get_db
from pydantic import BaseModel

class FleetSettings(BaseModel):
    num_devices: int
    sample_interval_secs: int
    upload_interval_secs: int
    heartbeat_interval_secs: int

router = APIRouter()

@router.get("/settings", response_model=FleetSettings)
def get_fleet_settings(db: Session = Depends(get_db)):
    settings = db.query(models.FleetSetting).first()
    if not settings:
        settings = models.FleetSetting()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings

@router.post("/settings")
def update_fleet_settings(settings: FleetSettings, db: Session = Depends(get_db)):
    db_settings = db.query(models.FleetSetting).first()
    if not db_settings:
        db_settings = models.FleetSetting()
        db.add(db_settings)

    db_settings.num_devices = settings.num_devices
    db_settings.sample_interval_secs = settings.sample_interval_secs
    db_settings.upload_interval_secs = settings.upload_interval_secs
    db_settings.heartbeat_interval_secs = settings.heartbeat_interval_secs
    db.commit()
    db.refresh(db_settings)
    
    return {"message": "Fleet settings updated successfully. Devices will update on their next heartbeat."}

@router.get("/health")
def get_fleet_health(db: Session = Depends(get_db)):
    """
    Provides a high-level overview of fleet health, including error counts
    and device distribution per firmware version.
    """
    # Count errors per firmware version
    error_counts = (
        db.query(
            models.DeviceError.firmware_version,
            func.count(models.DeviceError.id).label("error_count"),
        )
        .group_by(models.DeviceError.firmware_version)
        .all()
    )

    # Count devices per firmware version
    device_counts = (
        db.query(
            models.Device.current_version,
            func.count(models.Device.id).label("device_count"),
        )
        .group_by(models.Device.current_version)
        .all()
    )

    # Combine metrics into a single response
    health_report = {}

    for version, count in device_counts:
        if version not in health_report:
            health_report[version] = {"device_count": 0, "error_count": 0}
        health_report[version]["device_count"] = count

    for version, count in error_counts:
        if version not in health_report:
            health_report[version] = {"device_count": 0, "error_count": 0}
        health_report[version]["error_count"] = count
    
    # Calculate failure rate
    for version, metrics in health_report.items():
        if metrics["device_count"] > 0:
            metrics["failure_rate"] = metrics["error_count"] / metrics["device_count"]
        else:
            metrics["failure_rate"] = 0

    return health_report
