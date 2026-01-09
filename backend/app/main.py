from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import models
from .database import engine
from .api import devices, firmware, fleet
from .ui import views


app = FastAPI(title="Virtual Fleet Backend")

# Mount static files
app.mount("/static", StaticFiles(directory="app/ui/static"), name="static")

# Include API routers
app.include_router(devices.router, prefix="/api/devices", tags=["devices"])
app.include_router(firmware.router, prefix="/api/firmware", tags=["firmware"])
app.include_router(fleet.router, prefix="/api/fleet", tags=["fleet"])

# Include UI router
app.include_router(views.router, tags=["ui"])

@app.get("/health", tags=["system"])
def health_check():
    """Health check endpoint"""
    return {"status": "ok"}
