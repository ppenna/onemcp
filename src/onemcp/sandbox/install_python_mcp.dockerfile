FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# System deps + Python + pip/pipx
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    python3 \
    python3-venv \
    python3-pip \
    pipx \
 && rm -rf /var/lib/apt/lists/*

# Install uv (and uvx) via the official installer
# The script installs into /root/.local/bin by default; move binaries to /usr/local/bin
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
 && mv /root/.local/bin/uv /usr/local/bin/uv \
 && mv /root/.local/bin/uvx /usr/local/bin/uvx \
 && rm -rf /root/.local

# Default shell
SHELL ["/bin/bash", "-c"]
