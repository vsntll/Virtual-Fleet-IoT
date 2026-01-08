from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from typing import Optional

from .. import models
from ..database import get_db

# Pydantic models for request/response
from pydantic import BaseModel

class FirmwareResponse(BaseModel):
    version: str
    checksum: str
    url: str

router = APIRouter()

@router.get("/latest", response_model=Optional[FirmwareResponse])
def get_latest_firmware(device_id: str, db: Session = Depends(get_db)):
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    if device.desired_version:
        firmware = db.query(models.Firmware).filter(models.Firmware.version == device.desired_version).first()
        if firmware:
            return FirmwareResponse(version=firmware.version, checksum=firmware.checksum, url=firmware.url)

    # Simple logic: return the latest firmware overall if desired_version is not set
    latest_firmware = db.query(models.Firmware).order_by(models.Firmware.created_at.desc()).first()
    if latest_firmware and latest_firmware.version != device.current_version:
         return FirmwareResponse(version=latest_firmware.version, checksum=latest_firmware.checksum, url=latest_firmware.url)

    return None

@router.get("/binary/{firmware_id}")
def download_firmware_binary(firmware_id: int, db: Session = Depends(get_db)):
    firmware = db.query(models.Firmware).filter(models.Firmware.id == firmware_id).first()
    if not firmware:
        raise HTTPException(status_code=404, detail="Firmware not found")
    
    # In a real scenario, this would return a file response.
    # Here, we'll just return a dummy binary content.
    dummy_content = f"firmware_binary_content_for_{firmware.version}".encode()
    return Response(content=dummy_content, media_type="application/octet-stream")
