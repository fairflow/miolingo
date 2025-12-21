"""Remote storage utilities for user-uploaded materials.

Handles SSH-based file uploads to the server for user-contributed content.
Uses existing SSH tunnel credentials from session state.
"""

import paramiko
from io import StringIO
import streamlit as st
from pathlib import Path
import logging


def get_ssh_client():
    """Create SSH client using credentials from st.secrets."""
    ssh_config = st.secrets['ssh']
    
    # Parse SSH key from content
    key_content = ssh_config['key_content']
    key_file = StringIO(key_content)
    
    # Try to load the key
    ssh_key = None
    for key_class in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
        try:
            key_file.seek(0)
            ssh_key = key_class.from_private_key(key_file)
            break
        except:
            continue
    
    if not ssh_key:
        raise ValueError("Failed to load SSH key")
    
    # Connect via SSH
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    client.connect(
        hostname=ssh_config['host'],
        port=ssh_config['port'],
        username=ssh_config['username'],
        pkey=ssh_key,
        timeout=10
    )
    
    return client


def save_user_material(content: str, filename: str, language: str, username: str) -> dict:
    """Save user-uploaded material to remote server.
    
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
    
    # Construct remote path
    remote_dir = f"~/miolingo.io/public_ftp/incoming/{language}/{username}"
    remote_path = f"{remote_dir}/{safe_filename}"
    
    try:
        client = get_ssh_client()
        
        # Create directory structure
        stdin, stdout, stderr = client.exec_command(f'mkdir -p {remote_dir}')
        stdout.read()  # Wait for completion
        err = stderr.read().decode()
        if err and 'exists' not in err.lower():
            raise Exception(f"Failed to create directory: {err}")
        
        # Check file size (limit to 1MB for now)
        content_bytes = content.encode('utf-8')
        if len(content_bytes) > 1_000_000:
            client.close()
            return {
                'success': False,
                'path': None,
                'error': 'File too large (max 1MB)'
            }
        
        # Use SFTP to write file
        sftp = client.open_sftp()
        with sftp.open(remote_path, 'w') as f:
            f.write(content)
        sftp.close()
        
        # Verify upload
        stdin, stdout, stderr = client.exec_command(f'ls -lh {remote_path}')
        verification = stdout.read().decode().strip()
        
        client.close()
        
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
        
    Returns:
        dict with 'used_bytes', 'file_count', 'quota_bytes'
    """
    # For now, simple implementation - just count files
    # TODO: Implement proper quota tracking in database
    try:
        client = get_ssh_client()
        
        # Count files and total size for this user across all languages
        cmd = f'find ~/miolingo.io/public_ftp/incoming/*/"{username}" -type f -exec wc -c {{}} + 2>/dev/null | tail -1'
        stdin, stdout, stderr = client.exec_command(cmd)
        output = stdout.read().decode().strip()
        
        client.close()
        
        if output:
            parts = output.split()
            total_bytes = int(parts[0]) if parts else 0
        else:
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
