#!/bin/bash
# NAT + High-Concurrency HTTP CONNECT Proxy (Squid)
# Supports VPC CIDR + listen port input

# If using k8s, the VP_CIDR is likely specific to the cluster

set -e

usage() {
  echo "Usage: $0 [-c VPC_CIDR] [-p LISTEN_PORT]"
  exit 1
}

while getopts ":c:p:" opt; do
  case "${opt}" in
    c) VPC_CIDR="${OPTARG}" ;;
    p) LISTEN_PORT="${OPTARG}" ;;
    *) usage ;;
  esac
done

if [ -z "$VPC_CIDR" ]; then
  read -rp "Enter VPC CIDR block (e.g., 10.0.0.0/16): " VPC_CIDR
fi

if [ -z "$LISTEN_PORT" ]; then
  read -rp "Enter listen port (e.g., 8888): " LISTEN_PORT
fi

echo "Using VPC_CIDR: $VPC_CIDR"
echo "Using LISTEN_PORT: $LISTEN_PORT"
echo ""

echo "[1/7] Updating system..."
apt update -y
apt install -y squid iptables-persistent curl

echo "[2/7] Applying sysctl performance tuning..."

cat <<EOF >> /etc/sysctl.conf

# ---- NAT Proxy Performance ----
net.ipv4.ip_forward = 1

# Larger ephemeral port range
net.ipv4.ip_local_port_range = 15000 65000

# Larger conntrack table (default ~16k, we want 262k)
net.netfilter.nf_conntrack_max = 262144

# Faster TIME_WAIT cleanup
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_tw_recycle = 0

# Allow more open file descriptors
fs.file-max = 500000

EOF

sysctl -p

echo "[3/7] Configuring Squid as a CONNECT proxy..."

mv /etc/squid/squid.conf /etc/squid/squid.conf.bak

cat <<EOF > /etc/squid/squid.conf
# ============ Squid High-Concurrency Proxy ============

# Listen on custom port
http_port $LISTEN_PORT

# Only allow CONNECT tunneling (HTTPS proxy)
acl SSL_ports port 443
acl CONNECT method CONNECT
http_access allow CONNECT SSL_ports

# Allow VPC CIDR
acl vpc src $VPC_CIDR
http_access allow vpc

# Deny all else
http_access deny all

# ---- Performance Tuning ----

# Disable caching (faster, lower RAM)
cache deny all
memory_pools off
cache_mem 16 MB

# Increase concurrency capability
max_filedescriptors=65535

# Squid workers
workers 1

# Connection handling
tcp_outgoing_address 0.0.0.0
shutdown_lifetime 3 seconds

# No disk cache
cache_dir null /tmp

# Logging
access_log /var/log/squid/access.log
cache_log /var/log/squid/cache.log
EOF

echo "[4/7] Restarting Squid..."
systemctl restart squid
systemctl enable squid

echo "[5/7] Setting up IP forwarding..."
sysctl -w net.ipv4.ip_forward=1

echo "[6/7] Configuring iptables NAT fallback..."
iptables -t nat -F
iptables -A FORWARD -s "$VPC_CIDR" -j ACCEPT
iptables -t nat -A POSTROUTING -s "$VPC_CIDR" -o eth0 -j MASQUERADE

netfilter-persistent save
netfilter-persistent reload

echo "[7/7] Done!"

echo ""
echo "Squid CONNECT proxy running on port $LISTEN_PORT"
echo "Allowed VPC range: $VPC_CIDR"
echo ""
echo "You can test via:"
echo "  curl -x http://<NAT_IP>:$LISTEN_PORT https://google.com -I"
