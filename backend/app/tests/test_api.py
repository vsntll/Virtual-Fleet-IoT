from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from ..main import app
from ..database import Base, get_db
from .. import models

# Use an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create the tables in the test database
Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(scope="function", autouse=True)
def setup_teardown_db():
    # Create tables before each test
    Base.metadata.create_all(bind=engine)
    yield
    # Drop tables after each test
    Base.metadata.drop_all(bind=engine)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_register_device_on_heartbeat():
    response = client.post(
        "/api/devices/heartbeat",
        json={
            "device_id": "test-device-01",
            "firmware_version": "1.0.0",
            "reported_sample_interval_secs": 10,
            "reported_upload_interval_secs": 60,
            "reported_heartbeat_interval_secs": 30
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "desired_version": None,
        "desired_sample_interval_secs": 10,
        "desired_upload_interval_secs": 60,
        "desired_heartbeat_interval_secs": 30,
    }

def test_ingest_data_for_known_device():
    # First, register the device
    client.post(
        "/api/devices/heartbeat",
        json={
            "device_id": "test-device-02",
            "firmware_version": "1.0.0",
            "reported_sample_interval_secs": 10,
            "reported_upload_interval_secs": 60,
            "reported_heartbeat_interval_secs": 30
        },
    )
    
    # Then, ingest data
    response = client.post(
        "/api/devices/ingest",
        json={
            "device_id": "test-device-02",
            "measurements": [
                {
                    "timestamp": "2026-01-08T12:00:00Z",
                    "temp": 25.5,
                    "humidity": 60.1,
                    "battery": 0.95,
                    "sequence_number": 1
                }
            ]
        }
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Ingested 1 measurements."

def test_ingest_data_for_unknown_device():
    response = client.post(
        "/api/devices/ingest",
        json={
            "device_id": "unknown-device",
            "measurements": []
        }
    )
    assert response.status_code == 404

def test_report_device_error():
    # Register a device first
    client.post(
        "/api/devices/heartbeat",
        json={
            "device_id": "test-device-error",
            "firmware_version": "1.1.0",
            "reported_sample_interval_secs": 10,
            "reported_upload_interval_secs": 60,
            "reported_heartbeat_interval_secs": 30
        },
    )

    # Report an error
    response = client.post(
        "/api/devices/test-device-error/errors",
        json={
            "firmware_version": "1.1.0",
            "error_code": "E-101",
            "error_message": "Sensor read failure",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Error reported successfully."}

def test_get_fleet_health():
    # Register device 1 and report an error
    client.post(
        "/api/devices/heartbeat",
        json={
            "device_id": "health-test-01",
            "firmware_version": "2.0.0",
            "reported_sample_interval_secs": 10,
            "reported_upload_interval_secs": 60,
            "reported_heartbeat_interval_secs": 30
        },
    )
    client.post(
        "/api/devices/health-test-01/errors",
        json={
            "firmware_version": "2.0.0",
            "error_code": "E-202",
            "error_message": "Network timeout",
        },
    )

    # Register device 2 with a different version
    client.post(
        "/api/devices/heartbeat",
        json={
            "device_id": "health-test-02",
            "firmware_version": "2.1.0",
            "reported_sample_interval_secs": 10,
            "reported_upload_interval_secs": 60,
            "reported_heartbeat_interval_secs": 30
        },
    )

    # Get fleet health
    response = client.get("/api/fleet/health")
    assert response.status_code == 200
    health_data = response.json()

    assert "2.0.0" in health_data
    assert health_data["2.0.0"]["device_count"] == 1
    assert health_data["2.0.0"]["error_count"] == 1
    assert health_data["2.0.0"]["failure_rate"] == 1.0

    assert "2.1.0" in health_data
    assert health_data["2.1.0"]["device_count"] == 1
    assert health_data["2.1.0"]["error_count"] == 0
    assert health_data["2.1.0"]["failure_rate"] == 0.0

def test_blue_green_rollout():
    # Register a blue device
    client.post(
        "/api/devices/heartbeat",
        json={
            "device_id": "blue-device",
            "firmware_version": "1.0.0",
            "reported_sample_interval_secs": 10,
            "reported_upload_interval_secs": 60,
            "reported_heartbeat_interval_secs": 30
        },
    )
    client.post("/api/devices/blue-device/environment", json={"environment": "blue"})

    # Register a green device
    client.post(
        "/api/devices/heartbeat",
        json={
            "device_id": "green-device",
            "firmware_version": "1.0.0",
            "reported_sample_interval_secs": 10,
            "reported_upload_interval_secs": 60,
            "reported_heartbeat_interval_secs": 30
        },
    )
    client.post("/api/devices/green-device/environment", json={"environment": "green"})

    # Publish a new firmware for the green group
    # This requires a direct DB write in the test, as we don't have a file for the tool to use.
    db = next(override_get_db())
    green_firmware = models.Firmware(
        version="2.0.0-green",
        checksum="abcdef",
        url="/fake/url",
        rollout_group="green",
        target_percent=100,
    )
    db.add(green_firmware)
    db.commit()

    # Blue device should not get the update
    response_blue = client.get("/api/firmware/latest?device_id=blue-device")
    assert response_blue.status_code == 204

    # Green device should get the update
    response_green = client.get("/api/firmware/latest?device_id=green-device")
    assert response_green.status_code == 200
    assert response_green.json()["version"] == "2.0.0-green"
