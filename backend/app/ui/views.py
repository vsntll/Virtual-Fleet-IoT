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
    return templates.TemplateResponse("index.html", {"request": request, "devices": devices})

@router.get("/devices/{device_id}", response_class=HTMLResponse)
async def read_device(request: Request, device_id: str, db: Session = Depends(get_db)):
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if device:
        measurements = db.query(models.Measurement).filter(models.Measurement.device_id == device_id).order_by(models.Measurement.timestamp.desc()).limit(20).all()
    else:
        measurements = []
    return templates.TemplateResponse("device_detail.html", {"request": request, "device": device, "measurements": measurements})

@router.get("/devices/{device_id}/analysis", response_class=HTMLResponse)
async def read_device_analysis(request: Request, device_id: str, db: Session = Depends(get_db)):
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if device:
        measurements = db.query(models.Measurement).filter(models.Measurement.device_id == device_id).order_by(models.Measurement.timestamp.asc()).all()
    else:
        measurements = []
    return templates.TemplateResponse("device_analysis.html", {"request": request, "device": device, "measurements": measurements})
