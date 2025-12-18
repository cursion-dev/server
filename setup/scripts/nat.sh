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

# update and install deps
echo "[1/8] Updating system..."
apt update -y
apt install -y squid iptables-persistent curl

# load conntrack
echo "[2/8] Loading conntrack kernel modules..."
modprobe nf_conntrack
modprobe xt_conntrack || true

# adding sysctl tunning
if ! grep -q "NAT_PROXY_TUNING" /etc/sysctl.conf; then
echo "[3/8] Applying sysctl tuning..."
cat <<EOF >> /etc/sysctl.conf
# === NAT_PROXY_TUNING ===

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

# === END NAT_PROXY_TUNING ===
EOF
fi

sysctl -p

echo "[4/8] Configuring Squid..."
mv /etc/squid/squid.conf /etc/squid/squid.conf.bak

cat <<EOF > /etc/squid/squid.conf
# ================== Squid CONNECT Proxy ==================

# Prevent Squid from restarting under burst load
shutdown_lifetime 3 seconds

# Listen on custom port
http_port ${NAT_LISTEN_PORT}

# Allow HTTPS CONNECT only
acl SSL_ports port 443
acl CONNECT method CONNECT
http_access allow CONNECT SSL_ports

# Large CONNECT tunnels
request_header_max_size 64 KB
reply_header_max_size 64 KB

# Avoid connection pooling exhaustion
server_persistent_connections off

# Allow persistent connections from clients
client_persistent_connections on

# Disable request pipelining
pipeline_prefetch 0

# Allow VPC CIDR
acl vpc src ${NAT_VPC_CIDR}
http_access allow vpc

# Deny all other access
http_access deny all

# Memory Safety (1 GiB RAM)
cache deny all
memory_pools off

# Hard memory caps
cache_mem 64 MB
maximum_object_size_in_memory 32 KB

# Limit per-connection buffers
client_request_buffer_max_size 64 KB
request_body_max_size 0 KB

# FD scaling
max_filedescriptors 65535

workers 1

# NOTE: no cache_dir — means "no cache"
# (Null cache type is not supported in Ubuntu 24.04 build)

access_log /var/log/squid/access.log
cache_log /var/log/squid/cache.log
EOF

echo "[5/8] Adding systemd NOFILE limit..."
mkdir -p /etc/systemd/system/squid.service.d

cat <<EOF > /etc/systemd/system/squid.service.d/limits.conf
[Service]
LimitNOFILE=65535
EOF

# restarts squid on OOM failure
cat <<EOF > /etc/systemd/system/squid.service.d/oom.conf
[Service]
OOMScoreAdjust=-900
Restart=always
RestartSec=2
EOF

# adding memory swap 
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 1G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# update squid dameon
systemctl daemon-reexec
systemctl daemon-reload

# avoids silent failures
squid -k parse

# restart squid
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