#!/bin/bash
# If using k8s, the VP_CIDR is likely specific to the cluster


set -e

# ========== Helper: Print usage ==========
usage() {
  echo "Usage: $0 [-c VPC_CIDR] [-p LISTEN_PORT]"
  echo "  -c CIDR block (e.g., 10.0.0.0/16)"
  echo "  -p Port to listen on (e.g., 8888)"
  exit 1
}

# ========== Parse flags ==========
while getopts ":c:p:" opt; do
  case "${opt}" in
    c)
      VPC_CIDR="${OPTARG}"
      ;;
    p)
      LISTEN_PORT="${OPTARG}"
      ;;
    *)
      usage
      ;;
  esac
done

# ========== Prompt if not provided ==========
if [ -z "$VPC_CIDR" ]; then
  read -rp "Enter VPC CIDR block (e.g., 10.0.0.0/16): " VPC_CIDR
fi

if [ -z "$LISTEN_PORT" ]; then
  read -rp "Enter listen port (e.g., 8888): " LISTEN_PORT
fi

# ========== Display final values ==========
echo "Using VPC_CIDR: $VPC_CIDR"
echo "Using LISTEN_PORT: $LISTEN_PORT"

# ========== Begin Script ==========
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
EOF

echo "[3/6] Restarting tinyproxy..."
systemctl restart tinyproxy
systemctl enable tinyproxy

echo "[4/6] Setting up IP forwarding..."
sysctl -w net.ipv4.ip_forward=1
echo "net.ipv4.ip_forward = 1" >> /etc/sysctl.conf

echo "[5/6] Configuring iptables (NAT fallback)..."
iptables -t nat -F
iptables -A FORWARD -i eth0 -j ACCEPT
iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE

netfilter-persistent save
netfilter-persistent reload

echo "[6/6] Done!"

echo ""
echo "Tinyproxy running on port $LISTEN_PORT"
echo "Allowed VPC Range: $VPC_CIDR"
echo ""
