from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import json # Import json for parsing/serializing
import httpx # Import httpx for making HTTP requests
from typing import Optional

from .. import models
from ..database import get_db

router = APIRouter()

templates = Jinja2Templates(directory="app/ui/templates")

# Custom Jinja2 filters
def from_json_filter(value):
    if value:
        return json.loads(value)
    return {}

def to_json_filter(value):
    if value is not None:
        return json.dumps(value, indent=2) # Pretty print JSON
    return "null"

templates.env.filters['from_json'] = from_json_filter
templates.env.filters['tojson'] = to_json_filter


@router.get("/", response_class=HTMLResponse)
async def read_root(
    request: Request, 
    db: Session = Depends(get_db),
    status: Optional[str] = None,
    firmware_version: Optional[str] = None,
    environment: Optional[str] = None,
    region: Optional[str] = None,
    hardware_rev: Optional[str] = None,
    sort_by: Optional[str] = "last_seen",
    sort_order: Optional[str] = "desc",
):
    query = db.query(models.Device)

    if status:
        query = query.filter(models.Device.status == status)
    if firmware_version:
        query = query.filter(models.Device.current_version == firmware_version)
    if environment:
        query = query.filter(models.Device.environment == environment)
    if region:
        query = query.filter(models.Device.region == region)
    if hardware_rev:
        query = query.filter(models.Device.hardware_rev == hardware_rev)

    if sort_by:
        # Basic protection against SQL injection by only allowing known columns
        if hasattr(models.Device, sort_by):
            if sort_order == "desc":
                query = query.order_by(getattr(models.Device, sort_by).desc())
            else:
                query = query.order_by(getattr(models.Device, sort_by).asc())
        else:
            query = query.order_by(models.Device.last_seen.desc()) # Default sort if invalid sort_by
    else:
        query = query.order_by(models.Device.last_seen.desc()) # Default sort

    devices = query.all()
    blue_count = db.query(models.Device).filter(models.Device.environment == 'blue').count()
    green_count = db.query(models.Device).filter(models.Device.environment == 'green').count()
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "devices": devices,
        "blue_count": blue_count,
        "green_count": green_count,
        "current_status": status,
        "current_firmware_version": firmware_version,
        "current_environment": environment,
        "current_region": region,
        "current_hardware_rev": hardware_rev,
        "current_sort_by": sort_by,
        "current_sort_order": sort_order,
        "available_statuses": ["online", "offline", "error"], # Example statuses
        "available_environments": ["blue", "green"], # Example environments
        # Dynamically fetch available firmware versions, regions, hardware_revs from DB
        "available_firmware_versions": [fv.version for fv in db.query(models.Firmware.version).distinct().all()],
        "available_regions": [r.region for r in db.query(models.Device.region).filter(models.Device.region.isnot(None)).distinct().all()],
        "available_hardware_revs": [hr.hardware_rev for hr in db.query(models.Device.hardware_rev).filter(models.Device.hardware_rev.isnot(None)).distinct().all()],
    })

@router.get("/devices/{device_id}", response_class=HTMLResponse)
async def read_device(request: Request, device_id: str, db: Session = Depends(get_db)):
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if device:
        measurements = db.query(models.Measurement).filter(models.Measurement.device_id == device_id).order_by(models.Measurement.timestamp.desc()).limit(20).all()
        
        # Generic shadow states
        desired_state = {}
        if device.desired_state:
            try:
                desired_state = json.loads(device.desired_state)
            except json.JSONDecodeError:
                pass
        
        reported_state = {}
        if device.reported_state:
            try:
                reported_state = json.loads(device.reported_state)
            except json.JSONDecodeError:
                pass
        
        # Compare desired and reported states to highlight differences
        shadow_differences = {}
        all_keys = sorted(list(set(desired_state.keys()).union(reported_state.keys())))
        for key in all_keys:
            desired_value = desired_state.get(key)
            reported_value = reported_state.get(key)
            if desired_value != reported_value:
                shadow_differences[key] = {
                    "desired": desired_value,
                    "reported": reported_value,
                    "diff": True
                }
            else:
                shadow_differences[key] = {
                    "desired": desired_value,
                    "reported": reported_value,
                    "diff": False
                }
    else:
        measurements = []
        desired_state = {}
        reported_state = {}
        shadow_differences = {}

    return templates.TemplateResponse("device_detail.html", {
        "request": request, 
        "device": device, 
        "measurements": measurements, 
        "desired_state": desired_state,
        "reported_state": reported_state,
        "shadow_differences": shadow_differences
    })

@router.get("/devices/{device_id}/analysis", response_class=HTMLResponse)
async def read_device_analysis(request: Request, device_id: str, db: Session = Depends(get_db)):
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if device:
        measurements_data = db.query(models.Measurement).filter(models.Measurement.device_id == device_id).order_by(models.Measurement.timestamp.asc()).all()
        # Manually serialize to what we need for the chart, including converting datetime
        measurements = json.dumps([
            {
                "timestamp": m.timestamp.isoformat(),
                "temp": m.temp
            } for m in measurements_data
        ])
    else:
        measurements = "[]"
    return templates.TemplateResponse("device_analysis.html", {"request": request, "device": device, "measurements": measurements})


@router.get("/firmware_rollouts", response_class=HTMLResponse)
async def read_firmware_rollouts(request: Request, db: Session = Depends(get_db)):
    firmware_versions = db.query(models.Firmware).order_by(models.Firmware.created_at.desc()).all()
    return templates.TemplateResponse("firmware_rollouts.html", {
        "request": request,
        "firmware_versions": firmware_versions
    })

@router.get("/map", response_class=HTMLResponse)
async def map_view(request: Request, db: Session = Depends(get_db)):
    # Fetch all devices
    devices = db.query(models.Device).all()
    devices_data = []

    for device in devices:
        # Get the latest measurement with location data for each device
        latest_measurement = db.query(models.Measurement)
            .filter(models.Measurement.device_id == device.id)
            .filter(models.Measurement.latitude.isnot(None), models.Measurement.longitude.isnot(None))
            .order_by(models.Measurement.timestamp.desc())
            .first()

        if latest_measurement:
            devices_data.append({
                "id": device.id,
                "latitude": latest_measurement.latitude,
                "longitude": latest_measurement.longitude,
                "current_version": device.current_version,
                "status": device.status,
                "environment": device.environment,
            })
    
    return templates.TemplateResponse("map_view.html", {
        "request": request,
        "devices_data": devices_data
    })

@router.get("/alerts", response_class=HTMLResponse)
async def read_alerts(request: Request, db: Session = Depends(get_db)):
    alerts = db.query(models.Alert).filter(models.Alert.is_active == True).order_by(models.Alert.timestamp.desc()).all()
    return templates.TemplateResponse("alerts.html", {
        "request": request,
        "alerts": alerts
    })

@router.get("/logs", response_class=HTMLResponse)
async def view_logs(
    request: Request, 
    limit: int = 100, 
    level: Optional[str] = None,
    device_id: Optional[str] = None,
    firmware_version: Optional[str] = None
):
    async with httpx.AsyncClient() as client:
        # Construct query parameters
        params = {"limit": limit}
        if level:
            params["level"] = level
        if device_id:
            params["device_id"] = device_id
        if firmware_version:
            params["firmware_version"] = firmware_version

        # Assuming the backend API is running on localhost:8000
        response = await client.get("http://localhost:8000/api/fleet/logs", params=params)
        response.raise_for_status() # Raise an exception for HTTP errors
        logs_data = response.json()
    
    return templates.TemplateResponse("logs.html", {
        "request": request,
        "logs": logs_data.get("logs", []),
        "current_limit": limit,
        "current_level": level,
        "current_device_id": device_id,
        "current_firmware_version": firmware_version,
        "available_levels": ["INFO", "WARNING", "ERROR", "CRITICAL"], # Example levels
        # You might want to fetch actual device_ids and firmware_versions from DB
        "available_device_ids": ["device-1", "device-2"], # Placeholder
        "available_firmware_versions": ["1.0.0", "1.1.0"], # Placeholder
    })