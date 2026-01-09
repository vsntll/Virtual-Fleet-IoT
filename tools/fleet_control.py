import argparse
import subprocess
import os
import sys
import time

# Add the backend directory to the Python path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app.database import SessionLocal
from app import models

def get_num_desired_devices():
    db = SessionLocal()
    try:
        settings = db.query(models.FleetSetting).first()
        if settings:
            return settings.num_devices
        return 0
    finally:
        db.close()

def get_current_running_devices():
    try:
        # Use docker-compose ps -q to get only container IDs
        result = subprocess.run(
            ["docker-compose", "ps", "-q", "device"],
            capture_output=True,
            text=True,
            check=True,
            cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), '..')) # Run from project root
        )
        running_ids = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return len(running_ids)
    except subprocess.CalledProcessError as e:
        print(f"Error getting current running devices: {e}", file=sys.stderr)
        print(e.stderr, file=sys.stderr)
        return 0
    except FileNotFoundError:
        print("docker-compose command not found. Please ensure Docker Compose is installed and in your PATH.", file=sys.stderr)
        return 0

def scale_devices(num_devices):
    print(f"Scaling device service to {num_devices} instances...")
    try:
        command = ["docker-compose", "up", "--scale", f"device={num_devices}", "-d"]
        print(f"Executing: {' '.join(command)}")
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), '..')) # Run from project root
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        print(f"Successfully scaled to {num_devices} devices.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error scaling devices to {num_devices}: {e}", file=sys.stderr)
        print(e.stderr, file=sys.stderr)
        return False
    except FileNotFoundError:
        print("docker-compose command not found. Please ensure Docker Compose is installed and in your PATH.", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Control the virtual device fleet.")
    parser.add_argument("action", choices=["scale", "status"], help="Action to perform.")
    
    args = parser.parse_args()

    if args.action == "scale":
        desired_num_devices = get_num_desired_devices()
        if desired_num_devices is not None:
            current_running_devices = get_current_running_devices()
            print(f"Desired devices from DB: {desired_num_devices}, Currently running: {current_running_devices}")
            if desired_num_devices != current_running_devices:
                scale_devices(desired_num_devices)
            else:
                print(f"Fleet already at desired scale of {desired_num_devices} devices.")
        else:
            print("Could not retrieve desired number of devices from DB.", file=sys.stderr)
    elif args.action == "status":
        desired_num_devices = get_num_desired_devices()
        current_running_devices = get_current_running_devices()
        print(f"Fleet Status:")
        print(f"  Desired number of devices (from DB): {desired_num_devices}")
        print(f"  Currently running device containers: {current_running_devices}")

if __name__ == "__main__":
    main()
