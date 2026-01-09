from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

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

