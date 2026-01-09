import logging
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
import datetime
import json
from typing import List, Optional, Dict, Any
import uuid
from uuid import UUID

from .. import models
from ..database import get_db

# Pydantic models for request/response
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# --- Authentication Dependency ---
async def authenticate_device(
    auth_token: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> models.Device:
    if auth_token is None:
        logger.warning("Authentication failed: Authorization header missing")
        raise HTTPException(status_code=401, detail="Authorization header missing")

    device = db.query(models.Device).filter(models.Device.auth_token == auth_token).first()
    if not device:
        logger.warning("Authentication failed: Invalid authentication token", extra={"auth_token": auth_token})
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    if device.lifecycle_state != "active":
        logger.warning(
            "Authentication failed: Device not active", 
            extra={"device_id": device.id, "lifecycle_state": device.lifecycle_state}
        )
        raise HTTPException(status_code=403, detail=f"Device is {device.lifecycle_state}, not active.")
    
    logger.info("Device authenticated successfully", extra={"device_id": device.id})
    return device

router = APIRouter()

# --- Pydantic Models for API ---

class RegisterPayload(BaseModel):
    boot_id: uuid.UUID

class RegisterResponse(BaseModel):
    device_id: uuid.UUID
    auth_token: uuid.UUID
    desired_sample_interval_secs: int
    desired_upload_interval_secs: int
    desired_heartbeat_interval_secs: int

class HeartbeatPayload(BaseModel):
    device_id: str
    firmware_version: str
    reported_sample_interval_secs: int
    reported_upload_interval_secs: int
    reported_heartbeat_interval_secs: int
    region: Optional[str] = None
    hardware_rev: Optional[str] = None

class DesiredStateResponse(BaseModel):
    desired_version: Optional[str]
    desired_sample_interval_secs: int
    desired_upload_interval_secs: int
    desired_heartbeat_interval_secs: int

class DeviceStatePayload(BaseModel):
    desired_sample_interval_secs: int
    desired_upload_interval_secs: int
    desired_heartbeat_interval_secs: int

class DeviceErrorPayload(BaseModel):
    firmware_version: str
    error_code: str
    error_message: str

class DeviceEnvironmentPayload(BaseModel):
    environment: str
    
class MeasurementPayload(BaseModel):
    timestamp: datetime.datetime
    temp: float
    humidity: float
    battery: float
    sequence_number: int
    firmware_version: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    speed: Optional[float] = None

class IngestPayload(BaseModel):
    device_id: str
    measurements: List[MeasurementPayload]

# --- Generic Device Shadow Models ---

class DeviceShadowPatchRequest(BaseModel):
    desired: Optional[Dict[str, Any]] = None
    reported: Optional[Dict[str, Any]] = None

class DeviceShadowResponseGeneric(BaseModel):
    desired: Dict[str, Any]
    reported: Dict[str, Any]

# --- API Endpoints ---

@router.post("/register", response_model=RegisterResponse)
def register_device(payload: RegisterPayload, db: Session = Depends(get_db)):
    existing_device = db.query(models.Device).filter(models.Device.id == str(payload.boot_id)).first()
    if existing_device:
        logger.info(
            "Device already registered, returning existing credentials", 
            extra={"boot_id": payload.boot_id, "device_id": existing_device.id}
        )
        if existing_device.auth_token:
            return RegisterResponse(
                device_id=UUID(existing_device.id),
                auth_token=UUID(existing_device.auth_token),
                desired_sample_interval_secs=existing_device.desired_sample_interval_secs,
                desired_upload_interval_secs=existing_device.desired_upload_interval_secs,
                desired_heartbeat_interval_secs=existing_device.desired_heartbeat_interval_secs,
            )
        else:
            logger.error("Device ID exists but no auth token during re-registration attempt", extra={"boot_id": payload.boot_id})
            raise HTTPException(status_code=400, detail="Device ID exists but no auth token. Malformed registration.")

    new_device_id = uuid.uuid4()
    new_auth_token = uuid.uuid4()

    new_device = models.Device(
        id=str(new_device_id),
        auth_token=str(new_auth_token),
        lifecycle_state="new",
        registered_at=datetime.datetime.utcnow(),
        desired_state=json.dumps({}),  # Initialize generic desired state
        reported_state=json.dumps({}), # Initialize generic reported state
    )
    db.add(new_device)
    db.commit()
    db.refresh(new_device)

    logger.info(
        "New device registered successfully", 
        extra={"device_id": new_device_id, "lifecycle_state": new_device.lifecycle_state}
    )
    return RegisterResponse(
        device_id=new_device_id,
        auth_token=new_auth_token,
        desired_sample_interval_secs=new_device.desired_sample_interval_secs,
        desired_upload_interval_secs=new_device.desired_upload_interval_secs,
        desired_heartbeat_interval_secs=new_device.desired_heartbeat_interval_secs,
    )

@router.post("/heartbeat", response_model=DesiredStateResponse)
def heartbeat(
    payload: HeartbeatPayload, 
    authenticated_device: models.Device = Depends(authenticate_device), 
    db: Session = Depends(get_db)
):
    device = authenticated_device 
    
    device.current_version = payload.firmware_version
    device.last_seen = datetime.datetime.utcnow()
    device.status = "online"
    
    device.reported_sample_interval_secs = payload.reported_sample_interval_secs
    device.reported_upload_interval_secs = payload.reported_upload_interval_secs
    device.reported_heartbeat_interval_secs = payload.reported_heartbeat_interval_secs

    device.region = payload.region
    device.hardware_rev = payload.hardware_rev

    db.add(device)
    db.commit()
    db.refresh(device)
    
    logger.info(
        "Heartbeat received and device state updated", 
        extra={"device_id": device.id, "firmware_version": device.current_version, "status": device.status}
    )
    return DesiredStateResponse(
        desired_version=device.desired_version,
        desired_sample_interval_secs=device.desired_sample_interval_secs,
        desired_upload_interval_secs=device.desired_upload_interval_secs,
        desired_heartbeat_interval_secs=device.desired_heartbeat_interval_secs,
    )

@router.post("/{device_id}/state", response_model=models.Device) # Assuming models.Device is a Pydantic model
def update_device_state(
    device_id: str, 
    state: DeviceStatePayload, 
    authenticated_device: models.Device = Depends(authenticate_device), 
    db: Session = Depends(get_db)
):
    if authenticated_device.id != device_id:
        logger.error("Forbidden: Attempt to update another device's state", extra={"requester_device_id": authenticated_device.id, "target_device_id": device_id})
        raise HTTPException(status_code=403, detail="Forbidden: Cannot update another device's state")
    
    device = authenticated_device

    device.desired_sample_interval_secs = state.desired_sample_interval_secs
    device.desired_upload_interval_secs = state.desired_upload_interval_secs
    device.desired_heartbeat_interval_secs = state.desired_heartbeat_interval_secs
    
    db.commit()
    db.refresh(device)
    logger.info(
        "Device specific desired intervals updated", 
        extra={"device_id": device.id, "desired_sample_interval_secs": device.desired_sample_interval_secs}
    )
    return device

@router.post("/{device_id}/environment", response_model=models.Device) # Assuming models.Device is a Pydantic model
def update_device_environment(
    device_id: str, 
    environment: DeviceEnvironmentPayload, 
    authenticated_device: models.Device = Depends(authenticate_device),
    db: Session = Depends(get_db)
):
    if authenticated_device.id != device_id:
        logger.error("Forbidden: Attempt to update another device's environment", extra={"requester_device_id": authenticated_device.id, "target_device_id": device_id})
        raise HTTPException(status_code=403, detail="Forbidden: Cannot update another device's environment")
    
    device = authenticated_device

    device.environment = environment.environment
    db.commit()
    db.refresh(device)
    logger.info(
        "Device environment updated", 
        extra={"device_id": device.id, "new_environment": device.environment}
    )
    return device

@router.post("/ingest", status_code=204)
def ingest(payload: IngestPayload, authenticated_device: models.Device = Depends(authenticate_device), db: Session = Depends(get_db)):
    if authenticated_device.id != payload.device_id:
        logger.error("Forbidden: Attempt to ingest data for another device", extra={"requester_device_id": authenticated_device.id, "payload_device_id": payload.device_id})
        raise HTTPException(status_code=403, detail="Forbidden: Cannot ingest data for another device")

    device = authenticated_device

    new_measurements = []
    for m in payload.measurements:
        new_measurements.append(
            models.Measurement(
                device_id=device.id,
                timestamp=m.timestamp,
                temp=m.temp,
                humidity=m.humidity,
                battery=m.battery,
                sequence_number=m.sequence_number,
                firmware_version=m.firmware_version,
                latitude=m.latitude,
                longitude=m.longitude,
                speed=m.speed,
            )
        )
    db.add_all(new_measurements)
    db.commit()
    logger.info(
        "Measurements ingested successfully", 
        extra={"device_id": device.id, "measurement_count": len(new_measurements)}
    )

@router.post("/{device_id}/errors", status_code=204)
def report_error(
    device_id: str, 
    payload: DeviceErrorPayload, 
    authenticated_device: models.Device = Depends(authenticate_device), 
    db: Session = Depends(get_db)
):
    if authenticated_device.id != device_id:
        logger.error("Forbidden: Attempt to report errors for another device", extra={"requester_device_id": authenticated_device.id, "target_device_id": device_id})
        raise HTTPException(status_code=403, detail="Forbidden: Cannot report errors for another device")
    
    device = authenticated_device

    error = models.DeviceError(
        device_id=device.id,
        timestamp=datetime.datetime.utcnow(),
        firmware_version=payload.firmware_version,
        error_code=payload.error_code,
        error_message=payload.error_message,
    )
    db.add(error)
    db.commit()
    logger.warning(
        "Device error reported", 
        extra={"device_id": device.id, "firmware_version": error.firmware_version, "error_code": error.error_code}
    )

# --- Generic Device Shadow Endpoints ---

@router.get("/{device_id}/shadow", response_model=DeviceShadowResponseGeneric)
def get_generic_device_shadow(
    device_id: str, 
    authenticated_device: models.Device = Depends(authenticate_device), 
    db: Session = Depends(get_db)
):
    if authenticated_device.id != device_id:
        logger.error("Forbidden: Attempt to access another device's shadow", extra={"requester_device_id": authenticated_device.id, "target_device_id": device_id})
        raise HTTPException(status_code=403, detail="Forbidden: Cannot access another device's shadow")
    
    device = authenticated_device

    desired_state_json = {}
    if device.desired_state:
        try:
            desired_state_json = json.loads(device.desired_state)
        except json.JSONDecodeError:
            logger.error(
                "Failed to decode desired_state JSON for device", 
                extra={"device_id": device.id, "desired_state_raw": device.desired_state}
            )
            pass 

    reported_state_json = {}
    if device.reported_state:
        try:
            reported_state_json = json.loads(device.reported_state)
        except json.JSONDecodeError:
            logger.error(
                "Failed to decode reported_state JSON for device", 
                extra={"device_id": device.id, "reported_state_raw": device.reported_state}
            )
            pass

    logger.info("Device shadow fetched", extra={"device_id": device.id})
    return DeviceShadowResponseGeneric(
        desired=desired_state_json,
        reported=reported_state_json,
    )

@router.patch("/{device_id}/shadow", status_code=200)
def patch_generic_device_shadow(
    device_id: str, 
    payload: DeviceShadowPatchRequest, 
    authenticated_device: models.Device = Depends(authenticate_device), 
    db: Session = Depends(get_db)
):
    if authenticated_device.id != device_id:
        logger.error("Forbidden: Attempt to update another device's shadow", extra={"requester_device_id": authenticated_device.id, "target_device_id": device_id})
        raise HTTPException(status_code=403, detail="Forbidden: Cannot update another device's shadow")
    
    device = authenticated_device
    
    updated = False
    # Update desired state (from external source, e.g., UI)
    if payload.desired is not None:
        current_desired = {}
        if device.desired_state:
            try:
                current_desired = json.loads(device.desired_state)
            except json.JSONDecodeError:
                logger.error(
                    "Failed to decode existing desired_state JSON for device during update", 
                    extra={"device_id": device.id, "desired_state_raw": device.desired_state}
                )
                pass
        
        current_desired.update(payload.desired)
        device.desired_state = json.dumps(current_desired)
        updated = True
        logger.info(
            "Desired shadow state updated", 
            extra={"device_id": device.id, "new_desired_state_patch": payload.desired}
        )
    
    # Update reported state (from device)
    if payload.reported is not None:
        current_reported = {}
        if device.reported_state:
            try:
                current_reported = json.loads(device.reported_state)
            except json.JSONDecodeError:
                logger.error(
                    "Failed to decode existing reported_state JSON for device during update", 
                    extra={"device_id": device.id, "reported_state_raw": device.reported_state}
                )
                pass
        
        current_reported.update(payload.reported)
        device.reported_state = json.dumps(current_reported)
        updated = True
        logger.info(
            "Reported shadow state updated", 
            extra={"device_id": device.id, "new_reported_state_patch": payload.reported}
        )
    
    if not updated:
         logger.warning("Shadow update attempt with no desired or reported state provided", extra={"device_id": device.id, "payload": payload.dict()})
         raise HTTPException(status_code=400, detail="No desired or reported state provided for shadow update.")

    db.commit()
    db.refresh(device)
    logger.info("Device shadow updated successfully", extra={"device_id": device.id})
    return {"status": "ok", "message": "Device shadow updated successfully."}

class TokenRotationResponse(BaseModel):
    new_auth_token: uuid.UUID

@router.post("/{device_id}/rotate_token", response_model=TokenRotationResponse)
def rotate_device_token(
    device_id: str,
    authenticated_device: models.Device = Depends(authenticate_device),
    db: Session = Depends(get_db)
):
    if authenticated_device.id != device_id:
        logger.error("Forbidden: Attempt to rotate token for another device", extra={"requester_device_id": authenticated_device.id, "target_device_id": device_id})
        raise HTTPException(status_code=403, detail="Forbidden: Cannot rotate token for another device")

    device = authenticated_device
    new_auth_token = uuid.uuid4()
    device.auth_token = str(new_auth_token)
    
    db.add(device)
    db.commit()
    db.refresh(device)

    logger.info("Device auth token rotated successfully", extra={"device_id": device.id, "new_auth_token": new_auth_token})
    return TokenRotationResponse(new_auth_token=new_auth_token)