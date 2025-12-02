#!/usr/bin/env python3
"""
Check how many SSH connections we currently have open to Krystal server.
This helps diagnose if we're hitting connection limits.
"""

import subprocess
import sys

print("🔍 Checking SSH connections to Krystal...")
print("=" * 70)

# Check local processes
try:
    # Find Python processes that might have SSH tunnels
    result = subprocess.run(
        ["ps", "aux"],
        capture_output=True,
        text=True
    )
    
    lines = result.stdout.split('\n')
    
    # Count Streamlit processes
    streamlit_count = 0
    streamlit_pids = []
    
    for line in lines:
        if 'streamlit' in line.lower() and 'grep' not in line:
            streamlit_count += 1
            parts = line.split()
            if len(parts) > 1:
                streamlit_pids.append(parts[1])
    
    print(f"\n📊 Local Streamlit processes: {streamlit_count}")
    if streamlit_pids:
        print(f"   PIDs: {', '.join(streamlit_pids)}")
    
    # Check for active network connections to port 722
    print(f"\n🌐 Checking active network connections to port 722...")
    
    result = subprocess.run(
        ["lsof", "-i", "TCP:722"],
        capture_output=True,
        text=True
    )
    
    connections = [line for line in result.stdout.split('\n') if line and 'COMMAND' not in line]
    
    if connections:
        print(f"   Found {len(connections)} active SSH connection(s):")
        for conn in connections:
            print(f"   {conn}")
    else:
        print(f"   ✅ No active local SSH connections to port 722")
    
    # Try to SSH and check active connections on server
    print(f"\n🔐 Attempting to check server-side connections...")
    print(f"   (This requires SSH access and may not work with jailed shell)")
    
    # This command attempts to show connections to MySQL port from the server side
    ssh_command = [
        "ssh",
        "-p", "722",
        "-o", "ConnectTimeout=5",
        "-o", "StrictHostKeyChecking=no",
        "fairtlou@miolingo.io",
        "netstat -an | grep :3306 | wc -l"
    ]
    
    try:
        result = subprocess.run(
            ssh_command,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            count = result.stdout.strip()
            print(f"   Server-side MySQL connections: {count}")
        else:
            print(f"   ⚠️  Cannot access server-side info (jailed shell)")
    except subprocess.TimeoutExpired:
        print(f"   ⚠️  SSH command timed out")
    except Exception as e:
        print(f"   ⚠️  Cannot check server-side: {e}")

except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

print("\n" + "=" * 70)
print("✅ Diagnostic complete")
print("\n💡 Tips:")
print("   - Each Streamlit process can create 1 SSH tunnel")
print("   - SSH tunnels should auto-cleanup when process exits")
print("   - If you see many stale processes, restart them cleanly")
print("   - Ask Krystal support what their per-user SSH connection limit is")
