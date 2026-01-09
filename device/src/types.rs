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
pub struct Heartbeat<'a> {
    pub device_id: &'a str,
    pub firmware_version: &'a str,
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
