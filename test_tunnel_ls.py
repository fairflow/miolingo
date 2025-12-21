"""Quick test to verify ssh_tunnel in session state works for SSH commands."""

import streamlit as st
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from remote_storage import execute_ssh_command
from connection_pool import ConnectionPool

def ensure_tunnel():
    """Ensure tunnel exists in session state."""
    if 'ssh_tunnel' not in st.session_state:
        st.info("Creating tunnel directly for test...")
        try:
            secrets_config = {
                'ssh': dict(st.secrets["ssh"]),
                'mysql': dict(st.secrets["mysql"])
            }
            pool = ConnectionPool(secrets_config)
            tunnel = pool.create_ssh_tunnel()
            st.session_state['ssh_tunnel'] = tunnel
            st.success(f"✓ Tunnel created and stored: port {tunnel.local_bind_port}")
        except Exception as e:
            st.error(f"❌ Failed to create tunnel: {e}")
            import traceback
            st.code(traceback.format_exc())
            return False
    return True

def test_tunnel_ls():
    """Test that we can run ls command through session tunnel."""
    
    if not ensure_tunnel():
        return False
    
    tunnel = st.session_state.get('ssh_tunnel')
    st.info(f"✓ Tunnel in session state (port {tunnel.local_bind_port})")
    
    try:
        st.info("Running: ls -la ~")
        stdout, stderr, success = execute_ssh_command('ls -la ~')
        
        if success:
            st.success("✅ SSH ls command successful!")
            st.code(stdout[:500], language="text")
            return True
        else:
            st.error(f"❌ SSH command failed")
            st.code(f"stderr: {stderr}", language="text")
            return False
            
    except Exception as e:
        st.error(f"❌ Exception during SSH command: {e}")
        import traceback
        st.code(traceback.format_exc())
        return False

def test_touch_file():
    """Test creating a file via touch in user directory."""
    
    if not ensure_tunnel():
        return False
    
    # Test username and language
    username = "testuser"
    language = "fr"
    test_dir = f"~/miolingo.io/public_ftp/incoming/{language}/{username}"
    test_file = f"{test_dir}/test_touch.txt"
    
    st.info(f"Testing file creation at: {test_file}")
    
    try:
        # First, show where ~ actually expands to
        st.info("Step 0: Checking home directory and SSH user")
        cmd0 = "echo $HOME && whoami"
        stdout0, stderr0, success0 = execute_ssh_command(cmd0)
        if success0:
            st.code(f"Home: {stdout0.strip()}", language="text")
        
        # Create directory (mkdir -p handles existing dirs)
        st.info(f"Step 1: Creating directory with mkdir -p")
        cmd1 = f"mkdir -p {test_dir}"
        stdout1, stderr1, success1 = execute_ssh_command(cmd1)
        
        if not success1:
            st.error(f"❌ mkdir failed: {stderr1}")
            return False
        st.success("✓ Directory created/verified")
        
        # Touch the file
        st.info(f"Step 2: Creating empty file with touch")
        cmd2 = f"touch {test_file}"
        stdout2, stderr2, success2 = execute_ssh_command(cmd2)
        
        if not success2:
            st.error(f"❌ touch failed: {stderr2}")
            return False
        st.success("✓ File touched")
        
        # Verify file exists with absolute path
        st.info(f"Step 3: Verifying file (with absolute path)")
        cmd3 = f"ls -lh {test_file} && realpath {test_file}"
        stdout3, stderr3, success3 = execute_ssh_command(cmd3)
        
        if success3:
            st.success("✅ File created and verified!")
            st.code(stdout3, language="text")
            return True
        else:
            st.error(f"❌ Verification failed: {stderr3}")
            return False
            
    except Exception as e:
        st.error(f"❌ Exception: {e}")
        import traceback
        st.code(traceback.format_exc())
        return False


if __name__ == "__main__":
    st.title("Tunnel Test - File Operations")
    
    st.info(f"Session state keys: {list(st.session_state.keys())}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Test SSH ls"):
            test_tunnel_ls()
    
    with col2:
        if st.button("Test touch file"):
            test_touch_file()
