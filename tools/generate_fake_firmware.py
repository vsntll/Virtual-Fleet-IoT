import hashlib
import os
import argparse
import json
import requests

# This is a simple tool to create a fake firmware package and publish it to the backend.
# A "firmware package" is just a JSON file with a version and some dummy data.

def generate_firmware(version: str, content: str, output_dir: str = "firmware_artifacts"):
    """Generates a firmware file and its metadata."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    firmware_content = {
        "version": version,
        "dummy_content": content,
    }

    file_name = f"firmware_{version.replace('.', '_')}.json"
    file_path = os.path.join(output_dir, file_name)

    with open(file_path, "w") as f:
        json.dump(firmware_content, f)

    # Calculate checksum
    with open(file_path, "rb") as f:
        checksum = hashlib.sha256(f.read()).hexdigest()

    print(f"Generated firmware file: {file_path}")
    print(f"  - Version: {version}")
    print(f"  - Checksum: {checksum}")

    return file_path, checksum

def publish_firmware_to_backend(version: str, checksum: str, backend_url: str):
    """
    This function is a placeholder for what would be a call to a private/admin API
    on the backend to register new firmware. Since we haven't defined that API, 
    this function will just print what it would do.

    A real implementation would look something like this:
    
try:
        payload = {
            "version": version,
            "checksum": checksum,
            # The URL would point to where the device can download this file.
            # This is tricky in a local Docker setup without a proper file server.
            # For now, we assume a placeholder URL.
            "url": f"{backend_url}/api/firmware/binary/placeholder_id_for_{version}",
        }
        # Assuming a POST /api/firmware/ endpoint for admin
        response = requests.post(f"{backend_url}/api/firmware/", json=payload)
        response.raise_for_status()
        print("Successfully published firmware version to backend.")
    except requests.exceptions.RequestException as e:
        print(f"Error publishing firmware to backend: {e}")

    """
    print("\n---")
    print("NOTE: Publishing to backend is not implemented yet.")
    print("This would typically involve an admin API endpoint to register the new firmware.")
    print(f"  - Version: {version}")
    print(f"  - Checksum: {checksum}")
    print(f"  - Backend URL: {backend_url}")
    print("---\n")


def main():
    parser = argparse.ArgumentParser(description="Generate and publish fake firmware.")
    parser.add_argument("version", type=str, help="The firmware version, e.g., '1.2.3'.")
    parser.add_argument("--content", type=str, default="This is a new firmware version.", help="Dummy content for the firmware file.")
    parser.add_argument("--backend_url", type=str, default="http://localhost:8000", help="URL of the backend server.")
    parser.add_argument("--publish", action="store_true", help="Simulate publishing the firmware to the backend.")

    args = parser.parse_args()

    file_path, checksum = generate_firmware(args.version, args.content)

    if args.publish:
        publish_firmware_to_backend(args.version, checksum, args.backend_url)

if __name__ == "__main__":
    main()
