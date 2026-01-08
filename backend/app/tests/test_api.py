from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from ..main import app
from ..database import Base, get_db

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
        json={"device_id": "test-device-01", "firmware_version": "1.0.0"},
    )
    assert response.status_code == 200
    assert response.json() == {"desired_version": None}

def test_ingest_data_for_known_device():
    # First, register the device
    client.post(
        "/api/devices/heartbeat",
        json={"device_id": "test-device-02", "firmware_version": "1.0.0"},
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
                    "battery": 0.95
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
