import argparse
import requests
import json

BASE_URL = "http://localhost:8000"

def get_health_status():
    """Fetches and displays the health status of the fleet."""
    try:
        response = requests.get(f"{BASE_URL}/api/fleet/health")
        response.raise_for_status()
        health_data = response.json()
        
        print("Firmware Version | Device Count | Error Count | Failure Rate")
        print("------------------|--------------|-------------|---------------")
        for version, metrics in health_data.items():
            print(
                f"{version:<18}| {metrics['device_count']:<12} | {metrics['error_count']:<11} | {metrics['failure_rate']:.2%}"
            )
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching health status: {e}")

def set_rollout_phase(version, percent):
    """Sets the rollout percentage for a specific firmware version."""
    if not (0 <= percent <= 100):
        print("Error: Percentage must be between 0 and 100.")
        return
        
    try:
        payload = {"target_percent": percent}
        response = requests.patch(f"{BASE_URL}/api/firmware/{version}", json=payload)
        response.raise_for_status()
        
        updated_firmware = response.json()
        print(f"Successfully updated firmware {version}.")
        print(f"New target percentage: {updated_firmware['target_percent']}%")
        
    except requests.exceptions.RequestException as e:
        print(f"Error setting rollout phase: {e}")
        if e.response:
            print(f"Details: {e.response.text}")

def main():
    parser = argparse.ArgumentParser(description="Control firmware rollouts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Sub-parser for getting status
    parser_status = subparsers.add_parser("status", help="Get the health status of all firmware versions.")
    parser_status.set_defaults(func=get_health_status)

    # Sub-parser for setting phase
    parser_set_phase = subparsers.add_parser("set-phase", help="Set the rollout phase for a firmware version.")
    parser_set_phase.add_argument("version", help="The firmware version to update.")
    parser_set_phase.add_argument("percent", type=int, help="The target percentage for the rollout (0-100).")
    parser_set_phase.set_defaults(func=lambda args: set_rollout_phase(args.version, args.percent))

    args = parser.parse_args()
    if hasattr(args, 'func'):
        if args.command == 'status':
            args.func()
        else:
            args.func(args)

if __name__ == "__main__":
    main()
