use anyhow::Result;
use reqwest::Client;
use std::fs;
use std::path::Path;
use serde::{Deserialize, Serialize};
use tracing::{info, error, debug}; // Add debug import

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
            info!(path = OTA_STATE_PATH, ?state, "Loaded OTA state from file");
            Ok(state)
        } else {
            // Default state if none exists
            let default_state = OtaState {
                current_version: env!("CARGO_PKG_VERSION").to_string(),
                active_slot: "A".to_string(),
            };
            info!(path = OTA_STATE_PATH, ?default_state, "No OTA state file found, using default");
            Ok(default_state)
        }
    }

    pub fn save(&self) -> Result<()> {
        let file_content = serde_json::to_string_pretty(self)?;
        fs::write(OTA_STATE_PATH, file_content)?;
        info!(path = OTA_STATE_PATH, ?self, "OTA state saved to file");
        Ok(())
    }
}

pub async fn check_for_update(client: &Client, config: &Config, current_state: &mut OtaState) -> Result<()> {
    info!(device_id = %config.device_id, current_version = %current_state.current_version, "Checking for firmware updates");
    
    match net::fetch_latest_firmware(client, config).await {
        Ok(Some(firmware_metadata)) => {
            if firmware_metadata.version != current_state.current_version {
                info!(
                    device_id = %config.device_id, 
                    current_version = %current_state.current_version, 
                    new_version = %firmware_metadata.version, 
                    "New firmware version available"
                );
                
                // In a real device, you'd download to the inactive slot.
                // Here, we just download it to a firmware directory.
                match net::download_firmware(client, config, &firmware_metadata.url).await { // Pass config to download_firmware
                    Ok(firmware_data) => {
                        debug!(device_id = %config.device_id, "Checksum verification would happen here.");

                        // Create firmware directory if it doesn't exist
                        fs::create_dir_all(FIRMWARE_DIR)?;
                        let file_path = Path::new(FIRMWARE_DIR).join(format!("firmware_{}.bin", firmware_metadata.version));
                        fs::write(&file_path, firmware_data)?; // Pass reference to file_path
                        info!(device_id = %config.device_id, file_path = %file_path.display(), "Firmware saved.");

                        // "Switch" to the new version
                        current_state.current_version = firmware_metadata.version;
                        current_state.active_slot = if current_state.active_slot == "A" { "B" } else { "A" }.to_string();
                        current_state.save()?;
                        
                        info!(device_id = %config.device_id, new_version = %current_state.current_version, "Switched to new firmware version. Rebooting...");

                        // Simulate reboot by exiting. Docker will restart the container.
                        std::process::exit(0);
                    },
                    Err(e) => {
                        error!(device_id = %config.device_id, error = %e, "Failed to download new firmware");
                    }
                }
            } else {
                info!(device_id = %config.device_id, current_version = %current_state.current_version, "Device is up to date.");
            }
        }
        Ok(None) => {
            info!(device_id = %config.device_id, "No new firmware available from backend.");
        }
        Err(e) => {
            error!(device_id = %config.device_id, error = %e, "Failed to check for firmware update");
        }
    }

    Ok(())
}