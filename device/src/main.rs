use anyhow::Result;
use reqwest::Client;
use std::time::Duration;
use tokio::time;

mod config;
mod net;
mod ota;
mod simulate;
mod storage;
mod types;

use config::Config;
use ota::OtaState;

#[tokio::main]
async fn main() -> Result<()> {
    env_logger::init();

    let config = Config::from_env()?;
    log::info!("Device starting with config: {:?}", config);

    let mut conn = storage::init()?;
    log::info!("Initialized local database.");

    let mut ota_state = OtaState::load()?;
    log::info!("Loaded OTA state: {:?}", ota_state);

    let client = Client::new();

    let mut sample_interval = time::interval(Duration::from_secs(config.sample_interval_secs));
    let mut upload_interval = time::interval(Duration::from_secs(config.upload_interval_secs));
    let mut heartbeat_interval = time::interval(Duration::from_secs(config.heartbeat_interval_secs));
    let mut ota_check_interval = time::interval(Duration::from_secs(config.ota_check_interval_secs));

    loop {
        tokio::select! {
            _ = sample_interval.tick() => {
                let measurement = simulate::generate_measurement();
                log::info!("Generated measurement: {:?}", measurement);
                if let Err(e) = storage::append_measurement(&conn, &measurement) {
                    log::error!("Failed to store measurement: {}", e);
                }
            }
            _ = upload_interval.tick() => {
                log::info!("Attempting to upload measurements...");
                match storage::get_and_clear_measurements(&mut conn, 100) {
                    Ok(measurements) => {
                        if !measurements.is_empty() {
                            if let Err(e) = net::send_ingest(&client, &config, &measurements).await {
                                log::error!("Failed to ingest measurements: {}. Re-inserting into db.", e);
                                // simplified error handling: just put them back.
                                for m in measurements {
                                    if let Err(e_reinsert) = storage::append_measurement(&conn, &m) {
                                        log::error!("Failed to re-insert measurement: {}", e_reinsert);
                                    }
                                }
                            }
                        }
                    }
                    Err(e) => {
                        log::error!("Failed to get measurements from local DB: {}", e);
                    }
                }
            }
            _ = heartbeat_interval.tick() => {
                if let Err(e) = net::send_heartbeat(&client, &config, &ota_state.current_version).await {
                    log::error!("Failed to send heartbeat: {}", e);
                }
            }
            _ = ota_check_interval.tick() => {
                if let Err(e) = ota::check_for_update(&client, &config, &mut ota_state).await {
                    log::error!("OTA check failed: {}", e);
                }
            }
        }
    }
}