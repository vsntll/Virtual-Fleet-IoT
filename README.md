# Virtual Fleet IoT

## Introduction

This project creates a local "virtual fleet" of IoT devices that run as Docker containers and communicate with a backend server. It's designed to simulate a real-world IoT environment, allowing for the development and testing of device management, data ingestion, and over-the-air (OTA) update workflows, all on a local machine.

## Features

-   **Simulated Rust Devices:** Lightweight Rust containers that act as virtual IoT devices. Each device periodically wakes up, generates simulated sensor readings, and sends them to the backend.
-   **FastAPI Backend:** A Python-based backend using FastAPI that receives and processes data from the devices.
-   **Database Storage:** Uses SQLAlchemy and Alembic to store device information, firmware versions, and sensor measurements in a SQLite database.
-   **OTA Update Simulation:** A mechanism to simulate A/B over-the-air firmware updates for the virtual devices.
-   **Canary and Staged Rollouts:** Support for rolling out new firmware in stages, starting with a small subset of devices and gradually increasing the percentage of the fleet.
-   **Blue/Green Deployments:** Ability to maintain separate "blue" (stable) and "green" (testing) environments for devices, allowing for isolated testing of new firmware releases.
-   **Per-Segment Rollout Policies:** Flexibility to target firmware updates to specific device segments based on metadata like region or hardware revision.
-   **Web UI:** A simple web dashboard built with Jinja2 templates to monitor the status and data of the device fleet.
-   **Containerized with Docker:** The entire system is orchestrated with Docker Compose, making it easy to build, run, and scale.

## Architecture

The system consists of three main components:

1.  **Backend Service (`/backend`):** A Python FastAPI application that provides a REST API for device communication and a simple web interface for monitoring. It's responsible for data ingestion, device management, and coordinating OTA updates.
2.  **Device Service (`/device`):** A Rust application that simulates an IoT device. Multiple instances of this service can be run to create a "fleet". Each device has a unique ID and communicates with the backend via its API.
3.  **Docker Compose (`docker-compose.yml`):** Wires the services together, defining the environment, networks, and ports, and allowing for easy scaling of the device fleet.

## Directory Structure

```
.
├── backend/            # Python FastAPI backend service
│   ├── app/            # Main application source code
│   ├── alembic/        # Alembic migration scripts
│   ├── Dockerfile
│   └── alembic.ini
├── device/             # Rust device service
│   ├── src/
│   ├── Cargo.toml
│   └── Dockerfile
├── tools/              # Command-line tools for managing the fleet
├── docker-compose.yml  # Docker Compose orchestration file
└── requirements.txt    # Python dependencies
```

## Getting Started

### Prerequisites

-   [Docker](https://www.docker.com/get-started)
-   [Docker Compose](https://docs.docker.com/compose/install/)
-   [Python](https://www.python.org/downloads/) 3.11+
-   [Rust](https://www.rust-lang.org/tools/install) (for building the device)

### Installation & Setup

1.  **Clone the repository:**
    ```sh
    git clone <repository-url>
    cd virtual-fleet-iot
    ```

2.  **Set up the Python environment and install dependencies:**
    It is recommended to use a virtual environment.
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    pip install -r requirements.txt
    ```

3.  **Initialize the database:**
    The project uses Alembic to manage database migrations. The first time you set up the project, you need to apply the migrations to create the database schema. The database file (`fleet.db`) will be created inside the `backend/` directory.
    ```sh
    # From the project root directory
    .\venv\Scripts\alembic -c backend/alembic.ini upgrade head
    ```

4.  **Build and run the services:**
    Use Docker Compose to build and run the backend and device services. This command will build fresh images and start the containers.
    ```sh
    docker-compose up --build -d
    ```
    The `-d` flag runs the containers in detached mode.

### Post-Setup Steps (Important!)

Newly registered devices initially have a `lifecycle_state` of "new" and will not communicate fully with the backend until activated.

1.  **Identify new devices:**
    After `docker-compose up`, devices will register. You can find their IDs and current state by running:
    ```sh
    docker exec -it virtual-fleet-iot-backend-1 python -c "from app.database import SessionLocal; from app import models; db = SessionLocal(); devices = db.query(models.Device).all(); [print(f'ID: {d.id}, State: {d.lifecycle_state}') for d in devices]; db.close()"
    ```
2.  **Activate devices:**
    For each device with `State: new`, manually activate it using its ID (replace `<device-id>`):
    ```sh
    docker exec -it virtual-fleet-iot-backend-1 python -c "from app.database import SessionLocal; from app import models; db = SessionLocal(); device = db.query(models.Device).filter(models.Device.id == '<device-id>').first(); device.lifecycle_state = 'active'; db.commit(); db.close(); print('Device activated!')"
    ```
    After activating a device, it might take a few seconds for it to restart and begin sending authenticated requests.

## Usage

### Web UI

Once the services are running and devices are activated, you can access the web dashboard to monitor the fleet:

-   **Dashboard:** `http://localhost:8000/`
    *   View device status and basic information.
-   **Firmware Rollouts:** `http://localhost:8000/firmware_rollouts`
    *   Manage and monitor firmware deployments. You can advance rollout phases and target percentages for new firmware versions.
-   **Fleet Map:** `http://localhost:8000/map`
    *   Visualize device locations based on their reported GPS coordinates. Markers show device status and other info.
-   **Active Alerts:** `http://localhost:8000/alerts`
    *   View any active alerts triggered by metric thresholds (e.g., battery degradation, firmware failure rates). If no alerts are present, it will display a "Everything is A-OK!" message.
-   **Application Logs:** `http://localhost:8000/logs`
    *   Access a stream of structured application logs from the backend.

**Troubleshooting the Map:** If the map doesn't display correctly, check your browser's developer console for JavaScript errors. Ensure you have network access to `https://unpkg.com/leaflet/dist/leaflet.css` and `https://unpkg.com/leaflet/dist/leaflet.js` as these are loaded from a CDN.

### API Documentation

The backend API is documented using OpenAPI (Swagger). You can explore and interact with the API endpoints here:

-   **URL:** `http://localhost:8000/docs`

### Command-Line Tools

The `tools/` directory contains scripts for managing the system.

-   **Publish Firmware:**
    Use `tools/publish_firmware.py` to add new firmware versions to the system. You must provide a dummy binary file (e.g., `backend/dummy_firmware.bin`) and specify the initial rollout parameters.
    ```sh
    python tools/publish_firmware.py --version 0.1.1 --file backend/dummy_firmware.bin --phase canary --percent 1 --status active
    ```
    *(Note: Ensure `backend/dummy_firmware.bin` exists or create one with `echo "dummy content" > backend/dummy_firmware.bin`)*

-   **Control Rollouts:**
    The `tools/rollout_control.py` script provides a command-line interface to manage firmware rollouts and device environments.

    *   **Check Rollout Status:**
        ```sh
        python tools/rollout_control.py status
        ```
    *   **Set Rollout Percentage:**
        ```sh
        python tools/rollout_control.py set-phase <version> <percent>
        ```
    *   **Set Device Environment:**
        ```sh
        python tools/rollout_control.py set-environment <device-id> <environment>
        ```

-   **Compute Metrics & Alerts:**
    The `tools/compute_metrics.py` script calculates various fleet metrics and evaluates them against defined thresholds to generate alerts. Run this periodically to update the alerts in the UI.
    ```sh
    python tools/compute_metrics.py
    ```

## Running Tests

The backend has a suite of unit tests. To run them, execute the following command from the project root:

```sh
.\venv\Scripts\pytest
```