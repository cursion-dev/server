#!/bin/bash
# NAT + High-Concurrency HTTP CONNECT Proxy (Squid)
# Supports VPC CIDR + listen port input

# NAT_VPC_CIDR is the VPC where k8s is located 
# https://cloud.digitalocean.com/networking/vpc/

set -u # Treat unset variables as errors

# ===========================
# Positional arguments
# ===========================

NAT_VPC_CIDR="${1:-}"
NAT_LISTEN_PORT="${2:-}"
NAT_PRIVATE_IP="${3:-}"

if [ -z "$NAT_VPC_CIDR" ]; then
  read -rp "Enter VPC CIDR block (e.g., 10.124.0.0/16): " NAT_VPC_CIDR
fi

if [ -z "$NAT_LISTEN_PORT" ]; then
  read -rp "Enter Proxy Listen Port (e.g., 8888): " NAT_LISTEN_PORT
fi

if [ -z "$NAT_PRIVATE_IP" ]; then
  read -rp "Enter NAT Private IP addres (e.g., 10.124.0.29): " NAT_PRIVATE_IP
fi

echo ""
echo "Using NAT_VPC_CIDR: $NAT_VPC_CIDR"
echo "Using NAT_LISTEN_PORT: $NAT_LISTEN_PORT"
echo "Using NAT_PRIVATE_IP: $NAT_PRIVATE_IP"
echo ""

# update and install deps
echo "[1/8] Updating system..."
apt update -y
apt install -y squid iptables-persistent curl conntrack

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

# NAT proxy performance
net.ipv4.ip_forward = 1
net.ipv4.ip_local_port_range = 15000 65000

# Conntrack table
net.netfilter.nf_conntrack_max = 262144

# TIME_WAIT cleanup
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_tw_reuse = 1

# limit SYNs calls
net.ipv4.tcp_syn_retries = 2
net.ipv4.tcp_synack_retries = 2
net.ipv4.tcp_max_syn_backlog = 4096
net.ipv4.tcp_abort_on_overflow = 1

# File descriptors
fs.file-max = 500000

# === END NAT_PROXY_TUNING ===
EOF
fi

sysctl -p

# setup Squid configs
echo "[4/8] Configuring Squid..."
mv /etc/squid/squid.conf /etc/squid/squid.conf.bak

cat <<EOF > /etc/squid/squid.conf
# ================== Squid CONNECT Proxy ==================

shutdown_lifetime 3 seconds

# Bind ONLY to private VPC IP (prevents public access)
http_port ${NAT_PRIVATE_IP}:${NAT_LISTEN_PORT}

# ---- ACCESS CONTROL (ORDER MATTERS) ----
acl vpc src ${NAT_VPC_CIDR}
acl SSL_ports port 443
acl CONNECT method CONNECT

http_access allow vpc CONNECT SSL_ports
http_access deny all

# ---- HARD BACKPRESSURE ----
acl max_clients maxconn 500
http_access deny max_clients
connect_retries 1

# Timeouts to kill abandoned tunnels
request_timeout 30 seconds
connect_timeout 5 seconds
read_timeout 30 seconds
client_lifetime 5 minutes
persistent_request_timeout 30 seconds
half_closed_clients off

# Headers / buffers
request_header_max_size 64 KB
reply_header_max_size 64 KB
client_request_buffer_max_size 96 KB
request_body_max_size 0 KB

# Connection behavior
server_persistent_connections off
client_persistent_connections off
pipeline_prefetch 0

# Memory safety
cache deny all
memory_pools off
cache_mem 64 MB
maximum_object_size_in_memory 32 KB

# FDs
max_filedescriptors 65535
workers 1

access_log /var/log/squid/access.log
cache_log /var/log/squid/cache.log
EOF

# restarts squid on OOM failure
cat <<EOF > /etc/systemd/system/squid.service.d/oom.conf
[Service]
OOMScoreAdjust=-900
Restart=on-failure
RestartSec=10
EOF

# adding memory swap
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 1G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# update squid daemon
systemctl daemon-reexec
systemctl daemon-reload

# avoids silent failures
squid -k parse

echo "[6/8] Setting up iptables NAT..."
iptables -t nat -F
iptables -A FORWARD -s "$NAT_VPC_CIDR" -j ACCEPT
iptables -t nat -A POSTROUTING -s "$NAT_VPC_CIDR" -o eth0 -j MASQUERADE

# default deny/lock-down
iptables -A INPUT -i lo -j ACCEPT
iptables -P INPUT DROP
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -p tcp --dport $NAT_LISTEN_PORT -s $NAT_VPC_CIDR -j ACCEPT
iptables -A INPUT -p tcp --dport 22 -j ACCEPT

netfilter-persistent save
netfilter-persistent reload

# flush existing abusive connections
conntrack -F

# restart squid
echo "[7/8] Restarting Squid..."
systemctl restart squid
systemctl enable squid

# success message
echo "[8/8] Completed!"
echo ""
echo "Squid CONNECT proxy active on port: $NAT_LISTEN_PORT"
echo "Allowed VPC range: $NAT_VPC_CIDR"
echo ""
