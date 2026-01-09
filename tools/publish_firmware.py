import argparse
import hashlib
import os
import sqlite3
import datetime

def get_db_connection():
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

def generate_signature(firmware_data: bytes, private_key: str) -> str:
    """Generates a dummy signature for the firmware data."""
    signer = hashlib.sha256()
    signer.update(firmware_data)
    signer.update(private_key.encode('utf-8')) # Incorporate private key
    return signer.hexdigest()

def main():
    parser = argparse.ArgumentParser(description="Publish new firmware to the backend.")
    parser.add_argument("--version", required=True, help="Firmware version string (e.g., 1.2.3)")
    parser.add_argument("--file", required=True, help="Path to the firmware binary file.")
    parser.add_argument("--phase", default="100%", help="Rollout phase (e.g., canary, 10%%, 100%%)")
    parser.add_argument("--percent", type=int, default=100, help="Target percentage for the rollout (0-100)")
    parser.add_argument("--group", default="default", help="Rollout group (e.g., default, green)")
    parser.add_argument("--required-region", help="Required device region for this firmware.")
    parser.add_argument("--required-hardware-rev", help="Required device hardware revision for this firmware.")
    parser.add_argument("--private-key", default="super-secret-key", help="Private key for signing firmware.")
    parser.add_argument("--status", default="active", help="Rollout status (e.g., active, paused, rolled_back).")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: File not found at {args.file}")
        return

    # Calculate checksum of the firmware file
    checksum = calculate_checksum(args.file)

    # Read the firmware file content for signing
    with open(args.file, "rb") as f:
        firmware_file_content = f.read()
    
    # Generate signature
    signature = generate_signature(firmware_file_content, args.private_key)

    # In a real system, the URL would point to a cloud storage location.
    # Here, we'll use a placeholder URL that points back to the backend.
    firmware_url = f"/api/firmware/binary/{args.version}" 
    
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Check if firmware version already exists
        cursor.execute("SELECT COUNT(*) FROM firmware WHERE version = ?", (args.version,))
        exists = cursor.fetchone()[0]
        if exists > 0:
            print(f"Error: Firmware version {args.version} already exists. Skipping insertion.")
            return

        cursor.execute(
            """
            INSERT INTO firmware (version, checksum, url, rollout_group, rollout_phase, target_percent, required_region, required_hardware_rev, signature, rollout_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (args.version, checksum, firmware_url, args.group, args.phase, args.percent, args.required_region, args.required_hardware_rev, signature, args.status, datetime.datetime.utcnow())
        )
        conn.commit()
        print(f"Successfully published firmware version {args.version} with group '{args.group}', phase '{args.phase}', target {args.percent}%, status '{args.status}'.")
        print(f"Signature: {signature}")
        if args.required_region:
            print(f"  Required region: {args.required_region}")
        if args.required_hardware_rev:
            print(f"  Required hardware revision: {args.required_hardware_rev}")

    except Exception as e: # Catch all exceptions for debugging
        print(f"An unexpected error occurred: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()