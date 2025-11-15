#!/bin/bash
# NAT + High-Concurrency HTTP CONNECT Proxy (Squid)
# Supports VPC CIDR + listen port input

# If using k8s, the NAT_VP_CIDR is likely specific to the cluster

set -e

usage() {
  echo "Usage: $0 [-c NAT_VPC_CIDR] [-p NAT_LISTEN_PORT]"
  exit 1
}

# Reset variables so the script ALWAYS prompts if not provided
unset NAT_VPC_CIDR
unset NAT_LISTEN_PORT

while getopts ":c:p:" opt; do
  case "${opt}" in
    c) NAT_VPC_CIDR="${OPTARG}" ;;
    p) NAT_LISTEN_PORT="${OPTARG}" ;;
    *) usage ;;
  esac
done

if [ -z "$NAT_VPC_CIDR" ]; then
  read -rp "Enter VPC CIDR block (e.g., 10.124.0.0/16): " NAT_VPC_CIDR
fi

if [ -z "$NAT_LISTEN_PORT" ]; then
  read -rp "Enter Proxy Listen Port (e.g., 8888): " NAT_LISTEN_PORT
fi

echo "Using NAT_VPC_CIDR: $NAT_VPC_CIDR"
echo "Using NAT_LISTEN_PORT: $NAT_LISTEN_PORT"
echo ""

echo "[1/7] Updating system..."
apt update -y
apt install -y squid iptables-persistent curl

echo "[2/7] Loading conntrack kernel modules..."
modprobe nf_conntrack
modprobe nf_conntrack_ipv4 || true
modprobe xt_conntrack || true

echo "[3/7] Applying sysctl tuning..."
cat <<EOF >> /etc/sysctl.conf

# NAT proxy performance tuning
net.ipv4.ip_forward = 1
net.ipv4.ip_local_port_range = 15000 65000

# Increase conntrack table
net.netfilter.nf_conntrack_max = 262144

# Faster TIME_WAIT cleanup
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_tw_reuse = 1

# Increase FD limits
fs.file-max = 500000
EOF

sysctl -p

echo "[4/7] Configuring Squid..."
mv /etc/squid/squid.conf /etc/squid/squid.conf.bak

cat <<EOF > /etc/squid/squid.conf
# ================== Squid CONNECT Proxy ==================

# Listen on custom port
http_port $NAT_LISTEN_PORT

# Allow HTTPS CONNECT only
acl SSL_ports port 443
acl CONNECT method CONNECT
http_access allow CONNECT SSL_ports

# Allow VPC CIDR
acl vpc src $NAT_VPC_CIDR
http_access allow vpc

# Deny all other access
http_access deny all

# No caching (Chrome-friendly)
cache deny all
memory_pools off
cache_mem 16 MB

# FD scaling
max_filedescriptors 65535

workers 1

# No disk cache
cache_dir null /tmp

access_log /var/log/squid/access.log
cache_log /var/log/squid/cache.log
EOF

echo "[5/7] Restarting Squid..."
systemctl restart squid
systemctl enable squid

echo "[6/7] Setting up iptables NAT..."
iptables -t nat -F
iptables -A FORWARD -s "$NAT_VPC_CIDR" -j ACCEPT
iptables -t nat -A POSTROUTING -s "$NAT_VPC_CIDR" -o eth0 -j MASQUERADE

netfilter-persistent save
netfilter-persistent reload

echo "[7/7] Completed!"
echo ""
echo "Squid CONNECT proxy active on port: $NAT_LISTEN_PORT"
echo "Allowed VPC range: $NAT_VPC_CIDR"
echo ""
echo "Test from a worker:"
echo "  curl -x http://<NAT_IP>:$NAT_LISTEN_PORT https://google.com -I"
