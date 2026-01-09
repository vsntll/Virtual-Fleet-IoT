use crate::types::Measurement;
use chrono::Utc;
use std::sync::atomic::{AtomicU32, Ordering};
use lazy_static::lazy_static;
use std::sync::Mutex;
use rand::Rng;

// A simple atomic counter for the sequence number.
static SEQUENCE_COUNTER: AtomicU32 = AtomicU32::new(0);

// Simulated device state for movement
lazy_static! {
    static ref CURRENT_LAT: Mutex<f32> = Mutex::new(34.052235); // Initial latitude (e.g., Los Angeles)
    static ref CURRENT_LON: Mutex<f32> = Mutex::new(-118.243683); // Initial longitude
    static ref CURRENT_SPEED: Mutex<f32> = Mutex::new(0.0); // Initial speed
}

pub fn generate_measurement() -> Measurement {
    let sequence_number = SEQUENCE_COUNTER.fetch_add(1, Ordering::SeqCst);
    let mut rng = rand::thread_rng();

    // Simulate some realistic-looking sensor data
    let temp = 20.0 + (rng.gen::<f32>() * 5.0) - 2.5; // 17.5 to 22.5
    let humidity = 50.0 + (rng.gen::<f32>() * 10.0) - 5.0; // 45.0 to 55.0
    let battery = 0.9 - (rng.gen::<f32>() * 0.1); // 0.8 to 0.9, slowly decreasing

    // Simulate movement
    let mut lat = CURRENT_LAT.lock().unwrap();
    let mut lon = CURRENT_LON.lock().unwrap();
    let mut speed = CURRENT_SPEED.lock().unwrap();

    // Small random walk for latitude and longitude
    *lat += (rng.gen::<f32>() - 0.5) * 0.001; // +/- 0.0005 degrees
    *lon += (rng.gen::<f32>() - 0.5) * 0.001; // +/- 0.0005 degrees

    // Simulate speed changes
    *speed += (rng.gen::<f32>() - 0.5) * 5.0; // +/- 2.5 units (e.g., km/h or mph)
    if *speed < 0.0 { *speed = 0.0; } // Speed cannot be negative
    if *speed > 100.0 { *speed = 100.0; } // Max speed

    Measurement {
        timestamp: Utc::now(),
        temp,
        humidity,
        battery,
        sequence_number,
        latitude: Some(*lat),
        longitude: Some(*lon),
        speed: Some(*speed),
    }
}
