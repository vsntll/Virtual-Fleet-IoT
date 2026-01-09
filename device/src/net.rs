use anyhow::Result;
use reqwest::Client;

use crate::config::Config;
use crate::types::{FirmwareMetadata, Heartbeat, IngestPayload, DesiredState, RegisterPayload, RegisterResponse}; // Added RegisterPayload, RegisterResponse
use uuid::Uuid; // Added Uuid

pub async fn register_device(client: &Client, backend_url: &str, boot_id: Uuid) -> Result<RegisterResponse> {
    let url = format!("{}/api/devices/register", backend_url);
    let body = RegisterPayload { boot_id };
    
    let response = client.post(&url).json(&body).send().await?.error_for_status()?;
    let register_response = response.json::<RegisterResponse>().await?;
    log::info!("Device registered successfully. Device ID: {}", register_response.device_id);
    Ok(register_response)
}

pub async fn send_heartbeat(
    client: &Client, 
    config: &Config, 
    firmware_version: &str,
    sample_interval: u64,
    upload_interval: u64,
    heartbeat_interval: u64,
) -> Result<DesiredState> {
    let url = format!("{}/api/devices/heartbeat", config.backend_url);
    let body = Heartbeat {
        device_id: config.device_id.clone(),
        firmware_version: firmware_version.to_string(),
        reported_sample_interval_secs: sample_interval,
        reported_upload_interval_secs: upload_interval,
        reported_heartbeat_interval_secs: heartbeat_interval,
        region: config.region.clone(),
        hardware_rev: config.hardware_rev.clone(),
    };

    let auth_token = config.auth_token.as_ref().ok_or_else(|| anyhow::anyhow!("Auth token not found"))?;

    let desired_state = client.post(&url)
        .header("Authorization", auth_token)
        .json(&body)
        .send().await?.error_for_status()?.json::<DesiredState>().await?;
    log::info!("Heartbeat sent successfully, desired state received.");
    Ok(desired_state)
}

pub async fn send_ingest(client: &Client, config: &Config, measurements: &[crate::types::Measurement]) -> Result<()> {
    if measurements.is_empty() {
        return Ok(());
    }

    let url = format!("{}/api/devices/ingest", config.backend_url);
    let body = IngestPayload {
        device_id: config.device_id.clone(),
        measurements: measurements.to_vec(),
    };

    let auth_token = config.auth_token.as_ref().ok_or_else(|| anyhow::anyhow!("Auth token not found"))?;

    client.post(&url)
        .header("Authorization", auth_token)
        .json(&body)
        .send().await?.error_for_status()?;
    log::info!("Ingested {} measurements.", measurements.len());
    Ok(())
}

pub async fn fetch_latest_firmware(client: &Client, config: &Config) -> Result<Option<FirmwareMetadata>> {
    let url = format!("{}/api/firmware/latest?device_id={}", config.backend_url, config.device_id);
    
    let auth_token = config.auth_token.as_ref().ok_or_else(|| anyhow::anyhow!("Auth token not found"))?;

    let response = client.get(&url)
        .header("Authorization", auth_token)
        .send().await?;
    
    if response.status() == reqwest::StatusCode::NO_CONTENT {
        return Ok(None);
    }
    
    // Handle cases where the response body might be empty for other status codes too
    let text = response.text().await?;
    if text.is_empty() {
        return Ok(None);
    }

    let firmware: FirmwareMetadata = serde_json::from_str(&text)?;
    Ok(Some(firmware))
}

pub async fn download_firmware(client: &Client, config: &Config, firmware_url: &str) -> Result<Vec<u8>> {
    log::info!("Downloading firmware from {}", firmware_url);
    let auth_token = config.auth_token.as_ref().ok_or_else(|| anyhow::anyhow!("Auth token not found"))?;
    let response = client.get(firmware_url)
        .header("Authorization", auth_token)
        .send().await?;
    let bytes = response.error_for_status()?.bytes().await?.to_vec();
    log::info!("Firmware downloaded successfully ({} bytes).", bytes.len());
    Ok(bytes)
}
