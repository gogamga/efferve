FROM python:3.11-slim AS base

# Runtime dependencies for scapy (WiFi packet capture)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tcpdump \
    wireless-tools \
    iw \
    libpcap-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .

# Data directory for SQLite database
RUN mkdir -p /app/data
VOLUME /app/data

EXPOSE 8000

# NET_ADMIN and NET_RAW capabilities required for WiFi sniffing
# Run with: docker run --cap-add=NET_ADMIN --cap-add=NET_RAW --network=host
CMD ["uvicorn", "efferve.main:app", "--host", "0.0.0.0", "--port", "8000"]
