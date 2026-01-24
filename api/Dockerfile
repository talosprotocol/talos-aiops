FROM python:3.11-slim

# Create user with consistent UID
RUN groupadd --system --gid 1001 talos && \
    useradd --system --uid 1001 --gid talos --create-home talos

WORKDIR /app

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Install Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY --chown=1001:1001 src/ src/

# Setup data metrics dir
RUN mkdir -p /data && chown -R 1001:1001 /data

USER talos

# Expose API port
EXPOSE 8200

# Run application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8200"]
