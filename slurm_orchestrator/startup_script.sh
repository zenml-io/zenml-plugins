#!/usr/bin/env bash
set -euo pipefail

# Docker and Python installation script for SLURM compute nodes
# This script ensures Docker and Python are available for ZenML pipelines

STAMP_DIR="/var/lib/hpctk"
STAMP="${STAMP_DIR}/bootstrap_docker_python_v1"
mkdir -p "$STAMP_DIR"

# Exit if already installed
if [ -f "$STAMP" ]; then
    echo "Bootstrap already completed, exiting..."
    exit 0
fi

echo "Starting Docker and Python installation..."

# Install Docker and Python based on the distribution
if command -v dnf >/dev/null 2>&1; then
    echo "Detected RHEL/CentOS 8+ (dnf)"
    dnf -y install dnf-plugins-core || true
    dnf config-manager --add-repo=https://download.docker.com/linux/centos/docker-ce.repo || true
    dnf -y install python3 python3-pip python3-devel curl ca-certificates
    dnf -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin
    systemctl enable --now docker || true
elif command -v yum >/dev/null 2>&1; then
    echo "Detected RHEL/CentOS 7 (yum)"
    yum -y install yum-utils || true
    yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo || true
    yum -y install python3 python3-pip python3-devel curl ca-certificates
    yum -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin
    systemctl enable --now docker || true
elif command -v apt-get >/dev/null 2>&1; then
    echo "Detected Debian/Ubuntu (apt)"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y python3 python3-pip python3-dev ca-certificates curl
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker || true
else
    echo "ERROR: Unsupported distribution - no package manager found"
    exit 1
fi

echo "Creating docker group and adding users..."

# Create docker group if it doesn't exist
groupadd -f docker || true

# Add slurm user to docker group (SLURM daemon user)
getent passwd slurm >/dev/null 2>&1 && usermod -aG docker slurm || true

# Add google-sudoers group members to docker group
if getent group google-sudoers >/dev/null 2>&1; then
    echo "Adding google-sudoers members to docker group..."
    getent group google-sudoers | awk -F: '{print $4}' | tr ',' '\n' | while read -r u; do
        if [ -n "$u" ]; then
            echo "Adding user $u to docker group"
            usermod -aG docker "$u" || true
        fi
    done
else
    echo "google-sudoers group not found, skipping..."
fi

# Add specific ZenML user to docker group (customize this)
# Replace 'hamza_zenml_io' with your actual username
ZENML_USER="hamza_zenml_io"
if getent passwd "$ZENML_USER" >/dev/null 2>&1; then
    echo "Adding ZenML user $ZENML_USER to docker group"
    usermod -aG docker "$ZENML_USER" || true
else
    echo "ZenML user $ZENML_USER not found, skipping..."
fi

# Verify Docker installation
echo "Verifying Docker installation..."
if command -v docker >/dev/null 2>&1; then
    echo "Docker installed successfully"
    docker --version
else
    echo "ERROR: Docker installation failed"
    exit 1
fi

# Create stamp file to indicate completion
touch "$STAMP"
echo "Bootstrap completed successfully!"

# Log completion
echo "$(date): Docker and Python bootstrap completed" >> /var/log/slurm_bootstrap.log