use anyhow::Result;
use serde::Deserialize;
use std::env;
use uuid::Uuid;

#[derive(Debug, Deserialize, Clone)]
pub struct Config {
    pub device_id: String,
    pub backend_url: String,
    pub sample_interval_secs: u64,
    pub upload_interval_secs: u64,
    pub heartbeat_interval_secs: u64,
    pub ota_check_interval_secs: u64,
}

impl Config {
    pub fn from_env() -> Result<Self> {
        let device_id = env::var("DEVICE_ID").unwrap_or_else(|_| Uuid::new_v4().to_string());
        let backend_url = env::var("BACKEND_URL").unwrap_or_else(|_| "http://localhost:8000".to_string());
        
        let sample_interval_secs = get_env_var_u64("SAMPLE_INTERVAL_SECS", 10);
        let upload_interval_secs = get_env_var_u64("UPLOAD_INTERVAL_SECS", 60);
        let heartbeat_interval_secs = get_env_var_u64("HEARTBEAT_INTERVAL_SECS", 30);
        let ota_check_interval_secs = get_env_var_u64("OTA_CHECK_INTERVAL_SECS", 300);

        Ok(Config {
            device_id,
            backend_url,
            sample_interval_secs,
            upload_interval_secs,
            heartbeat_interval_secs,
            ota_check_interval_secs,
        })
    }
}

fn get_env_var_u64(key: &str, default: u64) -> u64 {
    env::var(key)
        .ok()
        .and_then(|val| val.parse().ok())
        .unwrap_or(default)
}
