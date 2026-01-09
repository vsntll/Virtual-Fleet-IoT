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

class FirmwareUpdatePayload(BaseModel):
    target_percent: int

router = APIRouter()

@router.get("/latest")
def get_latest_firmware(device_id: str, db: Session = Depends(get_db)):
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if not device:
        return Response(status_code=204)
        
    # 1. Direct assignment
    if device.desired_version:
        firmware = db.query(models.Firmware).filter(models.Firmware.version == device.desired_version).first()
        if firmware and firmware.version != device.current_version:
            return FirmwareResponse(version=firmware.version, checksum=firmware.checksum, url=firmware.url)

    # 2. Segment-based filtering
    fw_query = db.query(models.Firmware)
    if device.region:
        fw_query = fw_query.filter(
            (models.Firmware.required_region == None) | (models.Firmware.required_region == device.region)
        )
    if device.hardware_rev:
        fw_query = fw_query.filter(
            (models.Firmware.required_hardware_rev == None) | (models.Firmware.required_hardware_rev == device.hardware_rev)
        )

    latest_firmware = fw_query.order_by(models.Firmware.created_at.desc()).first()

    if not latest_firmware or latest_firmware.version == device.current_version:
        return Response(status_code=204)

    # 3. Blue/Green logic
    if latest_firmware.rollout_group == "green" and device.environment != "green":
        return Response(status_code=204)

    # 4. Canary/Staged rollout logic
    if device.rollout_bucket < latest_firmware.target_percent:
        return FirmwareResponse(version=latest_firmware.version, checksum=latest_firmware.checksum, url=latest_firmware.url)

    # 5. Default: No applicable update
    return Response(status_code=204)

@router.get("/binary/{firmware_id}")
def download_firmware_binary(firmware_id: int, db: Session = Depends(get_db)):
    firmware = db.query(models.Firmware).filter(models.Firmware.id == firmware_id).first()
    if not firmware:
        raise HTTPException(status_code=404, detail="Firmware not found")
    
    # In a real scenario, this would return a file response.
    # Here, we'll just return a dummy binary content.
    dummy_content = f"firmware_binary_content_for_{firmware.version}".encode()
    return Response(content=dummy_content, media_type="application/octet-stream")

@router.patch("/{version}")
def update_firmware_rollout(version: str, payload: FirmwareUpdatePayload, db: Session = Depends(get_db)):
    firmware = db.query(models.Firmware).filter(models.Firmware.version == version).first()
    if not firmware:
        raise HTTPException(status_code=404, detail="Firmware not found")

    if not (0 <= payload.target_percent <= 100):
        raise HTTPException(status_code=400, detail="Target percent must be between 0 and 100")

    firmware.target_percent = payload.target_percent
    db.commit()
    db.refresh(firmware)

    return firmware
