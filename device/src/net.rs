use anyhow::Result;
use reqwest::Client;
use tracing::{info, debug, error};

use crate::config::Config;
use crate::types::{FirmwareMetadata, Heartbeat, IngestPayload, DesiredState, RegisterPayload, RegisterResponse, DeviceShadow, ReportedShadowState}; 
use uuid::Uuid; 

pub async fn register_device(client: &Client, backend_url: &str, boot_id: Uuid) -> Result<RegisterResponse> {
    let url = format!("{}/api/devices/register", backend_url);
    let body = RegisterPayload { boot_id };
    
    info!(boot_id = %boot_id, "Attempting to register device");
    let response = client.post(&url).json(&body).send().await?.error_for_status()?;
    let register_response = response.json::<RegisterResponse>().await?;
    info!(device_id = %register_response.device_id, "Device registered successfully");
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
    debug!(device_id = %config.device_id, auth_token = %auth_token, "Sending heartbeat with auth token"); // Debug log

    debug!(device_id = %config.device_id, "Sending heartbeat");
    let desired_state = client.post(&url)
        .header("X-Auth-Token", auth_token) // Changed header name
        .json(&body)
        .send().await?.error_for_status()?.json::<DesiredState>().await?;
    info!(device_id = %config.device_id, "Heartbeat sent successfully, desired state received.");
    Ok(desired_state)
}

pub async fn send_ingest(client: &Client, config: &Config, measurements: &[crate::types::Measurement]) -> Result<()> {
    if measurements.is_empty() {
        debug!(device_id = %config.device_id, "No measurements to ingest");
        return Ok(());
    }

    let url = format!("{}/api/devices/ingest", config.backend_url);
    let body = IngestPayload {
        device_id: config.device_id.clone(),
        measurements: measurements.to_vec(),
    };

    let auth_token = config.auth_token.as_ref().ok_or_else(|| anyhow::anyhow!("Auth token not found"))?;
    debug!(device_id = %config.device_id, auth_token = %auth_token, "Sending ingest with auth token"); // Debug log

    client.post(&url)
        .header("X-Auth-Token", auth_token) // Changed header name
        .json(&body)
        .send().await?.error_for_status()?;
    info!(device_id = %config.device_id, count = measurements.len(), "Ingested measurements.");
    Ok(())
}

pub async fn fetch_latest_firmware(client: &Client, config: &Config) -> Result<Option<FirmwareMetadata>> {
    let url = format!("{}/api/firmware/latest?device_id={}", config.backend_url, config.device_id);
    
    let auth_token = config.auth_token.as_ref().ok_or_else(|| anyhow::anyhow!("Auth token not found"))?;
    debug!(device_id = %config.device_id, auth_token = %auth_token, "Fetching latest firmware with auth token"); // Debug log

    debug!(device_id = %config.device_id, "Fetching latest firmware");
    let response = client.get(&url)
        .header("X-Auth-Token", auth_token) // Changed header name
        .send().await?;
    
    if response.status() == reqwest::StatusCode::NO_CONTENT {
        info!(device_id = %config.device_id, "No new firmware available.");
        return Ok(None);
    }
    
    let text = response.text().await?;
    if text.is_empty() {
        error!(device_id = %config.device_id, "Firmware response body was empty but status was not 204.");
        return Ok(None);
    }

    let firmware: FirmwareMetadata = serde_json::from_str(&text)?;
    info!(device_id = %config.device_id, version = %firmware.version, "Fetched new firmware metadata");
    Ok(Some(firmware))
}

pub async fn download_firmware(client: &Client, config: &Config, firmware_url: &str) -> Result<Vec<u8>> {
    info!(device_id = %config.device_id, url = %firmware_url, "Downloading firmware");
    let auth_token = config.auth_token.as_ref().ok_or_else(|| anyhow::anyhow!("Auth token not found"))?;
    debug!(device_id = %config.device_id, auth_token = %auth_token, "Downloading firmware with auth token"); // Debug log

    let response = client.get(firmware_url)
        .header("X-Auth-Token", auth_token) // Changed header name
        .send().await?;
    let bytes = response.error_for_status()?.bytes().await?.to_vec();
    info!(device_id = %config.device_id, bytes = bytes.len(), "Firmware downloaded successfully");
    Ok(bytes)
}

pub async fn fetch_device_shadow(client: &Client, config: &Config) -> Result<DeviceShadow> {
    let url = format!("{}/api/devices/{}/shadow", config.backend_url, config.device_id);
    let auth_token = config.auth_token.as_ref().ok_or_else(|| anyhow::anyhow!("Auth token not found"))?;
    debug!(device_id = %config.device_id, auth_token = %auth_token, "Fetching device shadow with auth token"); // Debug log

    debug!(device_id = %config.device_id, "Fetching device shadow");
    let shadow = client.get(&url)
        .header("X-Auth-Token", auth_token) // Changed header name
        .send().await?.error_for_status()?.json::<DeviceShadow>().await?;
    debug!(device_id = %config.device_id, ?shadow, "Fetched device shadow");
    Ok(shadow)
}

pub async fn report_device_shadow(client: &Client, config: &Config, reported_state: ReportedShadowState) -> Result<()> {
    let url = format!("{}/api/devices/{}/shadow", config.backend_url, config.device_id);
    let auth_token = config.auth_token.as_ref().ok_or_else(|| anyhow::anyhow!("Auth token not found"))?;
    debug!(device_id = %config.device_id, auth_token = %auth_token, "Reporting device shadow state with auth token"); // Debug log

    debug!(device_id = %config.device_id, ?reported_state, "Reporting device shadow state");
    client.patch(&url)
        .header("X-Auth-Token", auth_token) // Changed header name
        .json(&reported_state)
        .send().await?.error_for_status()?;
    info!(device_id = %config.device_id, "Reported device shadow state.");
    Ok(())
}