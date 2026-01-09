import argparse
import datetime
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import desc, asc

# Add the backend directory to the Python path to import models
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from app import models

DATABASE_URL = "sqlite:///./backend/fleet.db"

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

def replay_events(device_id: Optional[str], start_time: datetime.datetime, end_time: datetime.datetime):
    db_gen = get_db()
    db = next(db_gen)

    print(f"Replaying events from {start_time} to {end_time}")
    if device_id:
        print(f"  for device: {device_id}")
    print("-" * 50)

    try:
        # Fetch measurements
        measurements_query = db.query(models.Measurement).filter(
            models.Measurement.timestamp >= start_time,
            models.Measurement.timestamp <= end_time
        )
        if device_id:
            measurements_query = measurements_query.filter(models.Measurement.device_id == device_id)
        measurements = measurements_query.order_by(models.Measurement.timestamp.asc()).all()

        # Fetch alerts
        alerts_query = db.query(models.Alert).filter(
            models.Alert.timestamp >= start_time,
            models.Alert.timestamp <= end_time
        )
        if device_id:
            alerts_query = alerts_query.filter(models.Alert.device_id == device_id)
        alerts = alerts_query.order_by(models.Alert.timestamp.asc()).all()

        all_events = []
        for m in measurements:
            all_events.append({
                "type": "measurement",
                "timestamp": m.timestamp,
                "device_id": m.device_id,
                "temp": m.temp,
                "humidity": m.humidity,
                "battery": m.battery,
                "firmware_version": m.firmware_version,
            })
        for a in alerts:
            all_events.append({
                "type": "alert",
                "timestamp": a.timestamp,
                "device_id": a.device_id,
                "alert_type": a.alert_type,
                "severity": a.severity,
                "message": a.message,
                "firmware_version": a.firmware_version,
            })
        
        # Sort all events by timestamp
        all_events.sort(key=lambda x: x["timestamp"])

        for event in all_events:
            if event["type"] == "measurement":
                print(f"[{event['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}] MEASUREMENT (Device: {event['device_id']}) - Temp: {event['temp']:.2f}, Hum: {event['humidity']:.2f}, Batt: {event['battery']:.2f}, FW: {event['firmware_version']}")
            elif event["type"] == "alert":
                print(f"[{event['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}] ALERT ({event['severity'].upper()}) (Device: {event['device_id'] or 'N/A'}, FW: {event['firmware_version'] or 'N/A'}) - Type: {event['alert_type']}, Message: {event['message']}")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay historical device events.")
    parser.add_argument("--device-id", type=str, help="Optional: Filter events by device ID.")
    parser.add_argument("--start-time", type=str, required=True, help="Start time in YYYY-MM-DD HH:MM:SS format.")
    parser.add_argument("--end-time", type=str, required=True, help="End time in YYYY-MM-DD HH:MM:SS format.")
    args = parser.parse_args()

    try:
        start_time_dt = datetime.datetime.strptime(args.start_time, "%Y-%m-%d %H:%M:%S")
        end_time_dt = datetime.datetime.strptime(args.end_time, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        print("Error: Invalid time format. Please use YYYY-MM-DD HH:MM:SS.")
        sys.exit(1)
    
    # Adjust DATABASE_URL dynamically (similar to compute_metrics.py)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    db_path = os.path.join(project_root, 'backend', 'fleet.db')
    DATABASE_URL = f"sqlite:///{db_path}"
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    replay_events(args.device_id, start_time_dt, end_time_dt)