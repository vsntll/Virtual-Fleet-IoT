# Virtual Fleet IoT

## Introduction

This project creates a local "virtual fleet" of IoT devices that run as Docker containers and communicate with a backend server. It's designed to simulate a real-world IoT environment, allowing for the development and testing of device management, data ingestion, and over-the-air (OTA) update workflows, all on a local machine.

## Features

-   **Simulated Rust Devices:** Lightweight Rust containers that act as virtual IoT devices. Each device periodically wakes up, generates simulated sensor readings, and sends them to the backend.
-   **FastAPI Backend:** A Python-based backend using FastAPI that receives and processes data from the devices.
-   **Database Storage:** Uses SQLAlchemy and Alembic to store device information, firmware versions, and sensor measurements in a SQLite database.
-   **OTA Update Simulation:** A mechanism to simulate A/B over-the-air firmware updates for the virtual devices.
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
    Use Docker Compose to build and run the backend and device services.
    ```sh
    docker-compose up --build -d
    ```
    The `-d` flag runs the containers in detached mode.

## Usage

### Web UI

Once the services are running, you can access the web dashboard to monitor the fleet:

-   **URL:** `http://localhost:8000/`

### API Documentation

The backend API is documented using OpenAPI (Swagger). You can explore and interact with the API endpoints here:

-   **URL:** `http://localhost:8000/docs`

### Command-Line Tools

The `tools/` directory contains scripts for managing the system.

-   **Generate Fake Firmware:**
    You can use `generate_fake_firmware.py` to create dummy firmware files for testing the OTA update functionality.
    ```sh
    python tools/generate_fake_firmware.py 1.1.0 --publish
    ```

## Running Tests

The backend has a suite of unit tests. To run them, execute the following command from the project root:

```sh
.\venv\Scripts\pytest
```
