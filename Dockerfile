FROM python:3.11-slim

# Set a working directory
WORKDIR /app

# Install system deps for some optional packages (kept minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app

# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt

# Run as non-root user for safety
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

# Default command (Render will use this as start command if Dockerfile used)
ENTRYPOINT ["python", "-m", "src.conditor"]
