use anyhow::Result;
use rusqlite::{params, Connection};
use std::path::Path;
use tracing::{info, error};

use crate::types::Measurement;

const DB_PATH: &str = "./device_storage.db";

pub fn init() -> Result<Connection> {
    let path = Path::new(DB_PATH);
    let conn = Connection::open(path)?;

    info!("Initializing local database at {}", DB_PATH);
    conn.execute(
        "CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY,
            timestamp TEXT NOT NULL,
            temp REAL NOT NULL,
            humidity REAL NOT NULL,
            battery REAL NOT NULL,
            sequence_number INTEGER NOT NULL,
            latitude REAL,
            longitude REAL,
            speed REAL,
            firmware_version TEXT
        )",
        [],
    )?;
    info!("Database initialization complete.");
    Ok(conn)
}

pub fn append_measurement(conn: &Connection, measurement: &Measurement) -> Result<()> {
    info!(
        timestamp = %measurement.timestamp,
        temp = measurement.temp,
        humidity = measurement.humidity,
        battery = measurement.battery,
        sequence_number = measurement.sequence_number,
        latitude = measurement.latitude,
        longitude = measurement.longitude,
        speed = measurement.speed,
        firmware_version = measurement.firmware_version,
        "Appending measurement to local DB"
    );
    conn.execute(
        "INSERT INTO measurements (timestamp, temp, humidity, battery, sequence_number, latitude, longitude, speed, firmware_version) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
        params![
            measurement.timestamp,
            measurement.temp,
            measurement.humidity,
            measurement.battery,
            measurement.sequence_number,
            measurement.latitude,
            measurement.longitude,
            measurement.speed,
            measurement.firmware_version,
        ],
    )?;
    Ok(())
}

pub fn get_and_clear_measurements(conn: &mut Connection, batch_size: u32) -> Result<Vec<Measurement>> {
    let tx = conn.transaction()?;
    
    let (measurements, ids_to_delete) = {
        let mut stmt = tx.prepare("SELECT id, timestamp, temp, humidity, battery, sequence_number, latitude, longitude, speed, firmware_version FROM measurements ORDER BY id LIMIT ?")?;
        
        let measurements_iter = stmt.query_map(params![batch_size], |row| {
            Ok((
                row.get::<_, i64>(0)?,
                Measurement {
                    timestamp: row.get(1)?,
                    temp: row.get(2)?,
                    humidity: row.get(3)?,
                    battery: row.get(4)?,
                    sequence_number: row.get(5)?,
                    latitude: row.get(6)?,
                    longitude: row.get(7)?,
                    speed: row.get(8)?,
                    firmware_version: row.get(9)?,
                },
            ))
        })?;

        let mut measurements = Vec::new();
        let mut ids_to_delete = Vec::new();

        for result in measurements_iter {
            let (id, measurement) = result?;
            measurements.push(measurement);
            ids_to_delete.push(id);
        }
        (measurements, ids_to_delete)
    };
    
    if !ids_to_delete.is_empty() {
        info!("Clearing {} measurements from local DB", ids_to_delete.len());
        for id in ids_to_delete {
            if let Err(e) = tx.execute("DELETE FROM measurements WHERE id = ?", params![id]) {
                error!(error = %e, id = id, "Failed to delete measurement from local DB");
            }
        }
    }
    
    tx.commit()?;
    info!("Batch of measurements committed and cleared from local DB");
    Ok(measurements)
}