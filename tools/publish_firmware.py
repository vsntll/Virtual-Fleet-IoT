import argparse
import hashlib
import os
import sqlite3

def get_db_connection():
    # This is a simplification. In a real app, you'd use a more robust way
    # to locate the database, possibly via a config file.
    db_path = os.path.join(os.path.dirname(__file__), '..', 'backend', 'fleet.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def calculate_checksum(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def main():
    parser = argparse.ArgumentParser(description="Publish new firmware to the backend.")
    parser.add_argument("--version", required=True, help="Firmware version string (e.g., 1.2.3)")
    parser.add_argument("--file", required=True, help="Path to the firmware binary file.")
    parser.add_argument("--phase", default="100%", help="Rollout phase (e.g., canary, 10%%, 100%%)")
    parser.add_argument("--percent", type=int, default=100, help="Target percentage for the rollout (0-100)")
    parser.add_argument("--group", default="default", help="Rollout group (e.g., default, green)")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: File not found at {args.file}")
        return

    checksum = calculate_checksum(args.file)
    # In a real system, the URL would point to a cloud storage location.
    # Here, we'll use a placeholder URL that points back to the backend.
    firmware_url = f"/api/firmware/binary/{args.version}" 
    
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO firmware (version, checksum, url, rollout_group, rollout_phase, target_percent, created_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (args.version, checksum, firmware_url, args.group, args.phase, args.percent)
        )
        conn.commit()
        print(f"Successfully published firmware version {args.version} with group '{args.group}', phase '{args.phase}' and target {args.percent}%.")
    except sqlite3.IntegrityError:
        print(f"Error: Firmware version {args.version} already exists.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
