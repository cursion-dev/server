#!/bin/bash
# NAT + High-Concurrency HTTP CONNECT Proxy (Squid)
# Supports VPC CIDR + listen port input

# If using k8s, the NAT_VP_CIDR is likely specific to the cluster


set -u # Treat unset variables as errors


# ===========================
# Positional arguments
# ===========================

NAT_VPC_CIDR="${1:-}"
NAT_LISTEN_PORT="${2:-}"

if [ -z "$NAT_VPC_CIDR" ]; then
  read -rp "Enter VPC CIDR block (e.g., 10.124.0.0/16): " NAT_VPC_CIDR
fi

if [ -z "$NAT_LISTEN_PORT" ]; then
  read -rp "Enter Proxy Listen Port (e.g., 8888): " NAT_LISTEN_PORT
fi

echo "Using NAT_VPC_CIDR: $NAT_VPC_CIDR"
echo "Using NAT_LISTEN_PORT: $NAT_LISTEN_PORT"
echo ""

echo "[1/8] Updating system..."
apt update -y
apt install -y squid iptables-persistent curl

echo "[2/8] Loading conntrack kernel modules..."
modprobe nf_conntrack
modprobe xt_conntrack || true

echo "[3/8] Applying sysctl tuning..."
cat <<EOF >> /etc/sysctl.conf

# TCP backlog & performance
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 250000

# Orphan sockets
net.ipv4.tcp_max_orphans = 16384

# SYN backlog
net.ipv4.tcp_max_syn_backlog = 16384

# NAT proxy performance
net.ipv4.ip_forward = 1
net.ipv4.ip_local_port_range = 15000 65000

# Conntrack table
net.netfilter.nf_conntrack_max = 262144

# TIME_WAIT cleanup
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_tw_reuse = 1

# File descriptors
fs.file-max = 500000
EOF

sysctl -p

echo "[4/8] Configuring Squid..."
mv /etc/squid/squid.conf /etc/squid/squid.conf.bak

cat <<EOF > /etc/squid/squid.conf
# ================== Squid CONNECT Proxy ==================

shutdown_lifetime 3 seconds
dns_v4_first on

http_port $NAT_LISTEN_PORT

acl SSL_ports port 443
acl CONNECT method CONNECT
http_access allow CONNECT SSL_ports

# Large CONNECT tunnels
request_header_max_size 64 KB
reply_header_max_size 64 KB

# Avoid connection pooling exhaustion
server_persistent_connections off
client_persistent_connections on

# Outbound sockets per worker
maxconn 5000

# Disable request pipelining
pipeline_prefetch off

# Allow VPC CIDR
acl vpc src $NAT_VPC_CIDR
http_access allow vpc

# Deny all others
http_access deny all

# No caching
cache deny all
memory_pools off
cache_mem 16 MB

# FD scaling
max_filedescriptors 65535

workers 1

cache_dir null /tmp

access_log /var/log/squid/access.log
cache_log /var/log/squid/cache.log
EOF

echo "[5/8] Adding systemd NOFILE limit..."
mkdir -p /etc/systemd/system/squid.service.d

cat <<EOF > /etc/systemd/system/squid.service.d/limits.conf
[Service]
LimitNOFILE=65535
EOF

systemctl daemon-reload

echo "[6/8] Restarting Squid..."
systemctl restart squid
systemctl enable squid

echo "[7/8] Setting up iptables NAT..."
iptables -t nat -F
iptables -A FORWARD -s "$NAT_VPC_CIDR" -j ACCEPT
iptables -t nat -A POSTROUTING -s "$NAT_VPC_CIDR" -o eth0 -j MASQUERADE

netfilter-persistent save
netfilter-persistent reload

echo "[8/8] Completed!"
echo ""
echo "Squid CONNECT proxy active on port: $NAT_LISTEN_PORT"
echo "Allowed VPC range: $NAT_VPC_CIDR"
echo ""
echo "Test with:"
echo "  curl -x http://<NAT_IP>:$NAT_LISTEN_PORT https://google.com -I"