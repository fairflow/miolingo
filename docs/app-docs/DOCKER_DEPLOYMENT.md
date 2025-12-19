# Docker Deployment Guide for Miolingo

**Version 6.4.0** | Last Updated: 19 December 2025

This guide explains how to run Miolingo using Docker for easy deployment and consistent environments.

---

## Quick Start (For Expert Users)

```bash
# 1. Pull the latest image from GitHub Container Registry
docker pull ghcr.io/fairflow/miolingo:latest

# 2. Create secrets file
mkdir -p .streamlit
cat > .streamlit/secrets.toml << 'EOF'
[ssh]
host = "your-ssh-server.com"
port = 22
username = "your_username"
key_content = """
-----BEGIN OPENSSH PRIVATE KEY-----
your_private_key_here
-----END OPENSSH PRIVATE KEY-----
"""

[mysql]
host = "127.0.0.1"
port = 3306
database = "miolingo"
user = "miolingo_user"
password = "your_password"

openai_api_key = "sk-your-openai-api-key"
google_cloud_tts_api_key = "your-google-cloud-api-key"
EOF

# 3. Run the container
docker run -d \
  --name miolingo \
  -p 8501:8501 \
  -v $(pwd)/.streamlit/secrets.toml:/app/.streamlit/secrets.toml:ro \
  -v $(pwd)/data/user-data:/app/data/user-data \
  --restart unless-stopped \
  ghcr.io/fairflow/miolingo:latest

# 4. Access at http://localhost:8501
```

---

## Using Docker Compose (Recommended)

Docker Compose simplifies multi-container setups and configuration management.

### Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/fairflow/miolingo.git
   cd miolingo
   ```

2. **Configure secrets:**

   ```bash
   cp .streamlit/secrets_template.toml .streamlit/secrets.toml
   nano .streamlit/secrets.toml  # Edit with your credentials
   ```

3. **Start the application:**

   ```bash
   docker-compose up -d
   ```

4. **View logs:**

   ```bash
   docker-compose logs -f miolingo
   ```

5. **Stop the application:**
   ```bash
   docker-compose down
   ```

---

## Building from Source

If you want to build the Docker image yourself instead of pulling from GitHub:

```bash
# Build the image
docker build -t miolingo:local .

# Run your local build
docker run -d \
  --name miolingo \
  -p 8501:8501 \
  -v $(pwd)/.streamlit/secrets.toml:/app/.streamlit/secrets.toml:ro \
  miolingo:local
```

---

## Available Docker Images

Images are automatically built and published to GitHub Container Registry on every release:

- **Latest stable:** `ghcr.io/fairflow/miolingo:latest`
- **Specific version:** `ghcr.io/fairflow/miolingo:v6.3.0`
- **Major version:** `ghcr.io/fairflow/miolingo:6`
- **Major.minor:** `ghcr.io/fairflow/miolingo:6.3`

Multi-architecture support:
- `linux/amd64` (x86_64)
- `linux/arm64` (ARM64, Apple Silicon)

---

## Configuration

### Environment Variables

You can override Streamlit settings via environment variables:

```bash
docker run -d \
  -e STREAMLIT_SERVER_PORT=8080 \
  -e STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
  -p 8080:8080 \
  ghcr.io/fairflow/miolingo:latest
```

### Volume Mounts

**Required:**
- `.streamlit/secrets.toml` - Database credentials and API keys

**Optional:**
- `data/user-data` - Persistent storage for user practice data
- Custom language materials directories

---

## Deploying to Production

### On a VPS (DigitalOcean, Hetzner, Linode, etc.)

1. **SSH into your VPS:**
   ```bash
   ssh user@your-vps-ip
   ```

2. **Install Docker:**
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER
   ```

3. **Set up Miolingo:**
   ```bash
   mkdir -p ~/miolingo/.streamlit
   cd ~/miolingo
   
   # Create secrets file
   nano .streamlit/secrets.toml
   
   # Pull and run
   docker pull ghcr.io/fairflow/miolingo:latest
   docker run -d \
     --name miolingo \
     -p 80:8501 \
     -v $(pwd)/.streamlit/secrets.toml:/app/.streamlit/secrets.toml:ro \
     -v $(pwd)/data:/app/data \
     --restart unless-stopped \
     ghcr.io/fairflow/miolingo:latest
   ```

4. **Set up HTTPS with Caddy (recommended):**
   ```bash
   docker run -d \
     --name caddy \
     -p 80:80 \
     -p 443:443 \
     -v caddy_data:/data \
     -v $(pwd)/Caddyfile:/etc/caddy/Caddyfile \
     --network host \
     caddy:latest
   ```

   **Caddyfile:**
   ```
   miolingo.yourdomain.com {
       reverse_proxy localhost:8501
   }
   ```

### Cost Considerations

**VPS Recommendations:**
- **Development/Small team:** Hetzner CX21 (€5.83/month, 2 vCPU, 4GB RAM)
- **Production:** Hetzner CX31 (€11.66/month, 2 vCPU, 8GB RAM)
- **High traffic:** DigitalOcean Droplet $24/month (4 vCPU, 8GB RAM)

**Running costs:**
- VPS: $6-24/month
- Google Cloud TTS API: ~$4/1M characters
- OpenAI API: ~$0.01/1K tokens (translation/enrichment)
- Total estimated: ~$10-50/month for 10-100 users

---

## Troubleshooting

### Container won't start

Check logs:
```bash
docker logs miolingo
```

Common issues:
- Missing secrets.toml
- Invalid SSH credentials
- Port 8501 already in use

### eSpeak NG not found

The Docker image builds eSpeak NG from source. If you see errors:
```bash
docker exec -it miolingo espeak-ng --version
```

### Database connection issues

Test SSH tunnel from container:
```bash
docker exec -it miolingo bash
nc -zv your-ssh-host 22
```

---

## Updating

Pull the latest image and restart:
```bash
docker pull ghcr.io/fairflow/miolingo:latest
docker-compose down
docker-compose up -d
```

Or with manual docker commands:
```bash
docker stop miolingo
docker rm miolingo
docker pull ghcr.io/fairflow/miolingo:latest
# Re-run the docker run command from Quick Start
```

---

## Contributing

If you're using Miolingo and want to contribute to hosting costs:
- [GitHub Sponsors](https://github.com/sponsors/fairflow) (coming soon)
- Host your own instance and share with others
- Contribute code, translations, or documentation

---

## Advanced: Multi-user Deployment

For organizations or language schools wanting to host Miolingo for multiple users:

1. Use a dedicated MySQL server (managed service recommended)
2. Set up connection pooling (already built-in)
3. Configure user limits and quotas
4. Monitor API usage costs
5. Consider user contribution model

Contact: io@miolingo.io for deployment consultation.
