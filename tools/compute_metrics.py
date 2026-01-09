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

# Determine the project root dynamically
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
db_path = os.path.join(project_root, 'backend', 'fleet.db')

# Global DATABASE_URL and session setup
DATABASE_URL = f"sqlite:///{db_path}"
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def compute_metrics_and_alerts():
    db_gen = get_db()
    db = next(db_gen) # Get the session object from the generator

    print(f"Using database: {DATABASE_URL}")
    print("Computing metrics and evaluating alerts...")

    try:
        # --- Firmware Failure Rates and Alerts ---
        time_window_24h = datetime.datetime.utcnow() - datetime.timedelta(hours=24)

        active_firmware_versions = db.query(models.Device.current_version).distinct().all()
        active_firmware_versions = [version[0] for version in active_firmware_versions if version[0] is not None]

        for firmware_version in active_firmware_versions:
            device_count = db.query(models.Device).filter(
                models.Device.current_version == firmware_version,
                models.Device.status == "online"
            ).count()

            error_count = db.query(models.DeviceError).filter(
                models.DeviceError.firmware_version == firmware_version,
                models.DeviceError.timestamp >= time_window_24h
            ).count()

            failure_rate = (error_count / device_count * 100) if device_count > 0 else 0

            print(f"Firmware: {firmware_version}, Devices: {device_count}, Errors (last 24h): {error_count}, Failure Rate: {failure_rate:.2f}%")

            # Store metrics in the Metric table
            db.add(models.Metric(
                timestamp=datetime.datetime.utcnow(),
                metric_name="active_devices",
                metric_value=float(device_count),
                firmware_version=firmware_version
            ))
            db.add(models.Metric(
                timestamp=datetime.datetime.utcnow(),
                metric_name="last_24h_errors",
                metric_value=float(error_count),
                firmware_version=firmware_version
            ))
            db.add(models.Metric(
                timestamp=datetime.datetime.utcnow(),
                metric_name="failure_rate_24h",
                metric_value=round(failure_rate, 2),
                firmware_version=firmware_version
            ))

            # Evaluate rules and raise alerts
            FAILURE_RATE_THRESHOLD = 5.0
            if failure_rate > FAILURE_RATE_THRESHOLD:
                db.add(models.Alert(
                    timestamp=datetime.datetime.utcnow(),
                    alert_type="FirmwareFailureRateExceeded",
                    severity="critical",
                    message=f"Firmware {firmware_version} failure rate ({failure_rate:.2f}%) exceeded threshold ({FAILURE_RATE_THRESHOLD}%)",
                    firmware_version=firmware_version,
                    is_active=True
                ))
                print(f"!!! ALERT: Firmware {firmware_version} failure rate exceeded threshold.")
            
            # Update the metrics_summary in the Firmware model (for UI compatibility)
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
        
        # --- Predictive Maintenance: Battery Degradation ---
        BATTERY_DEGRADATION_THRESHOLD = 10.0 # Percentage drop over 48 hours to trigger alert
        MEASUREMENT_WINDOW_HOURS = 48
        time_window_measurements = datetime.datetime.utcnow() - datetime.timedelta(hours=MEASUREMENT_WINDOW_HOURS)

        all_devices = db.query(models.Device).all()
        for device in all_devices:
            recent_measurements = db.query(models.Measurement).filter(
                models.Measurement.device_id == device.id,
                models.Measurement.timestamp >= time_window_measurements
            ).order_by(models.Measurement.timestamp.asc()).all()

            if len(recent_measurements) >= 2:
                # Get the first and last battery readings in the window
                initial_battery = recent_measurements[0].battery
                final_battery = recent_measurements[-1].battery
                
                # Simple degradation calculation: percentage drop
                if initial_battery > 0:
                    battery_drop_percent = ((initial_battery - final_battery) / initial_battery) * 100
                    if battery_drop_percent > BATTERY_DEGRADATION_THRESHOLD:
                        device.predicted_issue = f"Battery degrading rapidly ({battery_drop_percent:.2f}% drop in {MEASUREMENT_WINDOW_HOURS}h)."
                        db.add(models.Alert(
                            timestamp=datetime.datetime.utcnow(),
                            alert_type="BatteryDegradation",
                            severity="warning",
                            message=f"Device {device.id}: {device.predicted_issue}",
                            device_id=device.id,
                            is_active=True
                        ))
                        print(f"!!! PREDICTIVE ALERT: Device {device.id} - {device.predicted_issue}")
                    else:
                        device.predicted_issue = None # Clear if no issue
                else:
                    device.predicted_issue = None # Cannot calculate if initial battery is zero or less
            else:
                device.predicted_issue = None # Not enough data

            db.add(device) # Mark device for update

        db.commit() # Final commit for all metrics, alerts, and device updates
    except Exception as e:
        print(f"An error occurred: {e}")
        db.rollback() # Rollback in case of error
    finally:
        db.close()

if __name__ == "__main__":
    compute_metrics_and_alerts()