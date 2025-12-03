d#!/bin/bash
# Commands to run in Krystal jailshell to diagnose SSH blocking issue

echo "=== 1. Check if your IP is in fail2ban jail ==="
echo "sudo fail2ban-client status sshd"
echo ""

echo "=== 2. List all banned IPs ==="
echo "sudo fail2ban-client get sshd banip"
echo ""

echo "=== 3. Check recent SSH auth failures ==="
echo "sudo grep 'Failed password' /var/log/auth.log | tail -20"
echo ""

echo "=== 4. Check SSH connection attempts from your IP ==="
echo "# Replace YOUR_IP with your actual IP"
echo "sudo grep 'YOUR_IP' /var/log/auth.log | tail -20"
echo ""

echo "=== 5. Check current SSH connections ==="
echo "who"
echo ""

echo "=== 6. Check sshd status ==="
echo "sudo systemctl status sshd"
echo ""

echo "=== 7. If jailshell doesn't allow sudo, try these ==="
echo "# Check home directory for .ssh/authorized_keys"
echo "cat ~/.ssh/authorized_keys"
echo ""
echo "# Check if there are connection logs in home"
echo "ls -la ~/ | grep -i log"
echo ""

echo "=== 8. To unban your IP (if you find it's banned) ==="
echo "# Get your current IP first from local machine:"
echo "curl -s ifconfig.me"
echo ""
echo "# Then on Krystal shell:"
echo "sudo fail2ban-client set sshd unbanip YOUR_IP"
