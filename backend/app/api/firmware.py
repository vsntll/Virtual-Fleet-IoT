from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from typing import Optional, List
import logging

from .. import models
from ..database import get_db

# Pydantic models for request/response
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class FirmwareResponse(BaseModel):
    version: str
    checksum: str
    url: str
    rollout_phase: str
    target_percent: int
    rollout_status: str # Added rollout_status to response

class FirmwareUpdateTargetPercentPayload(BaseModel):
    target_percent: int

class FirmwareRollbackPayload(BaseModel):
    rollback_version: str

router = APIRouter()

@router.get("/latest")
def get_latest_firmware(device_id: str, db: Session = Depends(get_db)):
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if not device:
        logger.warning("Device not found for latest firmware check", extra={"device_id": device_id})
        return Response(status_code=204)
        
    # 1. Direct assignment
    if device.desired_version:
        firmware = db.query(models.Firmware).filter(models.Firmware.version == device.desired_version).first()
        if firmware and firmware.version != device.current_version:
            # Check if rollout is active
            if firmware.rollout_status != "active":
                logger.info(
                    "Desired firmware found but rollout is not active",
                    extra={"device_id": device_id, "firmware_version": firmware.version, "rollout_status": firmware.rollout_status}
                )
                return Response(status_code=204)

            logger.info(
                "Serving directly assigned desired firmware",
                extra={"device_id": device_id, "firmware_version": firmware.version}
            )
            return FirmwareResponse(
                version=firmware.version,
                checksum=firmware.checksum,
                url=firmware.url,
                rollout_phase=firmware.rollout_phase,
                target_percent=firmware.target_percent,
                rollout_status=firmware.rollout_status
            )

    # 2. Segment-based filtering
    fw_query = db.query(models.Firmware).filter(models.Firmware.rollout_status == "active") # Only consider active rollouts
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
        logger.info(
            "No new active firmware or device is up to date",
            extra={"device_id": device_id, "current_version": device.current_version, "latest_active_firmware": latest_firmware.version if latest_firmware else "N/A"}
        )
        return Response(status_code=204)

    # 3. Blue/Green logic
    if latest_firmware.rollout_group == "green" and device.environment != "green":
        logger.info(
            "Firmware for green environment but device is not in green environment",
            extra={"device_id": device_id, "firmware_version": latest_firmware.version, "device_environment": device.environment}
        )
        return Response(status_code=204)

    # 4. Canary/Staged rollout logic
    if device.rollout_bucket < latest_firmware.target_percent:
        logger.info(
            "Serving latest active firmware based on rollout percentage",
            extra={"device_id": device_id, "firmware_version": latest_firmware.version, "target_percent": latest_firmware.target_percent, "rollout_bucket": device.rollout_bucket}
        )
        return FirmwareResponse(
            version=latest_firmware.version,
            checksum=latest_firmware.checksum,
            url=latest_firmware.url,
            rollout_phase=latest_firmware.rollout_phase,
            target_percent=latest_firmware.target_percent,
            rollout_status=latest_firmware.rollout_status
        )

    # 5. Default: No applicable update
    logger.info("No applicable firmware update found for device", extra={"device_id": device_id})
    return Response(status_code=204)

@router.get("/binary/{version_str}")
def download_firmware_binary(version_str: str, db: Session = Depends(get_db)):
    firmware = db.query(models.Firmware).filter(models.Firmware.version == version_str).first()
    if not firmware:
        logger.warning("Firmware not found for download", extra={"firmware_version": version_str})
        raise HTTPException(status_code=404, detail="Firmware not found")
    
    # In a real scenario, this would return a file response.
    # Here, we'll just return a dummy binary content.
    dummy_content = f"firmware_binary_content_for_{firmware.version}".encode()
    logger.info("Serving firmware binary", extra={"firmware_version": firmware.version, "checksum": firmware.checksum})
    return Response(content=dummy_content, media_type="application/octet-stream")

@router.patch("/{version}/update_rollout_percent")
def update_firmware_rollout_percent(version: str, payload: FirmwareUpdateTargetPercentPayload, db: Session = Depends(get_db)):
    firmware = db.query(models.Firmware).filter(models.Firmware.version == version).first()
    if not firmware:
        logger.warning("Firmware not found for rollout percent update", extra={"firmware_version": version})
        raise HTTPException(status_code=404, detail="Firmware not found")

    if not (0 <= payload.target_percent <= 100):
        raise HTTPException(status_code=400, detail="Target percent must be between 0 and 100")

    firmware.target_percent = payload.target_percent
    db.commit()
    db.refresh(firmware)
    logger.info(
        "Firmware rollout target percent updated",
        extra={"firmware_version": firmware.version, "new_target_percent": firmware.target_percent}
    )
    return firmware

@router.patch("/{version}/pause_rollout")
def pause_rollout(version: str, db: Session = Depends(get_db)):
    firmware = db.query(models.Firmware).filter(models.Firmware.version == version).first()
    if not firmware:
        logger.warning("Firmware not found for pause rollout", extra={"firmware_version": version})
        raise HTTPException(status_code=404, detail="Firmware not found")
    
    firmware.rollout_status = "paused"
    db.commit()
    db.refresh(firmware)
    logger.info("Firmware rollout paused", extra={"firmware_version": firmware.version})
    return {"message": f"Rollout for firmware {version} paused."}

@router.patch("/{version}/resume_rollout")
def resume_rollout(version: str, db: Session = Depends(get_db)):
    firmware = db.query(models.Firmware).filter(models.Firmware.version == version).first()
    if not firmware:
        logger.warning("Firmware not found for resume rollout", extra={"firmware_version": version})
        raise HTTPException(status_code=404, detail="Firmware not found")
    
    firmware.rollout_status = "active"
    db.commit()
    db.refresh(firmware)
    logger.info("Firmware rollout resumed", extra={"firmware_version": firmware.version})
    return {"message": f"Rollout for firmware {version} resumed."}

@router.patch("/{version}/rollback")
def rollback_firmware(version: str, payload: FirmwareRollbackPayload, db: Session = Depends(get_db)):
    current_firmware = db.query(models.Firmware).filter(models.Firmware.version == version).first()
    if not current_firmware:
        logger.warning("Current firmware not found for rollback", extra={"firmware_version": version})
        raise HTTPException(status_code=404, detail="Current firmware not found")
    
    rollback_target_firmware = db.query(models.Firmware).filter(models.Firmware.version == payload.rollback_version).first()
    if not rollback_target_firmware:
        logger.warning("Rollback target firmware not found", extra={"rollback_version": payload.rollback_version})
        raise HTTPException(status_code=404, detail="Rollback target firmware not found")

    # Set all devices currently on 'version' to the 'rollback_version'
    devices_to_rollback = db.query(models.Device).filter(models.Device.current_version == version).all()
    for device in devices_to_rollback:
        device.desired_version = payload.rollback_version
        db.add(device) # Mark for update
    
    current_firmware.rollout_status = "rolled_back" # Mark the current firmware's rollout as rolled back
    db.add(current_firmware) # Mark for update

    db.commit()
    logger.info(
        "Firmware rollback initiated",
        extra={"from_version": version, "to_version": payload.rollback_version, "devices_affected": len(devices_to_rollback)}
    )
    return {"message": f"Rollback from {version} to {payload.rollback_version} initiated for {len(devices_to_rollback)} devices."}