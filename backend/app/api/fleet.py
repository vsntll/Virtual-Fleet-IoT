from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
import json
import os
from typing import List, Dict, Any, Optional
import datetime

from .. import models
from ..database import get_db
from pydantic import BaseModel

class FleetSettings(BaseModel):
    num_devices: int
    sample_interval_secs: int
    upload_interval_secs: int
    heartbeat_interval_secs: int

class LogEntry(BaseModel):
    timestamp: datetime.datetime
    level: str
    message: str
    name: str
    filename: Optional[str] = None
    lineno: Optional[int] = None
    funcName: Optional[str] = None
    pathname: Optional[str] = None
    process: Optional[int] = None
    processName: Optional[str] = None
    thread: Optional[int] = None
    threadName: Optional[str] = None
    # Catch-all for other structured data
    extra: Dict[str, Any] = {}

class LogResponse(BaseModel):
    logs: List[LogEntry]

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

@router.get("/logs", response_model=LogResponse)
async def get_logs(
    limit: int = 100, 
    offset: int = 0,
    level: Optional[str] = None,
    device_id: Optional[str] = None,
    firmware_version: Optional[str] = None
):
    log_file_path = "backend/app.log"
    if not os.path.exists(log_file_path):
        return LogResponse(logs=[])

    all_logs = []
    with open(log_file_path, 'r') as f:
        for line in f:
            try:
                log_data = json.loads(line)
                
                # Apply filters
                if level and log_data.get("levelname", "").lower() != level.lower():
                    continue
                if device_id and log_data.get("device_id") != device_id:
                    continue
                if firmware_version and log_data.get("firmware_version") != firmware_version:
                    continue

                # Reconstruct datetime for Pydantic parsing
                if "asctime" in log_data:
                    log_data["timestamp"] = log_data.pop("asctime") # Map asctime to timestamp
                
                # Extract extra data
                extra_data = {k: v for k, v in log_data.items() if k not in ["timestamp", "levelname", "message", "name", "filename", "lineno", "funcName", "pathname", "process", "processName", "thread", "threadName"]}
                log_data["extra"] = extra_data
                
                # Use levelname as level
                if "levelname" in log_data:
                    log_data["level"] = log_data.pop("levelname")

                # Reconstruct timestamp from original string format
                log_data["timestamp"] = datetime.datetime.strptime(
                    log_data["timestamp"], "%Y-%m-%d %H:%M:%S,%f"
                )

                all_logs.append(LogEntry(**log_data))
            except json.JSONDecodeError:
                # Handle non-JSON lines if any
                continue
            except Exception as e:
                # Handle other potential parsing errors
                print(f"Error parsing log line: {e} - {line}")
                continue
    
    # Sort logs by timestamp (newest first)
    all_logs.sort(key=lambda x: x.timestamp, reverse=True)

    # Apply pagination
    paginated_logs = all_logs[offset:offset + limit]

    return LogResponse(logs=paginated_logs)

class ChaosSettingsPayload(BaseModel):
    device_id: Optional[str] = None
    chaos_flags: Dict[str, Any]

@router.patch("/chaos")
def set_chaos_flags(payload: ChaosSettingsPayload, db: Session = Depends(get_db)):
    if payload.device_id:
        devices = db.query(models.Device).filter(models.Device.id == payload.device_id).all()
    else:
        devices = db.query(models.Device).all()

    if not devices:
        raise HTTPException(status_code=404, detail="Device(s) not found.")

    for device in devices:
        current_desired_state = {}
        if device.desired_state:
            try:
                current_desired_state = json.loads(device.desired_state)
            except json.JSONDecodeError:
                pass
        
        current_desired_state.update(payload.chaos_flags)
        device.desired_state = json.dumps(current_desired_state)
        db.add(device)
    
    db.commit()
    db.refresh(device) # Refresh only the last device, or iterate and refresh all if needed

    return {"message": "Chaos flags updated successfully for specified device(s)."}
