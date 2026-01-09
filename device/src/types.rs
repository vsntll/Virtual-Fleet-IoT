use serde::{Serialize, Deserialize};
use chrono::{DateTime, Utc};

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct Measurement {
    pub timestamp: DateTime<Utc>,
    pub temp: f32,
    pub humidity: f32,
    pub battery: f32,
    pub sequence_number: u32,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct Heartbeat {
    pub device_id: String,
    pub firmware_version: String,
    pub reported_sample_interval_secs: u64,
    pub reported_upload_interval_secs: u64,
    pub reported_heartbeat_interval_secs: u64,
    pub region: Option<String>,
    pub hardware_rev: Option<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct DesiredState {
    pub desired_version: Option<String>,
    pub desired_sample_interval_secs: u64,
    pub desired_upload_interval_secs: u64,
    pub desired_heartbeat_interval_secs: u64,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct FirmwareMetadata {
    pub version: String,
    pub checksum: String,
    pub url: String,
}

// For sending to the backend ingest API
#[derive(Serialize, Deserialize, Debug)]
pub struct IngestPayload {
    pub device_id: String,
    pub measurements: Vec<Measurement>,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct FleetSettings {
    pub num_devices: u64,
    pub sample_interval_secs: u64,
    pub upload_interval_secs: u64,
    pub heartbeat_interval_secs: u64,
}
