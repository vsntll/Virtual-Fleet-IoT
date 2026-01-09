import sqlite3
import datetime

def check_measurements(device_id):
    db_path = 'backend/fleet.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query total measurements
    cursor.execute("SELECT COUNT(*) FROM measurements WHERE device_id = ?", (device_id,))
    total_measurements = cursor.fetchone()[0]
    print(f"Total measurements for device {device_id}: {total_measurements}")

    # Query measurements within the last 48 hours
    time_window_48h = datetime.datetime.utcnow() - datetime.timedelta(hours=48)
    
    # Need to convert timezone aware datetime object to UTC for comparison
    # sqlite stores dates as strings, so we need to compare strings
    time_window_48h_str = time_window_48h.isoformat(timespec='seconds') + 'Z'

    cursor.execute(
        "SELECT battery FROM measurements WHERE device_id = ? AND timestamp >= ? ORDER BY timestamp ASC",
        (device_id, time_window_48h_str)
    )
    recent_measurements = cursor.fetchall()

    if len(recent_measurements) >= 2:
        initial_battery = recent_measurements[0][0]
        final_battery = recent_measurements[-1][0]
        print(f"Initial battery (last 48h): {initial_battery}, Final battery (last 48h): {final_battery}")
    else:
        print("Not enough recent measurements (last 48h) to compare battery levels.")

    conn.close()

if __name__ == "__main__":
    device_id = 'fa05bacd-98a5-4fc5-a384-00267e4e48c9' # Replace with your active device ID
    check_measurements(device_id)