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

    // Fetch initial fleet settings
    let mut settings = match net::fetch_fleet_settings(&client, &config).await {
        Ok(s) => s,
        Err(e) => {
            log::error!("Failed to fetch initial fleet settings: {}. Using defaults.", e);
            // Default settings if the backend is unavailable at startup
            types::FleetSettings {
                num_devices: 1, // Not used by the device, but good to have a default
                sample_interval_secs: config.sample_interval_secs,
                upload_interval_secs: config.upload_interval_secs,
                heartbeat_interval_secs: config.heartbeat_interval_secs,
            }
        }
    };
    log::info!("Initial fleet settings: {:?}", settings);


    let mut sample_interval = time::interval(Duration::from_secs(settings.sample_interval_secs));
    let mut upload_interval = time::interval(Duration::from_secs(settings.upload_interval_secs));
    let mut heartbeat_interval = time::interval(Duration::from_secs(settings.heartbeat_interval_secs));
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
                // Fetch new settings after heartbeat
                match net::fetch_fleet_settings(&client, &config).await {
                    Ok(new_settings) => {
                        if new_settings.sample_interval_secs != settings.sample_interval_secs {
                            sample_interval = time::interval(Duration::from_secs(new_settings.sample_interval_secs));
                            log::info!("Updated sample interval to {}s", new_settings.sample_interval_secs);
                        }
                        if new_settings.upload_interval_secs != settings.upload_interval_secs {
                            upload_interval = time::interval(Duration::from_secs(new_settings.upload_interval_secs));
                            log::info!("Updated upload interval to {}s", new_settings.upload_interval_secs);
                        }
                        if new_settings.heartbeat_interval_secs != settings.heartbeat_interval_secs {
                            heartbeat_interval = time::interval(Duration::from_secs(new_settings.heartbeat_interval_secs));
                            log::info!("Updated heartbeat interval to {}s", new_settings.heartbeat_interval_secs);
                        }
                        settings = new_settings;
                    }
                    Err(e) => {
                        log::error!("Failed to fetch fleet settings after heartbeat: {}", e);
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