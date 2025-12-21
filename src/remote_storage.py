"""Remote storage utilities for user-uploaded materials.

Handles SSH-based file uploads to the server for user-contributed content.
CRITICAL: Reuses existing SSH tunnel's transport - does NOT create new connections.
"""

import streamlit as st
import logging


def execute_ssh_command(command: str) -> tuple:
    """Execute SSH command using the session's tunnel transport.
    
    Args:
        command: Shell command to execute
        
    Returns:
        tuple: (stdout, stderr, success)
    """
    import streamlit as st
    
    try:
        # Ensure tunnel exists in session state (copied from test_tunnel_ls.py)
        if 'ssh_tunnel' not in st.session_state:
            # Create tunnel directly
            from connection_pool import ConnectionPool
            secrets_config = {
                'ssh': dict(st.secrets["ssh"]),
                'mysql': dict(st.secrets["mysql"])
            }
            pool = ConnectionPool(secrets_config)
            tunnel = pool.create_ssh_tunnel()
            st.session_state['ssh_tunnel'] = tunnel
            logging.info(f"Created tunnel and stored in session state: port {tunnel.local_bind_port}")
        
        # Get the tunnel directly from session state
        tunnel = st.session_state.get('ssh_tunnel')
        
        if not tunnel:
            raise ValueError("No tunnel available for this session")
        
        # Use the tunnel's existing SSH transport
        if not hasattr(tunnel, '_transport') or not tunnel._transport:
            raise ValueError("Tunnel transport not available")
        
        transport = tunnel._transport
        
        # Verify transport is active
        if not transport.is_active():
            raise ValueError("SSH transport is not active")
        
        # Open a new channel on the existing transport for command execution
        channel = transport.open_session()
        channel.set_combine_stderr(True)  # Combine stderr with stdout
        channel.exec_command(command)
        
        # Read output with timeout
        channel.settimeout(30.0)
        stdout_text = ""
        while True:
            if channel.recv_ready():
                chunk = channel.recv(4096).decode('utf-8', errors='replace')
                if not chunk:
                    break
                stdout_text += chunk
            if channel.exit_status_ready():
                break
        
        stderr_text = ""
        if channel.recv_stderr_ready():
            stderr_text = channel.recv_stderr(4096).decode('utf-8', errors='replace')
        
        exit_status = channel.recv_exit_status()
        channel.close()
        
        success = exit_status == 0
        
        if not success:
            logging.error(f"SSH command failed (exit={exit_status}): {command[:100]}")
            logging.error(f"stdout: {stdout_text[:500]}")
            logging.error(f"stderr: {stderr_text[:500]}")
        
        return stdout_text, stderr_text, success
        
    except Exception as e:
        logging.error(f"SSH command exception: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return "", str(e), False


def save_user_material(content: str, filename: str, language: str, username: str) -> dict:
    """Save user-uploaded material to remote server.
    
    IMPORTANT: Uses existing session tunnel - does not create new connections.
    
    Args:
        content: File content as string
        filename: Desired filename (will be sanitized)
        language: Language code (fr, de, pt, etc.)
        username: User's username for directory structure
        
    Returns:
        dict with 'success' (bool), 'path' (str), 'error' (str)
    """
    # Sanitize filename - only allow alphanumeric, dash, underscore, dot
    safe_filename = "".join(c for c in filename if c.isalnum() or c in '.-_')
    if not safe_filename.endswith('.txt'):
        safe_filename += '.txt'
    
    # Construct remote path: incoming/{username}/{language_code}/
    remote_dir = f"~/miolingo.io/public_ftp/incoming/{username}/{language}"
    remote_path = f"{remote_dir}/{safe_filename}"
    
    try:
        # Check file size (limit to 1MB for now)
        content_bytes = content.encode('utf-8')
        if len(content_bytes) > 1_000_000:
            return {
                'success': False,
                'path': None,
                'error': 'File too large (max 1MB)'
            }
        
        # Test SSH connection first
        test_stdout, test_stderr, test_success = execute_ssh_command('pwd')
        if not test_success:
            raise Exception(f"SSH test failed - pwd command: {test_stderr}")
        logging.info(f"SSH test passed - pwd returned: {test_stdout.strip()}")
        
        # Create directory structure using existing tunnel
        stdout, stderr, success = execute_ssh_command(f'mkdir -p {remote_dir}')
        if not success and 'exists' not in stderr.lower():
            raise Exception(f"Failed to create directory: {stderr}")
        
        logging.info(f"Directory created/verified: {remote_dir}")
        
        # Write file using SSH command (alternative to SFTP)
        # Escape content for safe shell transmission
        escaped_content = content.replace("'", "'\\''")
        cmd = f"cat > {remote_path} << 'MIOLINGO_EOF'\n{escaped_content}\nMIOLINGO_EOF"
        stdout, stderr, success = execute_ssh_command(cmd)
        
        if not success:
            raise Exception(f"Failed to write file: {stderr}")
        
        logging.info(f"File written to: {remote_path}")
        
        # Verify upload
        stdout, stderr, success = execute_ssh_command(f'ls -lh {remote_path}')
        verification = stdout.strip()
        
        logging.info(f"User material uploaded: {remote_path}")
        
        return {
            'success': True,
            'path': remote_path,
            'error': None,
            'verification': verification
        }
        
    except Exception as e:
        logging.error(f"Failed to upload user material: {e}")
        return {
            'success': False,
            'path': None,
            'error': str(e)
        }


def get_user_quota(username: str) -> dict:
    """Get user's upload quota information.
    
    Args:
        username: User's username
    Uses existing session tunnel - does not create new connections.
    
    Args:
        username: User's username
        
    Returns:
        dict with 'used_bytes', 'file_count', 'quota_bytes'
    """
    # For now, simple implementation - just count files
    # TODO: Implement proper quota tracking in database
    try:
        # Count files and total size for this user across all languages
        cmd = f'find ~/miolingo.io/public_ftp/incoming/*/"{username}" -type f -exec wc -c {{}} + 2>/dev/null | tail -1'
        stdout, stderr, success = execute_ssh_command(cmd)
        
        total_bytes = 0
        if success and stdout.strip():
            parts = stdout.strip().split()
            if parts:
                try:
                    total_bytes = int(parts[0])
                except (ValueError, IndexError):
                    total_bytes = 0
        
        # Default quota: 10MB per user
        quota_bytes = 10_000_000
        
        return {
            'used_bytes': total_bytes,
            'quota_bytes': quota_bytes,
            'remaining_bytes': max(0, quota_bytes - total_bytes),
            'used_mb': round(total_bytes / 1_000_000, 2),
            'quota_mb': round(quota_bytes / 1_000_000, 2)
        }
        
    except Exception as e:
        logging.error(f"Failed to get user quota: {e}")
        return {
            'used_bytes': 0,
            'quota_bytes': 10_000_000,
            'remaining_bytes': 10_000_000,
            'used_mb': 0,
            'quota_mb': 10
        }
