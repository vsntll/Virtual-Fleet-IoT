import sqlite3
import datetime
import uuid

def insert_degraded_battery_data(device_id):
    db_path = 'backend/fleet.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Clear existing measurements for the device
    cursor.execute("DELETE FROM measurements WHERE device_id = ?", (device_id,))

    # Insert measurements with degrading battery
    now = datetime.datetime.utcnow()
    measurements_to_insert = [
        # Initial high battery
        (device_id, (now - datetime.timedelta(hours=47)).isoformat(timespec='seconds') + 'Z', 25.0, 50.0, 0.9, 0, "0.1.0", 34.0, -118.0, 0.0),
        # Slightly degraded battery
        (device_id, (now - datetime.timedelta(hours=24)).isoformat(timespec='seconds') + 'Z', 26.0, 51.0, 0.8, 1, "0.1.0", 34.0, -118.0, 0.0),
        # Significantly degraded battery
        (device_id, now.isoformat(timespec='seconds') + 'Z', 27.0, 52.0, 0.5, 2, "0.1.0", 34.0, -118.0, 0.0),
    ]

    cursor.executemany(
        """
        INSERT INTO measurements (device_id, timestamp, temp, humidity, battery, sequence_number, firmware_version, latitude, longitude, speed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        measurements_to_insert
    )
    conn.commit()
    conn.close()
    print(f"Inserted degraded battery data for device {device_id}")

if __name__ == "__main__":
    device_id = 'fa05bacd-98a5-4fc5-a384-00267e4e48c9' # Replace with your active device ID
    insert_degraded_battery_data(device_id)