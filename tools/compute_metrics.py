import os
import sys
import datetime
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import func

# Add the backend directory to the Python path to import models
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from app import models

# Database setup (copying from backend/app/database.py, but adjusting path for tools)
# Adjust the database URL to point to the correct location for the tools
# Assuming the tools run from the project root or similar.
# If running from 'tools' directory, '../backend/fleet.db' or '../test.db'
# For now, let's assume it should target the main backend database.
DATABASE_URL = "sqlite:///./backend/fleet.db" # This needs to be correct based on where the DB file is relative to this script

# If running from project root, it might be "sqlite:///./backend/fleet.db"
# If running from 'tools' directory, it might need to adjust: "sqlite:///../backend/fleet.db"
# Let's assume for now the script will be executed from the project root.

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base() # Re-declare Base, or import if possible. If Base is always the same, we can import from models

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def compute_failure_rates():
    db_gen = get_db()
    db = next(db_gen) # Get the session object from the generator

    print("Computing failure rates...")

    try:
        # Define a time window for recent errors, e.g., last 24 hours
        time_window = datetime.datetime.utcnow() - datetime.timedelta(hours=24)

        # Get all distinct firmware versions that have devices
        active_firmware_versions = db.query(models.Device.current_version).distinct().all()
        active_firmware_versions = [version[0] for version in active_firmware_versions if version[0] is not None]

        for firmware_version in active_firmware_versions:
            # Count active devices for this firmware version
            device_count = db.query(models.Device).filter(
                models.Device.current_version == firmware_version,
                models.Device.status == "online" # Assuming "online" status for active devices
            ).count()

            # Count errors for this firmware version within the time window
            error_count = db.query(models.DeviceError).filter(
                models.DeviceError.firmware_version == firmware_version,
                models.DeviceError.timestamp >= time_window
            ).count()

            failure_rate = (error_count / device_count * 100) if device_count > 0 else 0

            print(f"Firmware: {firmware_version}, Devices: {device_count}, Errors (last 24h): {error_count}, Failure Rate: {failure_rate:.2f}%")

            # Update the metrics_summary in the Firmware model
            firmware_entry = db.query(models.Firmware).filter(models.Firmware.version == firmware_version).first()
            if firmware_entry:
                metrics_summary = {
                    "last_24h_errors": error_count,
                    "active_devices": device_count,
                    "failure_rate_24h": round(failure_rate, 2),
                    "computed_at": datetime.datetime.utcnow().isoformat()
                }
                firmware_entry.metrics_summary = json.dumps(metrics_summary)
                db.add(firmware_entry)
                db.commit()
                print(f"Updated metrics_summary for firmware {firmware_version}")
            else:
                print(f"Warning: Firmware entry for version {firmware_version} not found in DB. Cannot update metrics_summary.")

    except Exception as e:
        print(f"An error occurred: {e}")
        db.rollback() # Rollback in case of error
    finally:
        db.close()

if __name__ == "__main__":
    # Ensure all models are loaded for Alembic's Base to know them
    # from app import models # This line is already handled by the sys.path.insert and direct import

    # Determine the project root dynamically
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    db_path = os.path.join(project_root, 'backend', 'fleet.db')
    
    # Adjust DATABASE_URL dynamically
    DATABASE_URL = f"sqlite:///{db_path}"
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    print(f"Using database: {DATABASE_URL}")
    
    compute_failure_rates()