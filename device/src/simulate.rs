use crate::types::Measurement;
use chrono::Utc;
use std::sync::atomic::{AtomicU32, Ordering};

// A simple atomic counter for the sequence number.
static SEQUENCE_COUNTER: AtomicU32 = AtomicU32::new(0);

pub fn generate_measurement() -> Measurement {
    let sequence_number = SEQUENCE_COUNTER.fetch_add(1, Ordering::SeqCst);
    
    // Simulate some realistic-looking sensor data
    let temp = 20.0 + (rand::random::<f32>() * 5.0) - 2.5; // 17.5 to 22.5
    let humidity = 50.0 + (rand::random::<f32>() * 10.0) - 5.0; // 45.0 to 55.0
    let battery = 0.9 - (rand::random::<f32>() * 0.1); // 0.8 to 0.9, slowly decreasing

    Measurement {
        timestamp: Utc::now(),
        temp,
        humidity,
        battery,
        sequence_number,
    }
}
