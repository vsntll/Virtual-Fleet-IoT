use anyhow::Result;
use rusqlite::{params, Connection}; // Modified line
use std::path::Path;

use crate::types::Measurement;

const DB_PATH: &str = "./device_storage.db";

pub fn init() -> Result<Connection> {
    let path = Path::new(DB_PATH);
    let conn = Connection::open(path)?;

    conn.execute(
        "CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY,
            timestamp TEXT NOT NULL,
            temp REAL NOT NULL,
            humidity REAL NOT NULL,
            battery REAL NOT NULL,
            sequence_number INTEGER NOT NULL
        )",
        [], // Modified line
    )?;

    Ok(conn)
}

pub fn append_measurement(conn: &Connection, measurement: &Measurement) -> Result<()> {
    conn.execute(
        "INSERT INTO measurements (timestamp, temp, humidity, battery, sequence_number) VALUES (?1, ?2, ?3, ?4, ?5)",
        params![
            measurement.timestamp,
            measurement.temp,
            measurement.humidity,
            measurement.battery,
            measurement.sequence_number,
        ],
    )?;
    Ok(())
}

pub fn get_and_clear_measurements(conn: &mut Connection, batch_size: u32) -> Result<Vec<Measurement>> {
    let tx = conn.transaction()?;
    
    let (measurements, ids_to_delete) = { // Start of new scope
        let mut stmt = tx.prepare("SELECT id, timestamp, temp, humidity, battery, sequence_number FROM measurements ORDER BY id LIMIT ?")?;
        
        let measurements_iter = stmt.query_map(params![batch_size], |row| {
            Ok((
                row.get::<_, i64>(0)?,
                Measurement {
                    timestamp: row.get(1)?,
                    temp: row.get(2)?,
                    humidity: row.get(3)?,
                    battery: row.get(4)?,
                    sequence_number: row.get(5)?,
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
    }; // End of new scope, stmt and measurements_iter are dropped
    
    if !ids_to_delete.is_empty() {
        // In a real-world scenario with a high volume of data, this would be inefficient.
        // A single DELETE statement with a WHERE id IN (...) clause would be better,
        // but rusqlite doesn't support binding a list of values directly in a standard way.
        for id in ids_to_delete {
            tx.execute("DELETE FROM measurements WHERE id = ?", params![id])?;
        }
    }
    
    tx.commit()?;

    Ok(measurements)
}