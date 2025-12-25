# ============================================
# PYTHON 3.11 SLIM (Debian 12 Bookworm)
# ============================================

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# ============================================
# SYSTEM DEPENDENCIES (UPDATED FOR DEBIAN 12)
# ============================================

RUN apt-get update && apt-get install -y --no-install-recommends \
    # OpenCV dependencies (updated package names)
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libgthread-2.0-0 \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    # ZBar barcode library
    libzbar0 \
    # Build tools
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# PYTHON DEPENDENCIES
# ============================================

# Copy requirements first (layer caching)
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# ============================================
# APPLICATION CODE
# ============================================

# Copy backend application
COPY . .

# Create frontend directory (will be mounted as volume)
RUN mkdir -p /app/frontend

# ============================================
# CONFIGURATION
# ============================================

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV LOG_LEVEL=info

# Expose port
EXPOSE 8000

# ============================================
# HEALTH CHECK
# ============================================

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()"

# ============================================
# START COMMAND
# ============================================

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--log-level", "info"]
