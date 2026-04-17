# Dockerfile for Miolingo Pronunciation Trainer
# Uses Debian's prebuilt espeak-ng package instead of source build
# (previous multi-stage build added several minutes of cold-start time
# and ~400MB of build tooling with no functional benefit)

FROM python:3.12-slim

# Install runtime dependencies, including prebuilt eSpeak NG
RUN apt-get update && apt-get install -y \
    espeak-ng \
    ffmpeg \
    libsonic0 \
    portaudio19-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY data/ ./data/
COPY language_materials/ ./language_materials/
COPY docs/ ./docs/
COPY articles/ ./articles/
COPY .streamlit/ ./.streamlit/

# Create directory for practice history
RUN mkdir -p /app/data/user-data && \
    chmod 777 /app/data/user-data

# Expose Streamlit port
EXPOSE 8601

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8601/_stcore/health || exit 1

# Run as non-root user for security
RUN useradd -m -u 1000 miolingo && \
    chown -R miolingo:miolingo /app
USER miolingo

# Set environment variables
ENV STREAMLIT_SERVER_PORT=8601 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Start Streamlit
CMD ["streamlit", "run", "src/app.py", "--server.port=8601", "--server.address=0.0.0.0"]
