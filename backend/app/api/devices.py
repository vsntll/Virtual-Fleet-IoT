from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import datetime
import json # Added import for json
from typing import List, Optional, Dict, Any
import uuid # For generating UUIDs
from uuid import UUID # For UUID type hints

from .. import models
from ..database import get_db

# Pydantic models for request/response
from pydantic import BaseModel

class HeartbeatPayload(BaseModel):
    device_id: str
    firmware_version: str
    reported_sample_interval_secs: int
    reported_upload_interval_secs: int
    reported_heartbeat_interval_secs: int
    region: Optional[str] = None
    hardware_rev: Optional[str] = None

class DeviceState(BaseModel):
    desired_sample_interval_secs: int
    desired_upload_interval_secs: int
    desired_heartbeat_interval_secs: int

class DeviceErrorPayload(BaseModel):
    firmware_version: str
    error_code: str
    error_message: str

class DeviceEnvironment(BaseModel):
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


class DeviceShadowResponse(BaseModel):
    desired_sample_interval_secs: int
    desired_upload_interval_secs: int
    desired_heartbeat_interval_secs: int
    reported_sample_interval_secs: int
    reported_upload_interval_secs: int
    reported_heartbeat_interval_secs: int

class DeviceShadowPatchPayload(BaseModel):
    reported_sample_interval_secs: int
    reported_upload_interval_secs: int
    reported_heartbeat_interval_secs: int

from typing import Any # Added for Dict[str, Any]

class DeviceShadowPatchPayload(BaseModel):
    reported_sample_interval_secs: int
    reported_upload_interval_secs: int
    reported_heartbeat_interval_secs: int

class DeviceConfigFlagsResponse(BaseModel):
    config_flags: Dict[str, Any]

class DeviceConfigFlagsPayload(BaseModel):
    config_flags: Dict[str, Any]

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
import datetime
import json
from typing import List, Optional, Dict, Any
import uuid # For generating UUIDs
from uuid import UUID # For UUID type hints

from .. import models
from ..database import get_db

async def authenticate_device(
    auth_token: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> models.Device:
    if auth_token is None:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    device = db.query(models.Device).filter(models.Device.auth_token == auth_token).first()
    if not device:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    if device.lifecycle_state != "active":
        raise HTTPException(status_code=403, detail=f"Device is {device.lifecycle_state}, not active.")
    
    return device

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
import datetime
import json
from typing import List, Optional, Dict, Any
import uuid # For generating UUIDs
from uuid import UUID # For UUID type hints

from .. import models
from ..database import get_db

async def authenticate_device(
    auth_token: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> models.Device:
    if auth_token is None:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    device = db.query(models.Device).filter(models.Device.auth_token == auth_token).first()
    if not device:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    if device.lifecycle_state != "active":
        raise HTTPException(status_code=403, detail=f"Device is {device.lifecycle_state}, not active.")
    
    return device

router = APIRouter()


@router.post("/register", response_model=RegisterResponse)
def register_device(payload: RegisterPayload, db: Session = Depends(get_db)):
    # ... (existing register_device code) ...

@router.post("/heartbeat")
def heartbeat(
    payload: HeartbeatPayload, 
    authenticated_device: models.Device = Depends(authenticate_device), 
    db: Session = Depends(get_db)
):
    # Use authenticated_device.id instead of payload.device_id for security
    device = authenticated_device 
    
    # Update device current version and last seen
    device.current_version = payload.firmware_version
    device.last_seen = datetime.datetime.utcnow()
    device.status = "online" # Mark device as online on heartbeat
    
    # Update reported state if present in heartbeat (this covers the reported shadow part)
    device.reported_sample_interval_secs = payload.reported_sample_interval_secs
    device.reported_upload_interval_secs = payload.reported_upload_interval_secs
    device.reported_heartbeat_interval_secs = payload.reported_heartbeat_interval_secs
    device.region = payload.region
    device.hardware_rev = payload.hardware_rev

    db.add(device) # Ensure the device object is marked as dirty
    db.commit()
    db.refresh(device)
    
    # Return desired state
    return {
        "desired_version": device.desired_version,
        "desired_sample_interval_secs": device.desired_sample_interval_secs,
        "desired_upload_interval_secs": device.desired_upload_interval_secs,
        "desired_heartbeat_interval_secs": device.desired_heartbeat_interval_secs,
    }

@router.post("/{device_id}/state")
def update_device_state(
    device_id: str, 
    state: DeviceState, 
    authenticated_device: models.Device = Depends(authenticate_device), 
    db: Session = Depends(get_db)
):
    # Ensure the authenticated device matches the device_id in the path
    if authenticated_device.id != device_id:
        raise HTTPException(status_code=403, detail="Forbidden: Cannot update another device's state")
    
    device = authenticated_device

    device.desired_sample_interval_secs = state.desired_sample_interval_secs
    device.desired_upload_interval_secs = state.desired_upload_interval_secs
    device.desired_heartbeat_interval_secs = state.desired_heartbeat_interval_secs
    
    db.commit()
    db.refresh(device)
    return device

@router.post("/{device_id}/environment")
def update_device_environment(
    device_id: str, 
    environment: DeviceEnvironment, 
    authenticated_device: models.Device = Depends(authenticate_device),
    db: Session = Depends(get_db)
):
    if authenticated_device.id != device_id:
        raise HTTPException(status_code=403, detail="Forbidden: Cannot update another device's environment")
    
    device = authenticated_device

    device.environment = environment.environment
    db.commit()
    db.refresh(device)
    return device

@router.post("/ingest")
def ingest(payload: IngestPayload, authenticated_device: models.Device = Depends(authenticate_device), db: Session = Depends(get_db)):
    # Ensure the authenticated device matches the device_id in the payload
    if authenticated_device.id != payload.device_id:
        raise HTTPException(status_code=403, detail="Forbidden: Cannot ingest data for another device")

    device = authenticated_device

    # ... (existing ingest code) ...

@router.post("/{device_id}/errors")
def report_error(
    device_id: str, 
    payload: DeviceErrorPayload, 
    authenticated_device: models.Device = Depends(authenticate_device), 
    db: Session = Depends(get_db)
):
    if authenticated_device.id != device_id:
        raise HTTPException(status_code=403, detail="Forbidden: Cannot report errors for another device")
    
    device = authenticated_device

    error = models.DeviceError(
        device_id=device.id, # Use authenticated device's ID
        timestamp=datetime.datetime.utcnow(),
        firmware_version=payload.firmware_version,
        error_code=payload.error_code,
        error_message=payload.error_message,
    )
    db.add(error)
    db.commit()

    return {"status": "ok", "message": "Error reported successfully."}

@router.get("/{device_id}/shadow", response_model=DeviceShadowResponse)
def get_device_shadow(
    device_id: str, 
    authenticated_device: models.Device = Depends(authenticate_device), 
    db: Session = Depends(get_db)
):
    if authenticated_device.id != device_id:
        raise HTTPException(status_code=403, detail="Forbidden: Cannot access another device's shadow")
    
    device = authenticated_device

    return DeviceShadowResponse(
        desired_sample_interval_secs=device.desired_sample_interval_secs,
        desired_upload_interval_secs=device.desired_upload_interval_secs,
        desired_heartbeat_interval_secs=device.desired_heartbeat_interval_secs,
        reported_sample_interval_secs=device.reported_sample_interval_secs,
        reported_upload_interval_secs=device.reported_upload_interval_secs,
        reported_heartbeat_interval_secs=device.reported_heartbeat_interval_secs,
    )

@router.patch("/{device_id}/shadow")
def update_device_shadow(
    device_id: str, 
    payload: DeviceShadowPatchPayload, 
    authenticated_device: models.Device = Depends(authenticate_device), 
    db: Session = Depends(get_db)
):
    if authenticated_device.id != device_id:
        raise HTTPException(status_code=403, detail="Forbidden: Cannot update another device's shadow")
    
    device = authenticated_device

    device.reported_sample_interval_secs = payload.reported_sample_interval_secs
    device.reported_upload_interval_secs = payload.reported_upload_interval_secs
    device.reported_heartbeat_interval_secs = payload.reported_heartbeat_interval_secs
    
    db.commit()
    db.refresh(device)
    return {"status": "ok", "message": "Device reported state updated successfully."}

@router.get("/{device_id}/config_flags", response_model=DeviceConfigFlagsResponse)
def get_device_config_flags(
    device_id: str, 
    authenticated_device: models.Device = Depends(authenticate_device), 
    db: Session = Depends(get_db)
):
    if authenticated_device.id != device_id:
        raise HTTPException(status_code=403, detail="Forbidden: Cannot access another device's config flags")
    
    device = authenticated_device
    
    # Ensure config_flags is always a dict, even if stored as None or invalid JSON
    config_flags = {}
    if device.config_flags:
        try:
            config_flags = json.loads(device.config_flags)
        except json.JSONDecodeError:
            pass # Handle invalid JSON by returning empty dict

    return DeviceConfigFlagsResponse(config_flags=config_flags)

@router.patch("/{device_id}/config_flags")
def update_device_config_flags(
    device_id: str, 
    payload: DeviceConfigFlagsPayload, 
    authenticated_device: models.Device = Depends(authenticate_device), 
    db: Session = Depends(get_db)
):
    if authenticated_device.id != device_id:
        raise HTTPException(status_code=403, detail="Forbidden: Cannot update another device's config flags")
    
    device = authenticated_device
    
    device.config_flags = json.dumps(payload.config_flags)
    
    db.commit()
    db.refresh(device)
    return {"status": "ok", "message": "Device config flags updated successfully."}

@router.post("/register", response_model=RegisterResponse)
def register_device(payload: RegisterPayload, db: Session = Depends(get_db)):
    # Check if a device with this boot_id already exists (implying re-registration or existing device)
    # For simplicity, we'll use boot_id as a unique identifier for initial registration
    # In a real system, you might have a pre-provisioned list of boot_ids or a more complex JWT validation
    
    # Check if an auth_token already exists for this boot_id to prevent re-registration
    existing_device = db.query(models.Device).filter(models.Device.id == str(payload.boot_id)).first() # Using boot_id as initial device.id
    if existing_device:
        # If already registered, return existing credentials (or error, depending on policy)
        if existing_device.auth_token:
            return RegisterResponse(
                device_id=UUID(existing_device.id),
                auth_token=UUID(existing_device.auth_token),
                desired_sample_interval_secs=existing_device.desired_sample_interval_secs,
                desired_upload_interval_secs=existing_device.desired_upload_interval_secs,
                desired_heartbeat_interval_secs=existing_device.desired_heartbeat_interval_secs,
            )
        else:
            raise HTTPException(status_code=400, detail="Device ID exists but no auth token. Malformed registration.")


    # Generate a new unique device_id and auth_token
    new_device_id = uuid.uuid4()
    new_auth_token = uuid.uuid4()

    # Create new device record
    new_device = models.Device(
        id=str(new_device_id),
        auth_token=str(new_auth_token),
        lifecycle_state="new", # Device starts in 'new' state
        registered_at=datetime.datetime.utcnow(),
        # Initial desired state from defaults in models.py
    )
    db.add(new_device)
    db.commit()
    db.refresh(new_device)

    return RegisterResponse(
        device_id=new_device_id,
        auth_token=new_auth_token,
        desired_sample_interval_secs=new_device.desired_sample_interval_secs,
        desired_upload_interval_secs=new_device.desired_upload_interval_secs,
        desired_heartbeat_interval_secs=new_device.desired_heartbeat_interval_secs,
    )
