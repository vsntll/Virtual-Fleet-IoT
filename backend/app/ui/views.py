from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter()

templates = Jinja2Templates(directory="app/ui/templates")

@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: Session = Depends(get_db)):
    devices = db.query(models.Device).order_by(models.Device.last_seen.desc()).all()
    blue_count = db.query(models.Device).filter(models.Device.environment == 'blue').count()
    green_count = db.query(models.Device).filter(models.Device.environment == 'green').count()
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "devices": devices,
        "blue_count": blue_count,
        "green_count": green_count
    })

@router.get("/devices/{device_id}", response_class=HTMLResponse)
async def read_device(request: Request, device_id: str, db: Session = Depends(get_db)):
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if device:
        measurements = db.query(models.Measurement).filter(models.Measurement.device_id == device_id).order_by(models.Measurement.timestamp.desc()).limit(20).all()
        config_flags = {}
        if device.config_flags:
            try:
                config_flags = json.loads(device.config_flags)
            except json.JSONDecodeError:
                pass # Handle invalid JSON by returning empty dict
    else:
        measurements = []
        config_flags = {}
    return templates.TemplateResponse("device_detail.html", {"request": request, "device": device, "measurements": measurements, "config_flags": config_flags})

import json

import json

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

def from_json_filter(value):
    if value:
        return json.loads(value)
    return {}

templates.env.filters['from_json'] = from_json_filter

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
        latest_measurement = db.query(models.Measurement)\
            .filter(models.Measurement.device_id == device.id)\
            .filter(models.Measurement.latitude.isnot(None), models.Measurement.longitude.isnot(None))\
            .order_by(models.Measurement.timestamp.desc())\
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
