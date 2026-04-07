#!/bin/bash
# Minecraft Manager - Deployment Script for Debian 12 LXC
set -euo pipefail

echo "=== Minecraft Manager Installer ==="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root"
    exit 1
fi

# --- Java 21 (Temurin) ---
echo "Installing Java 21..."
apt-get update
apt-get install -y wget gnupg
wget -qO - https://packages.adoptium.net/artifactory/api/gpg/key/public | gpg --dearmor > /usr/share/keyrings/adoptium.gpg
echo "deb [signed-by=/usr/share/keyrings/adoptium.gpg] https://packages.adoptium.net/artifactory/deb bookworm main" > /etc/apt/sources.list.d/adoptium.list
apt-get update
apt-get install -y temurin-21-jre

# --- mDNS (Avahi) ---
echo "Installing Avahi for mDNS (minecraft.local)..."
apt-get install -y avahi-daemon
systemctl enable avahi-daemon
systemctl start avahi-daemon

# --- Python + pip ---
echo "Installing Python..."
apt-get install -y python3 python3-pip python3-venv

# --- Create minecraft user ---
echo "Creating minecraft user..."
useradd -r -m -d /opt/minecraft -s /bin/bash minecraft || true

# --- Directory structure ---
echo "Setting up directories..."
mkdir -p /opt/minecraft/{plugins,logs}
mkdir -p /opt/minecraft-versions
mkdir -p /var/backups/minecraft/{daily,monthly,update,worlds}
chown -R minecraft:minecraft /opt/minecraft /opt/minecraft-versions /var/backups/minecraft

# --- Download Paper ---
echo "Downloading Paper..."
MC_VER=$(curl -s https://api.papermc.io/v2/projects/paper | python3 -c "import sys,json;print(json.load(sys.stdin)['versions'][-1])")
BUILD=$(curl -s "https://api.papermc.io/v2/projects/paper/versions/$MC_VER/builds" | python3 -c "import sys,json;print(json.load(sys.stdin)['builds'][-1]['build'])")
JAR="paper-$MC_VER-$BUILD.jar"
curl -o "/opt/minecraft-versions/$JAR" "https://api.papermc.io/v2/projects/paper/versions/$MC_VER/builds/$BUILD/downloads/$JAR"
ln -sf "/opt/minecraft-versions/$JAR" /opt/minecraft/paper.jar
echo "paper-$MC_VER-$BUILD" > /opt/minecraft/VERSION

# --- Download Geyser + Floodgate ---
echo "Downloading Geyser + Floodgate..."
curl -L -o /opt/minecraft/plugins/Geyser-Spigot.jar \
    "https://download.geysermc.org/v2/projects/geyser/versions/latest/builds/latest/downloads/spigot"
curl -L -o /opt/minecraft/plugins/floodgate-spigot.jar \
    "https://download.geysermc.org/v2/projects/floodgate/versions/latest/builds/latest/downloads/spigot"

# --- EULA ---
echo "eula=true" > /opt/minecraft/eula.txt

# --- server.properties ---
if [ ! -f /opt/minecraft/server.properties ]; then
    cat > /opt/minecraft/server.properties <<'PROPS'
level-name=world
server-port=25565
gamemode=survival
difficulty=normal
max-players=10
motd=Minecraft Server
online-mode=true
white-list=false
PROPS
fi

chown -R minecraft:minecraft /opt/minecraft

# --- Systemd service ---
echo "Installing systemd service..."
cp "$(dirname "$0")/../systemd/minecraft.service" /etc/systemd/system/minecraft.service
systemctl daemon-reload
systemctl enable minecraft

# --- Install Manager ---
echo "Installing Minecraft Manager..."
MANAGER_DIR=/opt/minecraft-manager
mkdir -p "$MANAGER_DIR"
cp -r "$(dirname "$0")/../"* "$MANAGER_DIR/"
cd "$MANAGER_DIR"
python3 -m venv venv
source venv/bin/activate
pip install -e .

# --- Manager systemd service ---
cat > /etc/systemd/system/minecraft-manager.service <<EOF
[Unit]
Description=Minecraft Manager Web UI
After=network.target

[Service]
Type=simple
User=minecraft
Group=minecraft
WorkingDirectory=$MANAGER_DIR
ExecStart=$MANAGER_DIR/venv/bin/uvicorn minecraft_manager.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
Environment=MCM_MINECRAFT_DIR=/opt/minecraft
Environment=MCM_VERSIONS_DIR=/opt/minecraft-versions
Environment=MCM_BACKUP_DIR=/var/backups/minecraft
Environment=MCM_STDIN_PIPE=/run/minecraft.stdin

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable minecraft-manager

# --- Nginx ---
echo "Setting up nginx..."
apt-get install -y nginx apache2-utils

# Generate self-signed cert
mkdir -p /etc/nginx/ssl
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/minecraft.key \
    -out /etc/nginx/ssl/minecraft.crt \
    -subj "/CN=minecraft.local"

cp "$(dirname "$0")/nginx.conf" /etc/nginx/sites-available/minecraft
ln -sf /etc/nginx/sites-available/minecraft /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Create basic auth user
echo "Set up web UI password:"
htpasswd -c /etc/nginx/.htpasswd admin

nginx -t && systemctl restart nginx

# --- Cron for daily backup ---
cat > /etc/cron.d/minecraft-backup <<'CRON'
# Daily backup at 3:00 AM
0 3 * * * minecraft MCM_MINECRAFT_DIR=/opt/minecraft MCM_BACKUP_DIR=/var/backups/minecraft /opt/minecraft-manager/scripts/backup.sh daily >> /var/log/minecraft-backup.log 2>&1
# Monthly backup on the 1st at 3:30 AM
30 3 1 * * minecraft MCM_MINECRAFT_DIR=/opt/minecraft MCM_BACKUP_DIR=/var/backups/minecraft /opt/minecraft-manager/scripts/backup.sh monthly >> /var/log/minecraft-backup.log 2>&1
CRON

echo ""
echo "=== Installation Complete ==="
echo "Start Minecraft:  systemctl start minecraft"
echo "Start Manager:    systemctl start minecraft-manager"
echo "Manager URL:      https://minecraft.local/"
echo ""
echo "mDNS: minecraft.local is advertised via Avahi (no DNS config needed)"
echo ""
echo "Next steps:"
echo "1. Start the Minecraft server and let it generate the world"
echo "2. Configure Geyser: /opt/minecraft/plugins/Geyser-Spigot/config.yml"
