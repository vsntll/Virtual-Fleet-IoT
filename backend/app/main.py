import logging
from pythonjsonlogger import jsonlogger

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import models
from .database import engine
from .api import devices, firmware, fleet
from .ui import views


# Configure structured JSON logging
logger = logging.getLogger()
if not logger.handlers: # Avoid adding handlers multiple times if reloaded
    # Console handler
    console_handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        '%(levelname)s %(asctime)s %(name)s %(message)s'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    file_handler = logging.FileHandler('backend/app.log')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.setLevel(logging.INFO)

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
    logger.info("Health check performed", extra={"component": "system"})
    return {"status": "ok"}
