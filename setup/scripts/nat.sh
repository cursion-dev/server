#!/bin/bash

set -e

# ====== Configuration ======
VPC_CIDR="10.124.0.0/20"   # <-- Your VPC CIDR block
LISTEN_PORT="8888"         # <-- Tinyproxy listen port
# ============================

echo "[1/6] Updating system..."
apt update -y
apt install -y tinyproxy iptables-persistent curl

echo "[2/6] Configuring tinyproxy..."

# Backup original config
cp /etc/tinyproxy/tinyproxy.conf /etc/tinyproxy/tinyproxy.conf.bak

# Update tinyproxy.conf
cat <<EOF > /etc/tinyproxy/tinyproxy.conf
User nobody
Group nogroup
Port $LISTEN_PORT
Listen 0.0.0.0
Timeout 600
DefaultErrorFile "/usr/share/tinyproxy/default.html"
StatHost "tinyproxy.stats"
LogFile "/var/log/tinyproxy/tinyproxy.log"
LogLevel Info
MaxClients 100
MinSpareServers 5
MaxSpareServers 20
StartServers 10
MaxRequestsPerChild 0
ViaProxyName "tinyproxy"

Allow $VPC_CIDR

ConnectPort 443
ConnectPort 563
EOF

echo "[3/6] Restarting tinyproxy..."
systemctl restart tinyproxy
systemctl enable tinyproxy

echo "[4/6] Setting up IP forwarding..."

# Enable IP forwarding
sysctl -w net.ipv4.ip_forward=1
echo "net.ipv4.ip_forward = 1" >> /etc/sysctl.conf

echo "[5/6] Configuring iptables (NAT fallback)..."
# Flush existing rules & add new redirects
iptables -t nat -F
iptables -A FORWARD -i eth0 -j ACCEPT
iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE

# Save iptables rules
netfilter-persistent save
netfilter-persistent reload

echo "[6/6] Done!"

echo ""
echo "Tinyproxy running on port $LISTEN_PORT"
echo "Allowed VPC Range: $VPC_CIDR"
echo ""
