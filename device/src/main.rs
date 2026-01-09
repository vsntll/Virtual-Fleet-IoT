use anyhow::Result;
use reqwest::Client;
use std::collections::HashMap;
use std::time::Duration;
use tokio::time;
use serde_json::{json, Value};
use tracing_subscriber::{fmt, prelude::*, filter};
use tracing::{info, error, warn};
use rand::Rng; // Import rand for random numbers

mod config;
mod net;
mod ota;
mod simulate;
mod storage;
mod types;

use config::Config;
use ota::OtaState;
use types::ReportedShadowState;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize tracing with JSON formatter
    tracing_subscriber::registry()
        .with(fmt::layer().json())
        .with(filter::EnvFilter::from_default_env()) // Allows setting log level via RUST_LOG env var
        .init();

    let mut config = match Config::load_from_file() {
        Ok(mut conf) => {
            info!(device_id = %conf.device_id, "Loaded config from file: {:?}", conf);
            // Initialize shadow states from config if they exist
            if conf.desired_shadow_state.is_none() {
                conf.desired_shadow_state = Some(json!({}));
            }
            if conf.reported_shadow_state.is_none() {
                conf.reported_shadow_state = Some(json!({}));
            }
            conf
        },
        Err(e) => {
            error!(error = %e, "Could not load config from file. Attempting to register device.");
            let mut boot_config = Config::from_env()?; // Get initial config from env (especially backend_url)
            
            let client = Client::new();
            let register_response = net::register_device(&client, &boot_config.backend_url, uuid::Uuid::new_v4()).await?;
            
            boot_config.device_id = register_response.device_id.to_string();
            boot_config.auth_token = Some(register_response.auth_token.to_string());

            // Initialize generic shadow states to empty JSON objects upon registration
            boot_config.desired_shadow_state = Some(json!({}));
            boot_config.reported_shadow_state = Some(json!({}));
            boot_config.chaos_flags = Some(json!({})); // Initialize chaos_flags as empty

            boot_config.save_to_file()?;
            info!(device_id = %boot_config.device_id, "Device registered and config saved.");
            boot_config
        }
    };

    info!(device_id = %config.device_id, "Device starting with config: {:?}", config);

    let mut conn = storage::init()?;
    info!(device_id = %config.device_id, "Initialized local database.");

    let mut ota_state = OtaState::load()?;
    info!(device_id = %config.device_id, "Loaded OTA state: {:?}", ota_state);

    let client = Client::new();
    let mut rng = rand::thread_rng(); // Initialize random number generator

    let mut sample_interval_secs = config.sample_interval_secs;
    let mut upload_interval_secs = config.upload_interval_secs;
    let mut heartbeat_interval_secs = config.heartbeat_interval_secs;
    let shadow_check_interval_secs = 60; // How often to check for shadow updates

    let mut sample_interval = time::interval(Duration::from_secs(sample_interval_secs));
    let mut upload_interval = time::interval(Duration::from_secs(upload_interval_secs));
    let mut heartbeat_interval = time::interval(Duration::from_secs(heartbeat_interval_secs));
    let mut ota_check_interval = time::interval(Duration::from_secs(config.ota_check_interval_secs));
    let mut shadow_check_interval = time::interval(Duration::from_secs(shadow_check_interval_secs));

    // Initialize current reported state based on config
    let mut current_reported_state = config.reported_shadow_state.clone().unwrap_or_else(|| json!({})); // Added clone()

    loop {
        tokio::select! {
            _ = sample_interval.tick() => {
                let mut measurement = simulate::generate_measurement(ota_state.current_version.clone()); // Pass firmware_version
                info!(device_id = %config.device_id, "Generated measurement: {:?}", measurement);
                if let Err(e) = storage::append_measurement(&conn, &measurement) { // No await here
                    error!(device_id = %config.device_id, error = %e, "Failed to store measurement");
                }
            }
            _ = upload_interval.tick() => {
                info!(device_id = %config.device_id, "Attempting to upload measurements...");

                // --- CHAOS: Random Error ---
                let mut should_inject_error = false;
                if let Some(chaos) = &config.chaos_flags {
                    if let Some(Value::Bool(random_error)) = chaos.get("random_error") {
                        if *random_error && rng.gen_bool(0.1) { // 10% chance to inject error
                            warn!(device_id = %config.device_id, chaos_type = "random_error", "Injecting random error for upload");
                            should_inject_error = true;
                        }
                    }
                }
                if should_inject_error {
                    error!(device_id = %config.device_id, "Simulated network error during upload.");
                    // Skip actual upload, measurements remain in local DB
                    continue;
                }
                // --- END CHAOS ---

                match storage::get_and_clear_measurements(&mut conn, 100) { // No await here
                    Ok(measurements) => {
                        if !measurements.is_empty() {
                            info!(device_id = %config.device_id, count = measurements.len(), "Uploading measurements");
                            if let Err(e) = net::send_ingest(&client, &config, &measurements).await {
                                error!(device_id = %config.device_id, error = %e, "Failed to ingest measurements. Re-inserting into db.");
                                // simplified error handling: just put them back.
                                for m in measurements {
                                    if let Err(e_reinsert) = storage::append_measurement(&conn, &m) { // No await here
                                        error!(device_id = %config.device_id, error = %e_reinsert, "Failed to re-insert measurement");
                                    }
                                }
                            } else {
                                info!(device_id = %config.device_id, count = measurements.len(), "Measurements ingested successfully");
                            }
                        } else {
                            info!(device_id = %config.device_id, "No measurements to upload");
                        }
                    }
                    Err(e) => {
                        error!(device_id = %config.device_id, error = %e, "Failed to get measurements from local DB");
                    }
                }
            }
            _ = heartbeat_interval.tick() => {
                info!(device_id = %config.device_id, "Sending heartbeat");
                
                // --- CHAOS: Random Error ---
                let mut should_inject_error = false;
                if let Some(chaos) = &config.chaos_flags {
                    if let Some(Value::Bool(random_error)) = chaos.get("random_error") {
                        if *random_error && rng.gen_bool(0.1) { // 10% chance to inject error
                            warn!(device_id = %config.device_id, chaos_type = "random_error", "Injecting random error for heartbeat");
                            should_inject_error = true;
                        }
                    }
                }
                if should_inject_error {
                    error!(device_id = %config.device_id, "Simulated network error during heartbeat.");
                    // Skip actual heartbeat
                    continue;
                }
                // --- END CHAOS ---

                match net::send_heartbeat(&client, &config, &ota_state.current_version, sample_interval_secs, upload_interval_secs, heartbeat_interval_secs).await {
                    Ok(desired_state) => {
                        info!(device_id = %config.device_id, ?desired_state, "Received desired state in heartbeat response");
                        // These interval updates are also reflected in the shadow, but handled here for immediate effect
                        if desired_state.desired_sample_interval_secs != sample_interval_secs {
                            sample_interval_secs = desired_state.desired_sample_interval_secs;
                            sample_interval = time::interval(Duration::from_secs(sample_interval_secs));
                            info!(device_id = %config.device_id, new_interval = sample_interval_secs, "Shadow updated sample interval");
                        }
                        if desired_state.desired_upload_interval_secs != upload_interval_secs {
                            upload_interval_secs = desired_state.desired_upload_interval_secs;
                            upload_interval = time::interval(Duration::from_secs(upload_interval_secs));
                            info!(device_id = %config.device_id, new_interval = upload_interval_secs, "Shadow updated upload interval");
                        }
                        if desired_state.desired_heartbeat_interval_secs != heartbeat_interval_secs {
                            heartbeat_interval_secs = desired_state.desired_heartbeat_interval_secs;
                            heartbeat_interval = time::interval(Duration::from_secs(heartbeat_interval_secs));
                            info!(device_id = %config.device_id, new_interval = heartbeat_interval_secs, "Shadow updated heartbeat interval");
                        }
                        // Note: desired_version is not handled here, but in the ota module.
                    }
                    Err(e) => {
                        error!(device_id = %config.device_id, error = %e, "Failed to send heartbeat");
                    }
                }
            }
            _ = ota_check_interval.tick() => {
                info!(device_id = %config.device_id, "Checking for OTA update");
                if let Err(e) = ota::check_for_update(&client, &config, &mut ota_state).await {
                    error!(device_id = %config.device_id, error = %e, "OTA check failed");
                } else {
                    info!(device_id = %config.device_id, "OTA check completed");
                }
            }
            _ = shadow_check_interval.tick() => {
                info!(device_id = %config.device_id, "Checking device shadow...");
                match net::fetch_device_shadow(&client, &config).await {
                    Ok(shadow) => {
                        if let Some(desired) = shadow.desired {
                            info!(device_id = %config.device_id, ?desired, "Received desired shadow state");

                            // --- CHAOS: Update chaos_flags in config ---
                            if let Some(chaos_flags_value) = desired.get("chaos_flags") {
                                config.chaos_flags = Some(chaos_flags_value.clone());
                                info!(device_id = %config.device_id, ?chaos_flags_value, "Updated chaos_flags from desired shadow");
                            } else {
                                config.chaos_flags = None; // Clear chaos flags if not present in desired state
                                info!(device_id = %config.device_id, "Chaos flags cleared from desired shadow");
                            }
                            // --- END CHAOS ---

                            // For simplicity, apply changes to existing intervals if present in desired shadow
                            // In a real device, this would be a more robust config application logic
                            if let Some(Value::Number(s_interval)) = desired.get("sample_interval_secs") {
                                if let Some(new_val) = s_interval.as_u64() {
                                    if new_val != sample_interval_secs {
                                        sample_interval_secs = new_val;
                                        sample_interval = time::interval(Duration::from_secs(sample_interval_secs));
                                        info!(device_id = %config.device_id, new_interval = sample_interval_secs, "Shadow updated sample interval");
                                    }
                                }
                            }
                            if let Some(Value::Number(u_interval)) = desired.get("upload_interval_secs") {
                                if let Some(new_val) = u_interval.as_u64() {
                                    if new_val != upload_interval_secs {
                                        upload_interval_secs = new_val;
                                        upload_interval = time::interval(Duration::from_secs(upload_interval_secs));
                                        info!(device_id = %config.device_id, new_interval = upload_interval_secs, "Shadow updated upload interval");
                                    }
                                }
                            }
                            if let Some(Value::Number(h_interval)) = desired.get("heartbeat_interval_secs") {
                                if let Some(new_val) = h_interval.as_u64() {
                                    if new_val != heartbeat_interval_secs {
                                        heartbeat_interval_secs = new_val;
                                        heartbeat_interval = time::interval(Duration::from_secs(heartbeat_interval_secs));
                                        info!(device_id = %config.device_id, new_interval = heartbeat_interval_secs, "Shadow updated heartbeat interval");
                                    }
                                }
                            }

                            // Update local reported state to reflect current active configuration
                            current_reported_state["sample_interval_secs"] = json!(sample_interval_secs);
                            current_reported_state["upload_interval_secs"] = json!(upload_interval_secs);
                            current_reported_state["heartbeat_interval_secs"] = json!(heartbeat_interval_secs);
                            // Also report current chaos flags
                            current_reported_state["chaos_flags"] = config.chaos_flags.clone().unwrap_or_else(|| json!({}));


                            // Persist reported shadow state to config
                            config.reported_shadow_state = Some(current_reported_state.clone());
                            if let Err(e) = config.save_to_file() {
                                error!(device_id = %config.device_id, error = %e, "Failed to save config with reported shadow state");
                            }

                            // Report updated state back to backend
                            if let Err(e) = net::report_device_shadow(&client, &config, ReportedShadowState { state: current_reported_state.clone() }).await {
                                error!(device_id = %config.device_id, error = %e, "Failed to report shadow state");
                            } else {
                                info!(device_id = %config.device_id, "Reported current shadow state");
                            }
                        } else {
                            info!(device_id = %config.device_id, "No desired shadow state received");
                        }
                    }
                    Err(e) => {
                        error!(device_id = %config.device_id, error = %e, "Failed to fetch device shadow");
                    }
                }
            }
        }
    }
}