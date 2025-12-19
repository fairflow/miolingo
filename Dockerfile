# Multi-stage Dockerfile for Miolingo Pronunciation Trainer
# Optimized for fast builds and small image size

# Stage 1: Build eSpeak NG from source
FROM python:3.12-slim AS espeak-builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    autoconf \
    automake \
    libtool \
    pkg-config \
    git \
    libsonic-dev \
    ronn \
    kramdown \
    libpcaudio-dev \
    && rm -rf /var/lib/apt/lists/*

# Clone and build eSpeak NG
WORKDIR /build
RUN git clone --depth 1 https://github.com/espeak-ng/espeak-ng.git && \
    cd espeak-ng && \
    ./autogen.sh && \
    ./configure --prefix=/usr && \
    make && \
    make install DESTDIR=/espeak-install

# Stage 2: Final runtime image
FROM python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsonic0 \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy eSpeak NG from builder
COPY --from=espeak-builder /espeak-install/usr /usr

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
