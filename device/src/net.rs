use anyhow::Result;
use reqwest::Client;

use crate::config::Config;
use crate::types::{FirmwareMetadata, Heartbeat, IngestPayload};

pub async fn send_heartbeat<'a>(client: &Client, config: &Config, firmware_version: &'a str) -> Result<()> {
    let url = format!("{}/api/devices/heartbeat", config.backend_url);
    let body = Heartbeat {
        device_id: &config.device_id,
        firmware_version,
    };

    client.post(&url).json(&body).send().await?.error_for_status()?;
    log::info!("Heartbeat sent successfully.");
    Ok(())
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

    client.post(&url).json(&body).send().await?.error_for_status()?;
    log::info!("Ingested {} measurements.", measurements.len());
    Ok(())
}

pub async fn fetch_latest_firmware(client: &Client, config: &Config) -> Result<Option<FirmwareMetadata>> {
    let url = format!("{}/api/firmware/latest?device_id={}", config.backend_url, config.device_id);
    
    let response = client.get(&url).send().await?;
    
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

pub async fn download_firmware(client: &Client, firmware_url: &str) -> Result<Vec<u8>> {
    log::info!("Downloading firmware from {}", firmware_url);
    let response = client.get(firmware_url).send().await?;
    let bytes = response.error_for_status()?.bytes().await?.to_vec();
    log::info!("Firmware downloaded successfully ({} bytes).", bytes.len());
    Ok(bytes)
}
