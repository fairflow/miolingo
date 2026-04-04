#!/usr/bin/env python3
"""
Clean Restart Script for Streamlit Apps
Handles graceful shutdown and restart with proper cleanup

Usage:
    python scripts/clean_restart.py app          # Restart in headless mode (reuse tab)
    python scripts/clean_restart.py admin        # Restart admin on 8502
    python scripts/clean_restart.py monitor      # Restart connection_monitor on 8503
    python scripts/clean_restart.py all          # Restart all apps
    
    python scripts/clean_restart.py monitor -c   # Open new browser tab
    python scripts/clean_restart.py monitor --clean  # Same as -c

Features:
- Kills existing processes gracefully (SIGTERM first, then SIGKILL)
- Frees up ports if stuck
- Activates virtualenv automatically
- Waits for clean shutdown before restart
- Reports status and errors

Default behavior (headless mode):
- Server runs without opening new tab
- Existing browser tabs will reconnect automatically
- Avoids multiple tab proliferation

With --clean/-c flag:
- Opens a new browser tab
- Use when original tab is closed or you want a fresh tab

Author: Miolingo Team
Version: 0.2
"""

import sys
import subprocess
import time
import signal
from pathlib import Path
from typing import Optional, List

# App configurations
APPS = {
    'app': {
        'script': 'src/app.py',
        'port': 8501,
        'name': 'Miolingo App'
    },
    'admin': {
        'script': 'src/miolingo-admin.py',
        'port': 8502,
        'name': 'Admin Dashboard'
    },
    'monitor': {
        'script': 'src/connection_monitor.py',
        'port': 8503,
        'name': 'Connection Monitor'
    }
}


def get_workspace_root() -> Path:
    """
    Find the workspace root (directory containing the project files).

    Works in both the main repo and git worktrees. The venv may live in
    the main repo rather than the worktree, so we don't require venv/
    to exist here — we just need the directory that has src/ and scripts/.
    """
    current = Path(__file__).resolve().parent.parent
    if (current / 'src').exists():
        return current
    raise RuntimeError("Could not find workspace root (no src/ directory)")


def find_process_by_script(script_name: str) -> List[int]:
    """Find PIDs of processes running the given script"""
    try:
        result = subprocess.run(
            ['pgrep', '-f', f'streamlit run {script_name}'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return [int(pid) for pid in result.stdout.strip().split('\n') if pid]
        return []
    except Exception as e:
        print(f"Warning: Error finding process: {e}")
        return []


def find_process_on_port(port: int) -> List[int]:
    """Find PIDs using the given port"""
    try:
        result = subprocess.run(
            ['lsof', '-ti', f':{port}'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return [int(pid) for pid in result.stdout.strip().split('\n') if pid]
        return []
    except Exception as e:
        print(f"Warning: Error finding port usage: {e}")
        return []


def kill_process(pid: int, timeout: int = 5) -> bool:
    """
    Kill process gracefully (SIGTERM), then forcefully (SIGKILL) if needed
    Returns True if process was killed
    """
    try:
        # Check if process exists
        subprocess.run(['kill', '-0', str(pid)], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        # Process doesn't exist
        return False
    
    print(f"  Sending SIGTERM to PID {pid}...")
    try:
        subprocess.run(['kill', '-TERM', str(pid)], check=True)
        
        # Wait for graceful shutdown
        for i in range(timeout):
            try:
                subprocess.run(['kill', '-0', str(pid)], check=True, capture_output=True)
                time.sleep(1)
            except subprocess.CalledProcessError:
                print(f"  ✓ Process {pid} terminated gracefully")
                return True
        
        # Still alive - force kill
        print(f"  Process {pid} didn't die gracefully, forcing SIGKILL...")
        subprocess.run(['kill', '-KILL', str(pid)], check=True)
        time.sleep(0.5)
        print(f"  ✓ Process {pid} killed forcefully")
        return True
        
    except Exception as e:
        print(f"  Warning: Error killing process {pid}: {e}")
        return False


def free_port(port: int) -> bool:
    """Free up a port by killing processes using it"""
    pids = find_process_on_port(port)
    if not pids:
        return True
    
    print(f"  Port {port} in use by PIDs: {pids}")
    for pid in pids:
        kill_process(pid)
    
    # Verify port is free
    time.sleep(0.5)
    remaining = find_process_on_port(port)
    if remaining:
        print(f"  ⚠️  Port {port} still in use by: {remaining}")
        return False
    
    print(f"  ✓ Port {port} freed")
    return True


def start_app(app_key: str, workspace: Path, open_browser: bool = False) -> bool:
    """
    Start a Streamlit app
    
    Args:
        app_key: Which app to start (app/admin/monitor)
        workspace: Path to workspace root
        open_browser: If True, open new browser tab. If False, run headless (default)
    """
    config = APPS[app_key]
    script = config['script']
    port = config['port']
    name = config['name']
    
    print(f"\n▶️  Starting {name} on port {port}...")
    
    # Build command — use the streamlit from the active venv (already on PATH
    # if venv is activated), or fall back to looking in workspace/venv/.
    import shutil
    venv_streamlit = shutil.which('streamlit')
    if not venv_streamlit:
        # Try explicit venv path (main repo, not worktree)
        for candidate in [workspace / 'venv' / 'bin' / 'streamlit',
                          workspace / '.venv' / 'bin' / 'streamlit']:
            if candidate.exists():
                venv_streamlit = str(candidate)
                break
    if not venv_streamlit:
        print(f"  ❌ Streamlit not found. Activate venv or install streamlit.")
        return False

    cmd = [str(venv_streamlit), 'run', script, '--server.port', str(port)]
    if not open_browser:
        cmd.append('--server.headless=true')
    
    try:
        # Start in background
        process = subprocess.Popen(
            cmd,
            cwd=str(workspace),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True  # Detach from parent
        )
        
        # Wait a moment to check if it started successfully
        time.sleep(2)
        
        if process.poll() is not None:
            # Process died immediately
            stdout, stderr = process.communicate()
            print(f"  ❌ Failed to start (exit code {process.returncode})")
            if stderr:
                print(f"  Error: {stderr.decode()[:200]}")
            return False
        
        print(f"  ✓ Started with PID {process.pid}")
        print(f"  🌐 Access at: http://localhost:{port}")
        
        if open_browser:
            print(f"  📋 New browser tab will open automatically")
            print(f"  ⚠️  Note: This may create multiple tabs if old one reconnects")
        else:
            print(f"  🔄 Running in headless mode - existing tabs will reconnect")
            print(f"  💡 Use --clean flag to open a new browser tab instead")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error starting {name}: {e}")
        return False


def restart_app(app_key: str, open_browser: bool = False) -> bool:
    """
    Restart a single app with full cleanup
    
    Args:
        app_key: Which app to restart
        open_browser: If True, open new browser tab. If False, run headless (default)
    """
    if app_key not in APPS:
        print(f"❌ Unknown app: {app_key}")
        print(f"Available: {', '.join(APPS.keys())}")
        return False
    
    config = APPS[app_key]
    name = config['name']
    script = config['script']
    port = config['port']
    
    print(f"\n{'='*60}")
    print(f"🔄 Restarting: {name}")
    print(f"{'='*60}")
    
    # Find workspace root
    try:
        workspace = get_workspace_root()
        print(f"📁 Workspace: {workspace}")
    except RuntimeError as e:
        print(f"❌ {e}")
        return False
    
    # Step 1: Kill existing processes
    print(f"\n🛑 Stopping existing processes...")
    pids = find_process_by_script(script)
    if pids:
        print(f"  Found {len(pids)} process(es): {pids}")
        for pid in pids:
            kill_process(pid)
    else:
        print(f"  No existing processes found")
    
    # Step 2: Free port
    print(f"\n🔓 Freeing port {port}...")
    if not free_port(port):
        print(f"  ⚠️  Port may still be in use, attempting to start anyway...")
    
    # Step 3: Start app
    success = start_app(app_key, workspace, open_browser)
    
    if success:
        print(f"\n✅ {name} restarted successfully!")
    else:
        print(f"\n❌ Failed to restart {name}")
    
    return success


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    target = sys.argv[1].lower()
    
    # Check for --clean/-c flag (opens new browser tab)
    # Default is headless mode (existing tabs reconnect)
    open_browser = '--clean' in sys.argv or '-c' in sys.argv
    
    if target == 'all':
        print("\n🔄 Restarting all apps...")
        if open_browser:
            print("  📋 Mode: Opening new browser tabs")
        else:
            print("  🔄 Mode: Headless (existing tabs will reconnect)")
        
        results = {}
        for app_key in APPS.keys():
            results[app_key] = restart_app(app_key, open_browser)
        
        print(f"\n{'='*60}")
        print("📊 Summary:")
        print(f"{'='*60}")
        for app_key, success in results.items():
            status = "✅" if success else "❌"
            print(f"  {status} {APPS[app_key]['name']}")
        
        # Exit with error if any failed
        if not all(results.values()):
            sys.exit(1)
    
    elif target in APPS:
        success = restart_app(target, open_browser)
        sys.exit(0 if success else 1)
    
    else:
        print(f"❌ Unknown target: {target}")
        print(f"Available: {', '.join(APPS.keys())}, all")
        print(f"\nUsage: python scripts/clean_restart.py [app|admin|monitor|all] [-c|--clean]")
        print(f"  Default: Headless mode (existing tabs reconnect)")
        print(f"  --clean: Open new browser tab")
        sys.exit(1)


if __name__ == '__main__':
    main()
