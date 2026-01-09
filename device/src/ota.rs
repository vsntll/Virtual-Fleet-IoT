use anyhow::Result;
use reqwest::Client;
use std::fs;
use std::path::Path;
use serde::{Deserialize, Serialize};

use crate::config::Config;
use crate::net;

const OTA_STATE_PATH: &str = "./ota_state.json";
const FIRMWARE_DIR: &str = "./firmware";

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct OtaState {
    pub current_version: String,
    pub active_slot: String,
}

impl OtaState {
    pub fn load() -> Result<Self> {
        if Path::new(OTA_STATE_PATH).exists() {
            let file_content = fs::read_to_string(OTA_STATE_PATH)?;
            let state: OtaState = serde_json::from_str(&file_content)?;
            Ok(state)
        } else {
            // Default state if none exists
            Ok(OtaState {
                current_version: env!("CARGO_PKG_VERSION").to_string(),
                active_slot: "A".to_string(),
            })
        }
    }

    pub fn save(&self) -> Result<()> {
        let file_content = serde_json::to_string_pretty(self)?;
        fs::write(OTA_STATE_PATH, file_content)?;
        Ok(())
    }
}

pub async fn check_for_update(client: &Client, config: &Config, current_state: &mut OtaState) -> Result<()> {
    log::info!("Checking for firmware updates...");
    
    match net::fetch_latest_firmware(client, config).await {
        Ok(Some(firmware_metadata)) => {
            if firmware_metadata.version != current_state.current_version {
                log::info!("New firmware version available: {}", firmware_metadata.version);
                
                // In a real device, you'd download to the inactive slot.
                // Here, we just download it to a firmware directory.
                if let Ok(firmware_data) = net::download_firmware(client, &firmware_metadata.url).await {
                    
                    // Verify checksum (placeholder)
                    log::info!("Checksum verification would happen here.");

                    // Create firmware directory if it doesn't exist
                    fs::create_dir_all(FIRMWARE_DIR)?;
                    let file_path = Path::new(FIRMWARE_DIR).join(format!("firmware_{}.bin", firmware_metadata.version));
                    fs::write(file_path, firmware_data)?;
                    log::info!("Firmware {} saved.", firmware_metadata.version);

                    // "Switch" to the new version
                    current_state.current_version = firmware_metadata.version;
                    current_state.active_slot = if current_state.active_slot == "A" { "B" } else { "A" }.to_string();
                    current_state.save()?;
                    
                    log::info!("Switched to new firmware version: {}. Rebooting...", current_state.current_version);

                    // Simulate reboot by exiting. Docker will restart the container.
                    std::process::exit(0);
                }
            } else {
                log::info!("Device is up to date.");
            }
        }
        Ok(None) => {
            log::info!("No new firmware available from backend.");
        }
        Err(e) => {
            log::error!("Failed to check for firmware update: {}", e);
        }
    }

    Ok(())
}
