FROM swipl:11.0.0

# Install Python 3 (Debian trixie ships 3.13) and pip
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Verify both runtimes
RUN swipl --version && python3 --version

# Create non-root user
RUN groupadd -r euclid && useradd -r -g euclid -d /app -s /sbin/nologin euclid

WORKDIR /app

# Copy dependency files first (layer caching)
COPY pyproject.toml README.md LICENSE ./
COPY euclid_mcp/ euclid_mcp/

# Install Python package
RUN pip install --no-cache-dir --break-system-packages . && \
    rm -rf /root/.cache

# Copy integrations (HTTP API)
COPY integrations/ integrations/

# Set ownership
RUN chown -R euclid:euclid /app

USER euclid

# Default: MCP stdio mode
# Override with: docker run euclid-mcp python3 integrations/euclid_api.py
CMD ["python3", "-m", "euclid_mcp"]
