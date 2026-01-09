use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::env;
use std::fs;
use std::io::{self, Write};
use uuid::Uuid;
use serde_json::Value; // Import Value for chaos_flags
use std::path::PathBuf; // Import PathBuf

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct Config {
    pub device_id: String,
    pub auth_token: Option<String>,
    pub backend_url: String,
    pub sample_interval_secs: u64,
    pub upload_interval_secs: u64,
    pub heartbeat_interval_secs: u64,
    pub ota_check_interval_secs: u64,
    pub region: Option<String>,
    pub hardware_rev: Option<String>,
    pub desired_shadow_state: Option<serde_json::Value>,
    pub reported_shadow_state: Option<serde_json::Value>,
    pub chaos_flags: Option<Value>, // New field for chaos flags
}

impl Config {
    pub fn from_env() -> Result<Self> {
        let device_id = env::var("DEVICE_ID").unwrap_or_else(|_| Uuid::new_v4().to_string());
        let auth_token = env::var("AUTH_TOKEN").ok();
        let backend_url = env::var("BACKEND_URL").unwrap_or_else(|_| "http://localhost:8000".to_string());
        
        let sample_interval_secs = get_env_var_u64("SAMPLE_INTERVAL_SECS", 10);
        let upload_interval_secs = get_env_var_u64("UPLOAD_INTERVAL_SECS", 60);
        let heartbeat_interval_secs = get_env_var_u64("HEARTBEAT_INTERVAL_SECS", 30);
        let ota_check_interval_secs = get_env_var_u64("OTA_CHECK_INTERVAL_SECS", 300);

        let region = env::var("REGION").ok();
        let hardware_rev = env::var("HARDWARE_REV").ok();

        Ok(Config {
            device_id,
            auth_token,
            backend_url,
            sample_interval_secs,
            upload_interval_secs,
            heartbeat_interval_secs,
            ota_check_interval_secs,
            region,
            hardware_rev,
            desired_shadow_state: None, // Initialize to None
            reported_shadow_state: None, // Initialize to None
            chaos_flags: None, // Initialize chaos_flags to None
        })
    }

    fn get_config_file_path() -> PathBuf {
        let config_dir = env::var("CONFIG_DIR").unwrap_or_else(|_| ".".to_string());
        PathBuf::from(config_dir).join("device_config.json")
    }

    pub fn load_from_file() -> Result<Self> {
        let config_file_path = Self::get_config_file_path();
        let contents = fs::read_to_string(&config_file_path)?;
        let config: Config = serde_json::from_str(&contents)?;
        Ok(config)
    }

    pub fn save_to_file(&self) -> Result<()> {
        let config_file_path = Self::get_config_file_path();
        // Ensure the directory exists
        if let Some(parent) = config_file_path.parent() {
            fs::create_dir_all(parent)?;
        }
        let contents = serde_json::to_string_pretty(self)?;
        let mut file = fs::File::create(&config_file_path)?;
        file.write_all(contents.as_bytes())?;
        Ok(())
    }
}

fn get_env_var_u64(key: &str, default: u64) -> u64 {
    env::var(key)
        .ok()
        .and_then(|val| val.parse().ok())
        .unwrap_or(default)
}