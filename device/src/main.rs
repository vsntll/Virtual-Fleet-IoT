fn main() {
    println!("Device starting...");
    loop {
        // Just keep the container alive
        std::thread::sleep(std::time::Duration::from_secs(60));
    }
}
