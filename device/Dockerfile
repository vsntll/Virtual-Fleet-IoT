FROM rust:bookworm as builder
WORKDIR /usr/src/app
COPY device/Cargo.toml .
COPY device/src ./src
RUN cargo install --path .

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y libssl3 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/local/cargo/bin/device /usr/local/bin/device
CMD ["/usr/local/bin/device"]
