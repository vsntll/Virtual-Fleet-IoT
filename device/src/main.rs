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

    let mut sample_interval_secs = config.sample_interval_secs;
    let mut upload_interval_secs = config.upload_interval_secs;
    let mut heartbeat_interval_secs = config.heartbeat_interval_secs;

    let mut sample_interval = time::interval(Duration::from_secs(sample_interval_secs));
    let mut upload_interval = time::interval(Duration::from_secs(upload_interval_secs));
    let mut heartbeat_interval = time::interval(Duration::from_secs(heartbeat_interval_secs));
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
                match net::send_heartbeat(&client, &config, &ota_state.current_version, sample_interval_secs, upload_interval_secs, heartbeat_interval_secs).await {
                    Ok(desired_state) => {
                        log::info!("Received desired state: {:?}", desired_state);
                        if desired_state.desired_sample_interval_secs != sample_interval_secs {
                            sample_interval_secs = desired_state.desired_sample_interval_secs;
                            sample_interval = time::interval(Duration::from_secs(sample_interval_secs));
                            log::info!("Updated sample interval to {}s", sample_interval_secs);
                        }
                        if desired_state.desired_upload_interval_secs != upload_interval_secs {
                            upload_interval_secs = desired_state.desired_upload_interval_secs;
                            upload_interval = time::interval(Duration::from_secs(upload_interval_secs));
                            log::info!("Updated upload interval to {}s", upload_interval_secs);
                        }
                        if desired_state.desired_heartbeat_interval_secs != heartbeat_interval_secs {
                            heartbeat_interval_secs = desired_state.desired_heartbeat_interval_secs;
                            heartbeat_interval = time::interval(Duration::from_secs(heartbeat_interval_secs));
                            log::info!("Updated heartbeat interval to {}s", heartbeat_interval_secs);
                        }
                        // Note: desired_version is not handled here, but in the ota module.
                    }
                    Err(e) => {
                        log::error!("Failed to send heartbeat: {}", e);
                    }
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